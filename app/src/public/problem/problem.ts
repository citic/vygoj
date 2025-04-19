import { ExecutionResult, ProblemInterface } from '../../common/vygoj.js';
// import AceDiff from 'ace-diff';

const AceDiff = window.AceDiff;

// Execution status enumeration
// TODO: this enumeration is duplicated from common/vygoj.ts
export enum Status {
  pending = 'pending',
  passed = 'passed',
  wrong = 'wrong',
  timeout = 'timeout',
  compilerError = 'compilerError',
  runtimeError = 'runtimeError',
  internalError = 'internalError',
};

// Default given code for each supported programming language
// It may be a Map<string, string>
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

function loadConfig(key: string) {
  return window.localStorage.getItem(`${key}:${window.location.pathname}`);
}

function saveConfig(key: string, value: string) {
  window.localStorage.setItem(`${key}:${window.location.pathname}`, value);
}

function clientEncode(text: string) {
  // text: 'int main(int argc, char* argv[]) {\n  return atoi(argv[--argc]);\n}\n'
  // btoa: 'aW50IG1haW4oaW50IGFyZ2MsIGNoYXIqIGFyZ3ZbXSkgewogIHJldHVybiBhdG9pKGFyZ3ZbLS1hcmdjXSk7Cn0K'
  return window.btoa(text);
  // Judge0 uses: btoa(unescape(encodeURIComponent(text)) but unescape reverses encodeURIComponent
  // encodeURIComponent: 'int%20main(int%20argc%2C%20char*%20argv%5B%5D)%20%7B%0A%20%20return%20atoi(argv%5B--argc%5D)%3B%0A%7D%0A'
  // encodeURI: 'int%2520main(int%2520argc%252C%2520char*%2520argv%255B%255D)%2520%257B%250A%2520%2520return%2520atoi(argv%255B--argc%255D)%253B%250A%257D%250A'
  // btoa: 'aW50JTI1MjBtYWluKGludCUyNTIwYXJnYyUyNTJDJTI1MjBjaGFyKiUyNTIwYXJndiUyNTVCJTI1NUQpJTI1MjAlMjU3QiUyNTBBJTI1MjAlMjUyMHJldHVybiUyNTIwYXRvaShhcmd2JTI1NUItLWFyZ2MlMjU1RCklMjUzQiUyNTBBJTI1N0QlMjUwQQ=='
  // return window.btoa(window.encodeURI(window.encodeURIComponent(text)));
}

function clientDecode(data: string) {
  return window.atob(data);
  // try {
  //   return window.decodeURIComponent(window.decodeURI(window.atob(data)));
  // } catch (error) {
  //   console.error(error);
  //   return window.atob(data);
  // }
}

function hideElement(id: string) {
  const element = document.getElementById(id);
  console.assert(element);
  element!.classList.add('hidden');
}

function showElement(id: string) {
  const element = document.getElementById(id);
  console.assert(element);
  element!.classList.remove('hidden');
}

class ProblemManager {
  // Singleton instance
  static instance: ProblemManager = new ProblemManager();
  // References to all editors used in the problem page
  editors: AceAjax.Editor[];
  // Theme style in all editors
  theme: string;
  // The problem model fetched from server
  problem: ProblemInterface | null;
  // Index of the current shown test case
  activeTestCaseIndex: number = 0;
  // The Run button element
  runButton: HTMLButtonElement | null = null;
  // The result after running the user code
  result: ExecutionResult | null = null;
  // Shows the diff between expected output and user standard output
  differ: AceDiff | null = null;

  constructor() {
    this.editors = [];
    // Default theme: https://github.com/ajaxorg/ace/tree/master/lib/ace/theme
    this.theme = 'ace/theme/xcode'; // monokai
    this.problem = null;
  }

