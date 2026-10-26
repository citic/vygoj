// Code editor as an element: <editor-codigo></editor-codigo>
// Joins the toolbar and the Monaco editor, and connects them
import './barra-herramientas.js';
import './editor-monaco.js';

class CodeEditor extends HTMLElement {
  connectedCallback() {
    this.innerHTML = '<barra-herramientas></barra-herramientas><editor-monaco class="editor"></editor-monaco>';
  }

  // Creates the Monaco editor and gives it to the toolbar; call it after Monaco is loaded
  create(options) {
    const editor = this.querySelector('editor-monaco').create(options);
    this.querySelector('barra-herramientas').editor = editor;
    return editor;
  }
}

customElements.define('editor-codigo', CodeEditor);
