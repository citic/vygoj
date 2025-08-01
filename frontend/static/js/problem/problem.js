import {
  encode, ExecutionResult, Problem, Status,
} from '../vygoj.js';
// import AceDiff from 'ace-diff';

// Default given code for each supported programming language
// It may be a Map<string, string>
// TODO(jhc): Remove, it must come from frontend
const defaultCodeFor = {
  C: `#include <stdio.h>

int main(void) {
  printf("Hello world!\\n");
  return 0;
}
`,
  'C++': `#include <iostream>
  
int main() {
  std::cout << "Hello world!" << std::endl;
  return 0;
}
`,
};

function loadConfig(key) {
  return window.localStorage.getItem(`${key}:${window.location.pathname}`);
}

function saveConfig(key, value) {
  window.localStorage.setItem(`${key}:${window.location.pathname}`, value);
}

function hideElement(id) {
  const element = document.getElementById(id);
  console.assert(element);
  element.classList.add('hidden');
}

function showElement(id) {
  const element = document.getElementById(id);
  console.assert(element);
  element.classList.remove('hidden');
}

class ProblemManager {
  // Singleton instance
  constructor() {
    // References to all editors used in the problem page
    this.editors = []; // AceAjax.Editor
    // Theme style in all editors
    // Default theme: https://github.com/ajaxorg/ace/tree/master/lib/ace/theme
    this.theme = 'ace/theme/xcode'; // monokai
    // The problem model fetched from server
    this.problem = null; // class Problem instance
    // Index of the current shown test case
    this.activeTestCaseIndex = 0;
    // The Run button element
    this.runButton = null; // HTMLButtonElement
    // The result after running the user code
    this.result = null; // class ExecutionResult instance
    // Shows the diff between expected output and user standard output
    this.differ = null; // class AceDiff instance
  }

  static main() {
    const instance = new ProblemManager();
    instance.setup();
  }

  // TODO: Problem statement may have source code snippets, highlight them using a client library
  // such as highlight.js or prismjs
  async setup() {
    try {
      this.setupReferences();
      this.setupCodeEditor();
      this.setupTestCaseEditors();
      await this.fetchProblem();
      this.loadUserCode();
      this.loadTestCases();
      this.setupRunEnvironment();
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : String(error);
      this.updateCompileOutput(message);
    }
  }

  setupReferences() {
    if (!window.ace) {
      throw new Error('Ace Code Editor library not found');
    }
    this.runButton = document.getElementById('run_button');
    if (!this.runButton) {
      throw Error('could not find run_button element');
    }
  }

  setupCodeEditor() {
    const editor = window.ace.edit('code_editor');
    editor.setTheme(this.theme);
    editor.session.setMode('ace/mode/c_cpp');
    // Automatically adjust height to the number of lines typed by user
    editor.setOption('maxLines', 50); // Infinity
    editor.setOption('tabSize', 2); // Google code style
    this.editors.push(editor);
    editor.on('change', () => {
      const code = editor.getValue();
      saveConfig('code', code);
      if (this.runButton) {
        this.runButton.disabled = code.trim().length === 0;
      }
    });
  }

  setupTestCaseEditors() {
    this.setupTestCaseEditor('active_test_input');
    this.setupTestCaseEditor('active_test_expected_output');
    this.setupTestCaseEditor('active_test_user_output');
  }

  setupTestCaseEditor(id) {
    console.assert(window.ace);
    const editor = window.ace.edit(id);
    editor.setTheme(this.theme);
    editor.setOption('readOnly', true);
    editor.setOption('showInvisibles', true);
    // editor.setOption('maxLines', 15);
    editor.resize();
    this.editors.push(editor);
  }

  async fetchProblem() {
    console.assert(this.problem === null);
    const message = { action: 'fetch_problem' }; // Message object
    this.problem = new Problem(await ProblemManager.sendJson(message));
  }

  static async sendJson(object, uri = '') {
    const params = ProblemManager.createMessage(object);
    const response = await fetch(uri || window.location.href, params);
    const json = await response.json();
    return json;
  }

  // TODO(jhc): Uniform with Message() object
  static createMessage(object, method = 'POST') {
    return {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(object),
    };
  }

  /// Return the name of the problem from the loaded web page in browser
  static getName() {
    // Find DOM object <main id="problem" data-name="problem_name">
    const mainElement = document.getElementById('problem');
    // Return the value of data-name attribute
    return mainElement?.dataset.name;
  }

