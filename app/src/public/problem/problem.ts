import { ProblemInterface } from '../../common/vygoj.js';

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

  constructor() {
    this.editors = [];
    this.theme = 'ace/theme/xcode'; // monokai
    this.problem = null;
  }

  static main() {
    ProblemManager.instance.setup();
  }

  async setup() {
    try {
      if (!window.ace) {
        throw new Error('Ace Code Editor library not found');
      }
      this.setupEditor();
      this.setupTestCaseEditors();
      await this.fetchProblem();
      this.loadUserCode();
      this.loadTestCases();
    } catch (error) {
      console.error(error);
    }
  }

  setupEditor() {
    const editor = window.ace.edit('editor');
    editor.setTheme(this.theme);
    editor.session.setMode('ace/mode/c_cpp');
    // Automatically adjust height to the number of lines typed by user
    editor.setOption('maxLines', 50); // Infinity
    editor.setOption('tabSize', 2); // Google code style
    this.editors.push(editor);
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
      this.showTestCase(0);
    }
  }

  showTestCase(index: number) {
    console.assert(this.problem);
    console.assert(this.editors.length === 4);

    // Show input, expected output, and user output for this test case
    this.editors[1].setValue(this.problem?.tests[index].input || '', -1);
    this.editors[2].setValue(this.problem?.tests[index].output || '', -1);
    // this.editors[3].setValue(this.problem?.tests[index].userOutput, -1);

    // Deselect previous test case number
    const buttons = document.getElementsByClassName('test_button');
    console.assert(this.activeTestCaseIndex < buttons.length);
    buttons[this.activeTestCaseIndex].classList.remove('selected');

    // Mark this test case as the active in the interface
    this.activeTestCaseIndex = index;
    console.assert(index < buttons.length);
    buttons[index].classList.add('selected');
  }

  loadUserCode() {
    console.assert(this.problem);
    // TODO: add language combo box
    const language = 'C';
    let initialCode = undefined;
    // 1. Local storage
    // 2. Problem's initial code for the proramming language
    // 3. Default code for the programming language
    initialCode = defaultCodeFor[language];
    initialCode = initialCode || '';
    this.editors[0].setValue(initialCode, -1);
  }
}

window.addEventListener('load', ProblemManager.main);
