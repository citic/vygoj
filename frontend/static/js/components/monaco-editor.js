// Monaco editor as an element: <monaco-editor language="cpp" readonly diff></monaco-editor>
import * as monaco from 'https://esm.sh/monaco-editor';
import EditorWorker from 'https://esm.sh/monaco-editor/editor/editor.worker?worker';

// Monaco computes some things, like diffs, in a worker
window.MonacoEnvironment = { getWorker: () => new EditorWorker() };

class MonacoEditor extends HTMLElement {
  // Lets <label for> point to this element
  static formAssociated = true;

  connectedCallback() {
    const options = {
      ariaLabel: document.querySelector(`label[for="${this.id}"]`)?.textContent,
      language: this.getAttribute('language') || 'plaintext',
      readOnly: this.hasAttribute('readonly'),
      minimap: { enabled: !this.hasAttribute('readonly') }, // Read-only boxes are small
      automaticLayout: true,
    };
    if (this.hasAttribute('diff')) {
      this.editor = monaco.editor.createDiffEditor(this, options);
      this.editor.setModel({ original: monaco.editor.createModel(''), modified: monaco.editor.createModel('') });
    } else {
      this.editor = monaco.editor.create(this, options);
    }
  }
}

customElements.define('monaco-editor', MonacoEditor);
