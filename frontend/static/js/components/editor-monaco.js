// Monaco editor as an element: <editor-monaco></editor-monaco>
// With the readonly attribute the text cannot be changed and a corner button copies all of it
// The copy icon uses the Icons font loaded by barra-herramientas.js

class MonacoEditor extends HTMLElement {
  // Creates the editor inside this element; call it after Monaco is loaded
  create(options) {
    const readOnly = this.hasAttribute('readonly');
    this.editor = window.monaco.editor.create(this, { ...options, readOnly });
    if (readOnly) {
      this.insertAdjacentHTML('beforeend', '<button type="button" class="copy" title="Copy all" aria-label="Copy all">content_copy</button>');
      this.lastElementChild.addEventListener('click', () => navigator.clipboard.writeText(this.editor.getValue()));
    }
    return this.editor;
  }
}

customElements.define('editor-monaco', MonacoEditor);
