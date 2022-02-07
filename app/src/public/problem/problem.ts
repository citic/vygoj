import { ExecutionResult, ProblemInterface } from '../../common/vygoj.js';

// Execution status enumeration
// TODO: this enumartion is duplicated from common/vygoj.ts
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

  constructor() {
    this.editors = [];
    // Default theme: https://github.com/ajaxorg/ace/tree/master/lib/ace/theme
    this.theme = 'ace/theme/xcode'; // monokai
    this.problem = null;
  }

  static main() {
    ProblemManager.instance.setup();
  }

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
      console.assert(index < this.result.results.length);
      this.editors[3].setValue(this.result.results[index].stdout || '', -1);
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
    for (let index = 0; index < this.result!.results.length; ++index) {
      const test = this.result!.results[index];
      test.compileOutput = clientDecode(test.compileOutput || '');
      test.message = clientDecode(test.message || '');
      test.stderr = clientDecode(test.stderr || '');
      test.stdout = clientDecode(test.stdout || '');
    }
  }

  updateResult() {
    console.assert(this.result);
    console.log(this.result);
    this.updateStatistics();
    this.updateTestCases();
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
  
  // Updates the test cases buttons after a run
  updateTestCases() {
    // Update the test case handlers (buttons) to show if passed or failed
    const buttons = document.querySelectorAll('#test_cases button');
    console.assert(this.result);
    console.assert(this.result!.results.length == buttons.length);
    for (let index = 0; index < this.result!.results.length; ++index) {
      const test = this.result!.results[index];
      const button = buttons[index];
      button.classList.remove('danger');
      button.classList.remove('action');
      if (test.status === Status.passed) {
        button.classList.add('action');
      } else {
        button.classList.add('danger');
      }
    }
    // Updates the standard output/error of the selected test case
    this.showTestOutput(this.activeTestCaseIndex);
  }
}

window.addEventListener('load', ProblemManager.main);