  loadTestCases() {
    console.assert(this.problem);
    const buttons = document.getElementsByClassName('test_button');
    console.assert(buttons.length === this.problem.tests.length);
    // Make each test case button clickable
    for (let index = 0; index < buttons.length; index += 1) {
      buttons[index].addEventListener('click', () => {
        this.showTestCase(index);
      });
    }
    // Make the last selected test case (in local storage) as the active one
    if (buttons.length > 0) {
      this.activeTestCaseIndex = parseInt(loadConfig('test') || '0', 10);
      this.showTestCase(this.activeTestCaseIndex);
    }
  }

  showTestCase(index) {
    console.assert(this.problem);
    console.assert(this.editors.length === 4);
    // Show input, expected output, and user output for this test case
    this.editors[1].setValue(this.problem.tests[index].input || '', -1);
    this.editors[2].setValue(this.problem.tests[index].output || '', -1);
    this.showTestOutput(index);
    // Deselect previous test case number
    const buttons = document.getElementsByClassName('test_button');
    console.assert(this.activeTestCaseIndex < buttons.length);
    buttons[this.activeTestCaseIndex].classList.remove('selected');
    // Mark this test case as the active in the interface
    console.assert(index < buttons.length);
    this.activeTestCaseIndex = index;
    buttons[index].classList.add('selected');
    saveConfig('test', `${index}`);
  }

  // Shows the standard output and error of the given test case after a run
  showTestOutput(index) {
    if (this.result) {
      // Show standard output
      const test = index < this.result.results.length ? this.result.results[index] : null;
      const output = test?.stdout || '';
      this.editors[3].setValue(output, -1);
      // But if test case was failed, show diff instead
      this.showOutputDiff(index);
      // Show standard error
      this.updateErrorOutput(index);
      // Show message if nay
      this.updateVerdict(index);
    }
  }

  getProblemLanguage() {
    console.assert(this.problem);
    if (this.problem.languages && this.problem.languages.length > 0) {
      return this.problem.languages[0];
    }
    return 'C';
  }

  loadUserCode() {
    // TODO: add language combo box
    console.assert(this.problem);
    const language = this.getProblemLanguage();

    // 1. Local storage
    let initialCode = loadConfig('code');

    // 2. Problem's initial code for the programming language
    if (initialCode === null && this.problem.initialCodeFor
        && this.problem.initialCodeFor[language]) {
      initialCode = this.problem.initialCodeFor[language];
    }

    // 3. Default code for the programming language
    if (!initialCode) {
      initialCode = defaultCodeFor[language];
    }

    // Show the initial code in the editor
    initialCode = initialCode || '';
    this.editors[0].setValue(initialCode, -1);
    if (this.runButton) {
      this.runButton.disabled = initialCode.trim().length === 0;
    }
  }

  setupRunEnvironment() {
    console.assert(this.runButton);
    console.assert(this.editors.length > 0);
    // When the Run button is pressed
    this.runButton.addEventListener('click', async () => {
      await this.runSolution();
    });
  }

  async runSolution() {
    // TODO: add language combo box
    const language = this.getProblemLanguage();
    // Disable the Run button while the backend is running the code
    this.runButton.disabled = true;
    this.runButton.textContent = 'Running';
    // Send the code to the backend and wait the result
    this.result = new ExecutionResult(await ProblemManager.sendJson({
      action: 'run',
      language,
      code: encode(this.editors[0].getValue()),
    }));
    // The result has been received, decode it and update the test cases
    this.updateResult();
    // Enable the Run button again
    this.runButton.textContent = 'Run';
    this.runButton.disabled = false;
  }

  updateResult() {
    console.assert(this.result);
    console.dir(this.result);
    this.updateStatistics();
    this.updateCompileOutput();
    this.updateTestCases();
    this.updateErrorOutput(this.activeTestCaseIndex);
    this.updateVerdict(this.activeTestCaseIndex);
  }

  // Updates the count of passed test cases and count of points after a run
  updateStatistics() {
    console.assert(this.result);

    const passedTestElement = document.getElementById('passed_test_count');
    console.assert(passedTestElement);
    passedTestElement.textContent = String(this.result.passedTestCount);

    const totalTestCount = document.getElementById('total_test_count');
    console.assert(totalTestCount);
    totalTestCount.textContent = String(this.result.results.length);

    const totalPointsElement = document.getElementById('user_points');
    console.assert(totalPointsElement);
    totalPointsElement.textContent = String(this.result.points);
  }

  // Shows the compiler diagnostics (warnings or errors), if any
  updateCompileOutput(message = null) {
    // The DOM element where the output will be shown
    const diagnosticsElement = document.getElementById('diagnostics');
    console.assert(diagnosticsElement);
    // The compiler output text
    let compileOutput = message;
    // If no message was provided, get the compiler output from the result
    if (message === null && this.result) {
      compileOutput = this.result.compileOutput;
    }
    // If there is a diagnostic, show it
    if (compileOutput && compileOutput.length > 0) {
      diagnosticsElement.textContent = compileOutput;
      showElement('diagnostics_wrapper');
    } else {
      hideElement('diagnostics_wrapper');
    }
  }