  static main() {
    ProblemManager.instance.setup();
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
    this.runButton = document.getElementById('run_button') as HTMLButtonElement;
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

  setupTestCaseEditor(id: string) {
    const editor = ace.edit(id);
    editor.setTheme(this.theme);
    editor.setOption('readOnly', true);
    editor.setOption('showInvisibles', true);
    // editor.setOption('maxLines', 15);
    editor.resize();
    this.editors.push(editor);
  }

  async fetchProblem() {
    console.assert(this.problem === null);
    this.problem = await ProblemManager.sendJson({ action: 'fetch_problem' });
  }

  static async sendJson(object: Object, uri = '') {
    const params = ProblemManager.createMessage(object);
    const response = await fetch(uri || window.location.href, params);
    const json = await response.json();
    return json;
  }

  static createMessage(object: Object, method = 'POST') {
    return {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(object),
    };
  }

  static getName() {
    const mainElement = document.getElementById('problem');
    return mainElement?.dataset.name;
  }

  loadTestCases() {
    console.assert(this.problem);
    const buttons = document.getElementsByClassName('test_button');
    console.assert(buttons.length === this.problem?.tests.length);
    for (let index = 0; index < buttons.length; index += 1) {
      buttons[index].addEventListener('click', () => {
        this.showTestCase(index);
      });
    }
    if (buttons.length > 0) {
      this.activeTestCaseIndex = parseInt(loadConfig('test') || '0', 10);
      this.showTestCase(this.activeTestCaseIndex);
    }
  }

  showTestCase(index: number) {
    console.assert(this.problem);
    console.assert(this.editors.length === 4);

    // Show input, expected output, and user output for this test case
    this.editors[1].setValue(this.problem?.tests[index].input || '', -1);
    this.editors[2].setValue(this.problem?.tests[index].output || '', -1);
    this.showTestOutput(index);

    // Deselect previous test case number
    const buttons = document.getElementsByClassName('test_button');
    console.assert(this.activeTestCaseIndex < buttons.length);
    buttons[this.activeTestCaseIndex].classList.remove('selected');

    // Mark this test case as the active in the interface
    this.activeTestCaseIndex = index;
    console.assert(index < buttons.length);
    buttons[index].classList.add('selected');
    saveConfig('test', `${index}`);
  }

  // Shows the standard output and error of the given test case after a run
  showTestOutput(index: number) {
    if (this.result) {
      // Show standard output
      console.assert(index < this.result.results.length);
      const test = this.result.results[index];
      this.editors[3].setValue(test.stdout || '', -1);
      // But if test case was failed, show diff instead
      this.showOutputDiff(index);
      // Show standard error
      this.updateErrorOutput(index);
      // Show message if nay
      this.updateVerdict(index);
    }
  }

  loadUserCode() {
    // TODO: add language combo box
    const language = 'C';
    console.assert(this.problem);

    // 1. Local storage
    let initialCode = loadConfig('code');

    // 2. Problem's initial code for the proramming language
    if (initialCode === null && this.problem?.initialCodeFor
      && this.problem?.initialCodeFor[language]) {
      initialCode = this.problem?.initialCodeFor[language]!;
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
    this.runButton!.addEventListener('click', async () => {
      await this.runSolution();
    });
  }

  async runSolution() {
    // TODO: add language combo box
    const language = 'C';
    // Disable the Run button while the backend is running the code
    this.runButton!.disabled = true;
    this.runButton!.textContent = 'Running';
    // Send the code to the backend and wait the result
    this.result = await ProblemManager.sendJson({
      action: 'run',
      language,
      code: clientEncode(this.editors[0].getValue()),
    });
    // The result has been received, decode it and update the test cases
    this.decodeResult();
    this.updateResult();
    // Enable the Run button again
    this.runButton!.textContent = 'Run';
    this.runButton!.disabled = false;
  }

  decodeResult() {
    console.assert(this.result);
    this.result!.compileOutput = clientDecode(this.result!.compileOutput || '');
    // TODO: Change LC_ALL=en_US in compiler environment to avoid Unicode quotes
    this.result!.compileOutput = this.result!.compileOutput.replace(/â/g, '‘');
    for (let index = 0; index < this.result!.results.length; ++index) {
      const test = this.result!.results[index];
      test.message = clientDecode(test.message || '');
      test.stderr = clientDecode(test.stderr || '');
      test.stdout = clientDecode(test.stdout || '');
    }
  }

  updateResult() {
    console.assert(this.result);
    console.log(this.result);
    this.updateStatistics();
    this.updateCompileOutput();
    this.updateTestCases();
    this.updateErrorOutput(this.activeTestCaseIndex);
    this.updateVerdict(this.activeTestCaseIndex);
  }

  // Updates the count of passed test cases and points after a run
  updateStatistics() {
    const passedTestElement = document.getElementById('passed_test_count');
    console.assert(passedTestElement);
    if (passedTestElement) {
      passedTestElement.textContent = String(this.result?.passedTestCount);
    }
    const totalPointsElement = document.getElementById('user_points');
    console.assert(totalPointsElement);
    if (totalPointsElement) {
      totalPointsElement.textContent = String(this.result?.points);
    }
  }

  // Shows the compiler diagnostics (warnings or errors), if any
  updateCompileOutput(message: string | null = null) {
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
      diagnosticsElement!.textContent = compileOutput;
      showElement('diagnostics_wrapper');
    } else {
      hideElement('diagnostics_wrapper');
    }
  }

  // Shows standard error output for the selected test case
  updateErrorOutput(index: number) {
    // The DOM element where the output will be shown
    const stderrElement = document.getElementById('stderr');
    console.assert(stderrElement);
    // The program stderr output text for the active test case
    let stderrOutput = null;
    console.assert(this.result);
    console.assert(index < this.result!.results.length);
    // Compiler output should be identical for each test case, we take the first one
    if (this.result && index < this.result!.results.length) {
      stderrOutput = this.result.results[index].stderr;
    }
    // If there is output text, show it
    if (stderrOutput && stderrOutput.length > 0) {
      stderrElement!.textContent = stderrOutput;
      showElement('stderr_wrapper');
    } else {
      hideElement('stderr_wrapper');
    }
  }

  // Shows a diff output instead of standard output
  showOutputDiff(index: number) {
    // Expected output
    console.assert(this.problem);
    console.assert(index < this.problem!.tests.length);
    const expectedOutput = this.problem!.tests[index].output;

    // User output
    console.assert(this.result);
    console.assert(index < this.result!.results.length);
    const userOutput = this.result!.results[index].stdout;

    // TODO: Use AceDiff always and decrease gutter width
    if (this.result!.results[index].status == Status.wrong) {
      // Hide expected output and user output and show diff element
      hideElement('active_test_expected_output_wrapper');
      hideElement('active_test_user_output_wrapper');
      showElement('output_diff_wrapper');

      // Create a Ace Diff in output_diff element
      this.differ = new AceDiff({
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
    console.assert(this.result!.results.length == buttons.length);
    for (let index = 0; index < this.result!.results.length; ++index) {
      const test = this.result!.results[index];
      const button = buttons[index];
      button.classList.remove('failed');
      button.classList.remove('passed');
      if (test.status === Status.passed) {
        button.classList.add('passed');
      } else {
        button.classList.add('failed');
      }
    }
    // Updates the standard output/error of the selected test case
    this.showTestOutput(this.activeTestCaseIndex);
  }

  // Shows or updates the verdict message
  updateVerdict(index: number) {
    // The DOM element where the verdict will be shown
    const verdictElement = document.getElementById('test_verdict');
    console.assert(verdictElement);
    // The verdict text for the active test case
    let verdict = null;
    console.assert(this.result);
    console.assert(index < this.result!.results.length);
    // Compiler output should be identical for each test case, we take the first one
    if (this.result && index < this.result!.results.length) {
      const test = this.result.results[index];
      verdict = `Test case ${index + 1} verdict: ${test.status}`;
      if (test.message) {
        verdict += `: ${test.message}`;
      }
      const time = test.wallTime || test.cpuTime || '';
      if (time.length > 0) {
        verdict += `. It took ${time}s`;
      }
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
      verdictElement!.textContent = verdict;
    } else {
      verdictElement!.textContent = '';
    }
  }
}

window.addEventListener('load', ProblemManager.main);
