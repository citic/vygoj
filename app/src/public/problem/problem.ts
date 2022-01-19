declare var ace: any;

class Problem {
  static main() {
    const problem = new Problem();
    problem.setup();
  }

  setup() {
    if (window.ace) {
      const editor = window.ace.edit("editor");
      editor.setTheme("ace/theme/monokai");
      editor.session.setMode("ace/mode/c_cpp");
    } else {
      console.error('Ace Code Editor library not found');
    }
  }
}

window.addEventListener('load', Problem.main);
