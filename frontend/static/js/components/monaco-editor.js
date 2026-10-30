// Monaco editor as an element: <monaco-editor language="cpp" readonly diff></monaco-editor>
import * as monaco from 'https://esm.sh/monaco-editor';
import EditorWorker from 'https://esm.sh/monaco-editor/editor/editor.worker?worker';

// Monaco computes some things, like diffs, in a worker
window.MonacoEnvironment = { getWorker: () => new EditorWorker() };

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
