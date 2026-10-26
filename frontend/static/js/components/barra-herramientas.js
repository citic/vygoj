// Toolbar for the code editor: <barra-herramientas></barra-herramientas>
// problem.js gives it the Monaco editor, the problem languages and the initial code

// Icons are a font: each button writes the icon name ("undo") and the font draws it
document.fonts.add(new FontFace('Icons', `url(${new URL('../../fonts/icons.woff2', import.meta.url)})`));

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

class Toolbar extends HTMLElement {
  constructor() {
    super();
    // Shadow DOM: this HTML and CSS do not mix with the page's
    this.attachShadow({ mode: 'open' }).innerHTML = `
      <style>
        :host {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 2px;
          padding: 4px 8px;
          background: #f8fafc;
          border: 1px solid #e2e6ee;
          /* Its height changes a little with the corner handle; the icons and title follow it */
          container-type: size;
          /* Icon size: the toolbar height minus the padding, but small enough to fit in one row */
          --icon: clamp(12px, min(100cqh - 12px, (100cqw - 230px) / 16), 60px);
          box-sizing: border-box;
          height: 42px;
          min-height: 34px;
          max-height: 50px;
          resize: vertical;
          overflow: auto;
        }
        strong { margin-right: 12px; font-size: max(12px, var(--icon) * 0.8); font-style: italic; color: var(--bg-color); }
        /* A narrow toolbar leaves the room of the title to the buttons */
        @container (width < 450px) { strong { display: none; } }
        button {
          padding: 6px;
          border: 0;
          border-radius: 6px;
          background: none;
          font: var(--icon)/1 Icons;
          color: #64748b;
          cursor: pointer;
        }
        button:hover { background: #e2e6ee; color: inherit; }
        /* Line that separates the groups of buttons */
        [data-action="undo"], [data-action="clear"], [data-action="fullscreen"] {
          margin-left: 9px;
          box-shadow: -6px 0 0 -5px #e2e6ee;
        }
        select { margin-left: auto; font: inherit; }
        /* Layout menu, the beforetoggle listener places it under its button */
        [popover] { inset: auto; margin: 0; padding: 4px; border: 1px solid #e2e6ee; border-radius: 6px; }
        [popover] button { display: block; width: 100%; font: inherit; text-align: left; }
        /* Hidden toolbar: only the toggle button stays, as a tab on top of the editor */
        :host(:state(hidden)) {
          justify-content: center;
          container-type: normal;
          height: auto !important; /* Ignores the height of the handle */
          min-height: 0;
          padding: 0;
          border: 0;
          background: none;
          resize: none;
          overflow: visible;
        }
        :host(:state(hidden)) > :not(.toggle) { display: none; }
        :host(:state(hidden)) .toggle {
          padding: 0 16px;
          font-size: 20px;
          border: 1px solid #e2e6ee;
          border-bottom: 0;
          border-radius: 6px 6px 0 0;
          background: #f8fafc;
        }
      </style>
      <strong>Your solution</strong>
      ${buttons.map(([action, title, icon]) => `<button type="button" data-action="${action}" title="${title}" aria-label="${title}">${icon}</button>`).join('')}
      <button type="button" popovertarget="layouts" title="Layout" aria-label="Layout">vertical_split</button>
      <div id="layouts" popover>
        <button type="button" data-layout="top">Statement on top</button>
        <button type="button" data-layout="left">Statement on the left</button>
        <button type="button" data-layout="right">Statement on the right</button>
      </div>
      <select aria-label="Programming language"></select>
      <button type="button" class="toggle"></button>`;
    const internals = this.attachInternals();
    internals.role = 'toolbar';
    internals.ariaLabel = 'Editor';
    this.shadowRoot.addEventListener('click', (event) => this.run(event.target.dataset.action));
    document.addEventListener('fullscreenchange', () => this.updateFullscreenButton());
    const menu = this.shadowRoot.querySelector('[popover]');
    menu.addEventListener('beforetoggle', () => {
      const { bottom, right } = menu.previousElementSibling.getBoundingClientRect();
      menu.style.top = `${bottom}px`;
      menu.style.right = `${document.documentElement.clientWidth - right}px`;
    });
    // The page CSS uses <html data-layout> to place the statement; the choice is remembered
    menu.addEventListener('click', (event) => {
      const { layout } = event.target.dataset;
      if (!layout) return;
      document.documentElement.dataset.layout = layout;
      window.localStorage.setItem('layout', layout);
      menu.hidePopover();
    });
    document.documentElement.dataset.layout = window.localStorage.getItem('layout') || 'top';
    // The last button hides the toolbar, leaving a tab to show it again; the choice is remembered
    const toggle = this.shadowRoot.querySelector('.toggle');
    const show = (shown) => {
      internals.states[shown ? 'delete' : 'add']('hidden');
      toggle.textContent = shown ? 'expand_less' : 'expand_more';
      toggle.title = shown ? 'Hide the toolbar' : 'Show the toolbar';
      toggle.ariaExpanded = shown;
      window.localStorage.setItem('toolbarShown', shown);
    };
    toggle.addEventListener('click', () => show(internals.states.has('hidden')));
    show(window.localStorage.getItem('toolbarShown') !== 'false');
  }

  // The language chosen by the student
  get language() {
    return this.shadowRoot.querySelector('select').value;
  }

  // Fills the language list with the problem languages, e.g. ['C', 'C++']
  set languages(languages) {
    this.shadowRoot.querySelector('select').innerHTML = languages.map((language) => `<option>${language}</option>`).join('');
  }

  async run(action) {
    const { editor } = this;
    if (!action || !editor) return;
    const selection = () => editor.getModel().getValueInRange(editor.getSelection());
    // Writes text in the range; it stays in the history, so Undo can revert it
    const write = (text, range = editor.getSelection()) => {
      editor.pushUndoStop();
      editor.executeEdits('toolbar', [{ range, text }]);
      editor.pushUndoStop();
    };
    const all = () => editor.getModel().getFullModelRange();
    const actions = {
      cut: async () => { await navigator.clipboard.writeText(selection()); write(''); },
      copy: () => navigator.clipboard.writeText(selection()),
      paste: async () => write(await navigator.clipboard.readText()),
      undo: () => editor.trigger('toolbar', 'undo'),
      redo: () => editor.trigger('toolbar', 'redo'),
      clear: () => window.confirm('Do you want to clear all the code?') && write('', all()),
      revert: () => window.confirm('Do you want to revert to the initial code?') && write(this.initialCode, all()),
      // Fullscreen for the parent, so the toolbar and the editor stay together
      fullscreen: () => (document.fullscreenElement
        ? document.exitFullscreen() : this.parentElement.requestFullscreen()),
    };
    try {
      await actions[action]();
    } catch {
      window.alert('The browser blocked the clipboard. Use Ctrl+X, Ctrl+C or Ctrl+V.');
    }
    editor.focus();
  }

  // Changes the icon and title of the fullscreen button when entering or leaving (also with Esc)
  updateFullscreenButton() {
    const button = this.shadowRoot.querySelector('[data-action="fullscreen"]');
    const full = Boolean(document.fullscreenElement);
    button.textContent = full ? 'fullscreen_exit' : 'fullscreen';
    button.title = full ? 'Exit fullscreen' : 'Fullscreen';
    button.ariaLabel = button.title;
  }
}

customElements.define('barra-herramientas', Toolbar);
