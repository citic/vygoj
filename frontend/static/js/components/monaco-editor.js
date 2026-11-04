// Monaco editor as an element: <monaco-editor language="cpp" readonly diff></monaco-editor>
import * as monaco from 'https://esm.sh/monaco-editor';
import EditorWorker from 'https://esm.sh/monaco-editor/editor/editor.worker?worker';

// Monaco computes some things, like diffs, in a worker
window.MonacoEnvironment = { getWorker: () => new EditorWorker() };

// C standard library functions (json/c-library.json) for suggestions and parameter hints
const cLibrary = fetch('/json/c-library.json')
  .then((response) => response.json())
  .then((functions) => new Map(Object.entries(functions)))
  .catch(() => new Map());

['c', 'cpp'].forEach((language) => {
  monaco.languages.registerCompletionItemProvider(language, {
    provideCompletionItems: async (model, position) => {
      const library = await cLibrary;
      const { word } = model.getWordUntilPosition(position);
      const functions = [...library].map(([name, { signature, documentation }]) => ({
        label: name,
        kind: monaco.languages.CompletionItemKind.Function,
        insertText: name,
        detail: signature,
        documentation,
      }));
      // Monaco stops suggesting the words in the code when a provider gives suggestions
      const words = [...new Set(model.getValue().match(/[A-Za-z_]\w*/g))]
        .filter((name) => name !== word && !library.has(name))
        .map((name) => ({
          label: name,
          kind: monaco.languages.CompletionItemKind.Text,
          insertText: name,
        }));
      return { suggestions: [...functions, ...words] };
    },
  });

  monaco.languages.registerSignatureHelpProvider(language, {
    signatureHelpTriggerCharacters: ['(', ','],
    provideSignatureHelp: async (model, position) => {
      // Name and arguments of the call the cursor is in, e.g. "fgets(buffer, "
      const line = model.getLineContent(position.lineNumber).slice(0, position.column - 1);
      const [, name, args] = line.match(/(\w+)\(([^()]*)$/) ?? [];
      const { signature, documentation } = (await cLibrary).get(name) ?? {};
      if (!signature) return null;
      const parameters = signature.slice(signature.indexOf('(') + 1, -1).split(', ')
        .map((label) => ({ label }));
      return {
        value: {
          signatures: [{ label: signature, documentation, parameters }],
          activeSignature: 0,
          activeParameter: args.split(',').length - 1,
        },
        dispose: () => {},
      };
    },
  });
});

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
    }
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (this.editor) {
      monaco.editor.setModelLanguage(this.editor.getModel(), newValue || 'plaintext');
    }
  }
}

customElements.define('monaco-editor', MonacoEditor);