  // Shows standard error output for the selected test case
  updateErrorOutput(index) {
    // The DOM element where the output will be shown
    const stderrElement = document.getElementById('stderr');
    console.assert(stderrElement);
    // The program stderr output text for the active test case
    let stderrOutput = null;
    console.assert(this.result);
    // If the test case result exists, get its message, otherwise (compilation error?) clear field
    if (index < this.result.results.length) {
      // Compiler output should be identical for each test case, we take the first one
      // TODO(jhc): Compile output is in the problem result instead of test result
      if (this.result && index < this.result.results.length) {
        stderrOutput = this.result.results[index].stderr;
      }
    }
    // If there is output text, show it
    if (stderrOutput && stderrOutput.length > 0) {
      stderrElement.textContent = stderrOutput;
      showElement('stderr_wrapper');
    } else {
      hideElement('stderr_wrapper');
    }
  }

  // Shows a diff output instead of standard output
  showOutputDiff(index) {
    // Expected output
    console.assert(this.problem);
    console.assert(index < this.problem.tests.length);
    const expectedOutput = this.problem.tests[index].output;
    // User output
    console.assert(this.result);
    // If the test case result exists, get its message, otherwise (compilation error?) clear field
    let userOutput = null;
    if (index < this.result.results.length) {
      userOutput = this.result.results[index].stdout;
    }
    // TODO: Use AceDiff always and decrease gutter width
    if (userOutput && this.result.results[index].status === Status.WRONG) {
      // Hide expected output and user output and show diff element
      hideElement('active_test_expected_output_wrapper');
      hideElement('active_test_user_output_wrapper');
      showElement('output_diff_wrapper');
      // Create a Ace Diff in output_diff element
      this.differ = new window.AceDiff({
        // ace: window.ace,
        element: '#output_diff',
        diffGranularity: 'specific',
        left: {
          editable: false,
          // copyLinkEnabled: false,
          content: expectedOutput,
        },
        right: {
          editable: false,
          // copyLinkEnabled: false,
          content: userOutput,
        },
      });
    } else {
      // Show expected output and user output and hide diff element
      hideElement('output_diff_wrapper');
      showElement('active_test_expected_output_wrapper');
      showElement('active_test_user_output_wrapper');

      if (this.differ) {
        // this.differ.destroy();
        this.differ = null;
      }
    }
  }

  // Updates the test cases buttons after a run
  updateTestCases() {
    // Update the test case handlers (buttons) to show if passed or failed
    const buttons = document.querySelectorAll('#test_cases button');
    console.assert(this.result);
    for (let index = 0; index < buttons.length; index += 1) {
      const test = index < this.result.results.length ? this.result.results[index] : null;
      const button = buttons[index];
      button.classList.remove('failed');
      button.classList.remove('passed');
      if (test === null) {
        // Do not add any class to the button, possible compilation error, no test case were run
      } else if (test.status === Status.PASSED) {
        button.classList.add('passed');
      } else {
        button.classList.add('failed');
      }
      // Updates the standard output/error of the selected test case
      this.showTestOutput(this.activeTestCaseIndex);
    }
  }

  // Shows or updates the verdict message
  updateVerdict(index) {
    // The DOM element where the verdict will be shown
    const verdictElement = document.getElementById('test_verdict');
    console.assert(verdictElement);
    // The verdict text for the active test case
    let verdict = null;
    console.assert(this.result);
    // Compiler output should be identical for each test case, we take the first one
    if (this.result && index < this.result.results.length) {
      const test = this.result.results[index];
      // console.dir(test);
      verdict = `Test case ${index + 1} verdict: ${test.status}`;
      if (test.message) {
        verdict += `: ${test.message}`;
      }
      const time = test.wallTime || test.cpuTime || '';
      verdict += `. It took ${time}s`;
      if (test.memory) {
        verdict += `, ${test.memory}B`;
      }
      if (test.threadCount) {
        verdict += `, ${test.threadCount} secondary threads`;
      }
      if (test.exitCode) {
        verdict += `, and exited with code ${test.exitCode}`;
      }
    }
    // If there is output text, show it
    if (verdict && verdict.length > 0) {
      verdictElement.textContent = verdict;
    } else {
      verdictElement.textContent = '';
    }
  }
}

window.addEventListener('load', ProblemManager.main);
