class Problem {
  // References to all editors used in the problem page
  editors: Object[];

  // Theme style in all editors
  theme: string;

  constructor() {
    this.editors = [];
    this.theme = 'ace/theme/xcode'; // monokai
  }

  static main() {
    const problem = new Problem();
    problem.setup();
  }

  setup() {
    if (window.ace) {
      this.setupEditor();
      this.setupTestCases();
      this.loadCode();
    } else {
      console.error('Ace Code Editor library not found');
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

  setupTestCases() {
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

  // eslint-disable-next-line class-methods-use-this
  async loadCode() {
    try {
      const problem = await Problem.sendJson({ action: 'fetch_problem' });
      console.log(problem);
    } catch (error) {
      console.error(error);
    }
  }

  static async sendJson(object: Object, uri = '') {
    const params = Problem.createMessage(object);
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
}

window.addEventListener('load', Problem.main);
