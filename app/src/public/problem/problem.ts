// eslint-disable-next-line no-var
declare var ace: any; // TODO: npm install @types/ace

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
    } else {
      console.error('Ace Code Editor library not found');
    }
  }

  setupEditor() {
    const editor = ace.edit('editor');
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
}

window.addEventListener('load', Problem.main);
