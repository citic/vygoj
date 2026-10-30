// Toolbar for a Monaco editor: <editor-toolbar for="code_editor"></editor-toolbar>
// The icons are ligatures of the Material Symbols font that the page loads

// [action, title, icon]
const buttons = [
  ['cut', 'Cut', 'content_cut'],
  ['copy', 'Copy', 'content_copy'],
  ['paste', 'Paste', 'content_paste'],
  ['undo', 'Undo', 'undo'],
  ['redo', 'Redo', 'redo'],
  ['clear', 'Clear all', 'backspace'],
  ['revert', 'Revert to initial code', 'restart_alt'],
  ['fullscreen', 'Fullscreen', 'fullscreen'],
];

class EditorToolbar extends HTMLElement {
  connectedCallback() {
    this.role = 'toolbar';
    this.insertAdjacentHTML('afterbegin', buttons.map(([action, title, icon]) => `<button type="button" id="${action}_button"
      class="material-symbols-outlined" data-action="${action}" title="${title}" aria-label="${title}">${icon}</button>`).join(''));
    // Only the buttons have an action; a click on the language list must not focus the editor
    this.addEventListener('click', (event) => event.target.dataset.action && this.run(event.target.dataset.action));
    // The fullscreen button changes its icon and title when entering or leaving, also with Esc
    document.addEventListener('fullscreenchange', () => {
      const button = this.querySelector('#fullscreen_button');
      button.textContent = document.fullscreenElement ? 'fullscreen_exit' : 'fullscreen';
      button.title = document.fullscreenElement ? 'Exit fullscreen' : 'Fullscreen';
      button.ariaLabel = button.title;
    });
  }

  async run(action) {
    const { editor } = document.getElementById(this.getAttribute('for'));
    const model = editor.getModel();
    const selection = model.getValueInRange(editor.getSelection());
    // Writes the text in the selection or range as its own step in the history, so Undo reverts it
    const write = (text, range = editor.getSelection()) => {
      editor.pushUndoStop();
      editor.executeEdits('toolbar', [{ range, text }]);
      editor.pushUndoStop();
    };
    const actions = {
      cut: async () => { await navigator.clipboard.writeText(selection); write(''); },
      copy: () => navigator.clipboard.writeText(selection),
      paste: async () => write(await navigator.clipboard.readText()),
      undo: () => editor.trigger('toolbar', 'undo'),
      redo: () => editor.trigger('toolbar', 'redo'),
      clear: () => window.confirm('Do you want to clear all the code?') && write('', model.getFullModelRange()),
      // Fullscreen for the parent, so the toolbar and the editor stay together
      fullscreen: () => (document.fullscreenElement
        ? document.exitFullscreen() : this.parentElement.requestFullscreen()),
    };
    try {
      await actions[action]?.();
    } catch {
      window.alert('The browser blocked the clipboard. Use Ctrl+X, Ctrl+C or Ctrl+V.');
    }
    editor.focus();
  }
}

customElements.define('editor-toolbar', EditorToolbar);
