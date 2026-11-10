// Monaco editor as an element: <monaco-editor language="cpp" readonly diff></monaco-editor>
import * as monaco from 'https://esm.sh/monaco-editor';
import EditorWorker from 'https://esm.sh/monaco-editor/editor/editor.worker?worker';

// Monaco computes some things, like diffs, in a worker
window.MonacoEnvironment = { getWorker: () => new EditorWorker() };

// Monaco has one theme for all editors: dark when the page is dark, by user choice or by the OS
const prefersDark = matchMedia('(prefers-color-scheme: dark)');
const setTheme = () => {
  const scheme = document.documentElement.dataset.colorScheme || (prefersDark.matches ? 'dark' : 'light');
  monaco.editor.setTheme(scheme === 'dark' ? 'vs-dark' : 'vs');
};
prefersDark.addEventListener('change', setTheme);
setTheme();

// Returns the column of a line of code that the compiler calls displayedColumn. gcc counts the
// columns as displayed, with a tab up to the next multiple of 8, and Monaco counts characters
function characterColumn(text, displayedColumn) {
  let displayed = 1;
  for (let index = 0; index < text.length; index += 1) {
    if (displayed >= displayedColumn) {
      return index + 1;
    }
    displayed += text[index] === '\t' ? 8 - ((displayed - 1) % 8) : 1;
  }
  return text.length + 1;
}

class MonacoEditor extends HTMLElement {
  // Lets <label for> point to this element
  static formAssociated = true;

  // Changing the language attribute changes the highlighting of the code
  static observedAttributes = ['language'];

  connectedCallback() {
    const options = {
      // Accessible name: its aria-label attribute or the text of its <label for>
      ariaLabel: this.getAttribute('aria-label') || document.querySelector(`label[for="${this.id}"]`)?.textContent,
      language: this.getAttribute('language') || 'plaintext',
      readOnly: this.hasAttribute('readonly'),
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      automaticLayout: true,
      // A diff always shows its two sides, even when narrow, as the labels above it say. Without
      // the overview ruler and the dragging of their border, both sides are equally wide
      useInlineViewWhenSpaceIsLimited: false,
      renderOverviewRuler: false,
      enableSplitViewResizing: false,
    };
    if (this.hasAttribute('diff')) {
      this.editor = monaco.editor.createDiffEditor(this, options);
      this.editor.setModel({ original: monaco.editor.createModel(''), modified: monaco.editor.createModel('') });
    } else {
      this.editor = monaco.editor.create(this, options);
      this.editor.onDidChangeModelContent(() => this.moveDiagnostics());
    }
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (this.editor) {
      monaco.editor.setModelLanguage(this.editor.getModel(), newValue || 'plaintext');
    }
  }

  // Underlines the diagnostics of the compiler in the code: [{ line, column, severity, message }],
  // with the columns as the compiler counts them. It underlines the word at the column, or the
  // rest of the line when there is no word or column
  showDiagnostics(diagnostics) {
    const model = this.editor.getModel();
    const severities = {
      error: monaco.MarkerSeverity.Error,
      warning: monaco.MarkerSeverity.Warning,
      note: monaco.MarkerSeverity.Info,
    };
    // The compiler output is untrusted: a line out of the code goes to the nearest one
    this.markers = diagnostics.map(({
      line, column, severity, message,
    }) => {
      const lineNumber = Math.min(Math.max(line, 1), model.getLineCount());
      const text = model.getLineContent(lineNumber);
      const character = column && characterColumn(text, column);
      const word = character && model.getWordAtPosition({ lineNumber, column: character });
      const end = word ? word.endColumn : model.getLineMaxColumn(lineNumber);
      const first = character || model.getLineFirstNonWhitespaceColumn(lineNumber) || 1;
      // At the end of a line, e.g. a missing semicolon, the last character is underlined
      const start = Math.min(word ? word.startColumn : first, Math.max(end - 1, 1));
      return {
        startLineNumber: lineNumber,
        endLineNumber: lineNumber,
        startColumn: start,
        endColumn: end,
        severity: severities[severity] ?? monaco.MarkerSeverity.Warning,
        message,
      };
    });
    // Monaco keeps markers where they are when the code changes, but it moves decorations with
    // their text. A decoration for each marker moves it
    const stickiness = monaco.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges;
    const decorations = this.markers.map((range) => ({ range, options: { stickiness } }));
    this.decorations = model.deltaDecorations(this.decorations ?? [], decorations);
    monaco.editor.setModelMarkers(model, 'diagnostics', this.markers);
  }

  // Moves the underlines with their text when the code changes. The ones of deleted text, e.g. a
  // fixed error or code of another language, disappear
  moveDiagnostics() {
    if (!this.markers?.length) {
      return;
    }
    const model = this.editor.getModel();
    const markers = this.markers.map((marker, index) => {
      const range = model.getDecorationRange(this.decorations[index]);
      return range && !range.isEmpty() && { ...marker, ...range };
    }).filter((marker) => marker);
    monaco.editor.setModelMarkers(model, 'diagnostics', markers);
  }

  // Moves the cursor to the start of the code of a diagnostic, in the middle of the editor
  goToDiagnostic(index) {
    const id = this.decorations?.[index];
    const range = id && this.editor.getModel().getDecorationRange(id);
    if (range) {
      this.editor.setPosition(range.getStartPosition());
      this.editor.revealLineInCenter(range.startLineNumber);
      this.editor.focus();
    }
  }
}

customElements.define('monaco-editor', MonacoEditor);
