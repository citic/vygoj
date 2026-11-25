import * as monaco from 'https://esm.sh/monaco-editor';
import {
  ExecutionResult, MAIN_FILES, MAX_SOLUTION_BYTES, MAX_SOLUTION_FILES, Problem, SOLUTION_EXTENSIONS,
  SOLUTION_FILE_PATTERN, Status,
} from '../vyg.js';
import { CHECK_EVENT, STATUS_EVENT } from '../site.js';
import _ from '../i18n.js';
import '../components/monaco-editor.js';
import LanguageClient, { fileUri } from '../components/lang-client.js';
import '../components/editor-toolbar.js';
import '../components/tab-control.js';

// Milliseconds to wait for the answers of the server, so the page never waits forever. The time of
// a run depends on the limits of the judge, so the page gets it in data-run-timeout (seconds, see
// Limits.client_run_timeout() in limits.py). DEFAULT_RUN_TIMEOUT is used if it is missing
const FETCH_TIMEOUT = 30000;
const DEFAULT_RUN_TIMEOUT = 120000;
// HTTP statuses of the frontend or a proxy when the judge cannot be reached
const UNREACHABLE_STATUSES = [502, 503, 504];
// Side in pixels of the square of the corner handle of an element with CSS resize, about the size
// that browsers draw it
const RESIZE_HANDLE_SIZE = 16;
// A line of the compiler, the linker, or the linter about a line of a file of the solution, with
// its file, its line, its column or section of the linker, its severity, and its message. E.g.
// "tree.c:4:18: error: 'y' undeclared" (gcc), "/tmp/solution.c:3:(.text+0x5): undefined reference
// to `foo'" (ld), "solution.c:5:  Missing space after ,  [whitespace/comma] [3]" (cpplint),
// "Solution.java:7: error: ';' expected" (javac), or "solution.ale:3:1: syntax error: unexpected
// token 'end'" (alecci). The files of the solution are in /home/student, so lines about other
// folders (e.g. /usr/include/tree.h) are not diagnostics, even if a file of the solution has the
// same name. The linker may name a temporary copy in /tmp
const DIAGNOSTIC = /^(?:\/home\/student\/|\/tmp\/)?([\w-]+\.\w+):(\d+):(?:(\d+):|(\(\.[^)]*\)):)?\s*(?:(?:fatal |syntax )?(error|warning|note):)?\s*(.*)$/;
// A line of Python about a line of a file, e.g. '  File "tree.py", line 3' of a syntax error. Its
// message is in a later line that names the error, e.g. "SyntaxError: invalid syntax"
const PYTHON_DIAGNOSTIC = /^\s*File "(?:\/home\/student\/)?([\w-]+\.py)", line (\d+)/;
const PYTHON_ERROR = /^\w*(?:Error|Exception|Warning)\b/;
// An error of alecci with its line at the end, e.g. "solution.ale: error: undefined variable 'y'
// (line 2)"
const ALECCI_DIAGNOSTIC = /^(?:\/home\/student\/)?([\w-]+\.ale): (error|warning): (.*) \(line (\d+)\)$/;
// Extensions of the files of a solution with an icon in /img/files/<extension>.svg: the file
// icons of Visual Studio Code (vscode-icons, MIT license). Other extensions get file.svg. They are
// files of this site, because the CSP blocks images of other sites (see design/readme.adoc)
const FILE_ICONS = ['c', 'h', 'cpp', 'hpp', 'java', 'py'];

// Returns the extensions of the main file of a solution in the language (the one of its default
// name, e.g. c in solution.c), or of the other files
function fileExtensions(language, main) {
  return main ? [MAIN_FILES[language]?.split('.').pop()] : SOLUTION_EXTENSIONS[language] ?? [];
}

// True if the point is in the rectangle
function isOver(rect, x, y) {
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

// Returns the address of the icon of a file, by its extension
function fileIcon(name) {
  const extension = name.split('.').pop();
  return `/img/files/${FILE_ICONS.includes(extension) ? extension : 'file'}.svg`;
}

// An error that means that the server or the judge could not be reached, not that the request was
// wrong. The connection is checked again after it
class ConnectionError extends Error {}

// Monaco name of each programming language of VygOJ. vygoj.json may write a language by its
// name or by its extension (LANGUAGE_EXTENSIONS in vyg.py), so keys are in lowercase.
// TODO: Java and Kotlin are missing because esm.sh fails to serve their highlighting (error 520)

const monacoLanguageFor = {
  ale: 'alecci',
  alecci: 'alecci',
  c: 'c',
  'c++': 'cpp',
  cpp: 'cpp',
  javascript: 'javascript',
  js: 'javascript',
  python: 'python',
  py: 'python',
};

function loadConfig(key) {
  return window.localStorage.getItem(`${key}:${window.location.pathname}`);
}

function saveConfig(key, value) {
  window.localStorage.setItem(`${key}:${window.location.pathname}`, value);
}

// Returns the files of a solution in the language ({ name: code }) in JSON, or null if the text is
// not a solution: up to MAX_SOLUTION_FILES files, the main file first, with the extensions of the
// language. localStorage and the server are untrusted, and their values may be invalid or old
function parseFiles(text, language) {
  try {
    const files = JSON.parse(text);
    const entries = files && typeof files === 'object' ? Object.entries(files) : [];
    const valid = entries.length > 0 && entries.length <= MAX_SOLUTION_FILES
      && entries.every(([name, code], index) => typeof code === 'string'
        && fileExtensions(language, index === 0).includes(name.match(SOLUTION_FILE_PATTERN)?.[1]));
    return valid ? files : null;
  } catch {
    return null;
  }
}

// Writes each line of the text as a command line argument in single quotes, so the backend, which
// splits them as a shell would, gets each line whole. A single quote in a line closes the quotes,
// goes escaped, and opens them again: it's -> 'it'\''s'. Empty lines are skipped
function quoteLines(text) {
  return text.split(/\r?\n/).filter((line) => line)
    .map((line) => `'${line.replaceAll("'", "'\\''")}'`).join(' ');
}

// Show a number of bytes with a binary unit, e.g. 1536 as '1.5 KiB'
function formatBytes(bytes) {
  const units = ['B', 'KiB', 'MiB', 'GiB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return unit === 0 ? `${value} ${units[0]}` : `${value.toFixed(1)} ${units[unit]}`;
}

function hideElement(id) {
  const element = document.getElementById(id);
  console.assert(element);
  element.hidden = true;
}

function showElement(id) {
  const element = document.getElementById(id);
  console.assert(element);
  element.hidden = false;
}

class ProblemManager {
  // Singleton instance
  constructor() {
    // References to all editors used in the problem page
    this.editors = []; // monaco.editor.IStandaloneCodeEditor
    // The problem model fetched from server
    this.problem = null; // class Problem instance
    // Index of the current shown test case
    this.activeTestCaseIndex = 0;
    // The Run button element, null for anonymous visitors, who cannot run code
    this.runButton = null; // HTMLButtonElement
    // The result after running the user code
    this.result = null; // class ExecutionResult instance
    // True while a run is waiting for its result
    this.running = false; // boolean
    // False while the connection with the frontend or the backend is lost
    this.online = true; // boolean
    // False while the code editor shows code that is already stored (when loading it, or when
    // another tab changed it), so the change is not saved again. Saving it again made tabs of the
    // same problem send each other old versions of the code forever
    this.savesCode = true;
    // The files of the solution in the chosen language, by name in the order of their tabs, the
    // main file first. Each Monaco model keeps the code, Undo history, and diagnostics of a file
    this.files = new Map(); // Map of string to monaco.editor.ITextModel
    // Cursor and scroll of each file while the editor shows another one, by name
    this.viewStates = new Map(); // Map of string to monaco.editor.ICodeEditorViewState
    // Cursor and scroll of the files of each window while it shows another one, by model
    this.sideViewStates = new WeakMap(); // WeakMap of HTMLElement to WeakMap
    // Windows made so far, which numbers the id of the editor of each one
    this.sideCount = 0; // number
    // Ends the open field of the name of a file, if any, as when it loses the focus
    this.finishFileName = null; // function
    // Versions of the solution that the runs of the user saved in the chosen language, from the
    // oldest to the newest, as [commit, time in seconds] pairs, for the slider of the toolbar
    this.versions = []; // Array
    // Files of the versions already fetched, by language and commit, which never change
    this.versionFiles = new Map(); // Map of string to Object
    // Files of the solution while the slider shows a version, shown again at the end of the
    // slider. Null while the editor shows them
    this.currentFiles = null; // Object
    // Suggestions of the language server for the chosen language, null if it has none
    this.languageClient = null; // LanguageClient
  }

  static main() {
    const instance = new ProblemManager();
    instance.setup();
  }

  // TODO: Problem statement may have source code snippets, highlight them using a client library
  // such as highlight.js or prismjs
  async setup() {
    try {
      this.setupReferences();
      this.openStatementLinksInNewTab();
      ProblemManager.setupLayoutMenu();
      this.setupCodeEditor();
      this.setupTestCaseEditors();
      await this.fetchProblem();
      this.loadUserCode();
      this.setupVersions();
      this.loadTestCases();
      this.setupRunEnvironment();
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : String(error);
      this.updateCompileOutput(message);
    }
  }

  setupReferences() {
    // Anonymous visitors get a link to log in instead of the Run button
    this.runButton = document.getElementById('run_button');
  }

  // Open the statement links in a new tab, so students do not leave their solution.
  // Links to sections of the statement itself (#id) stay in this tab. The opened page must not
  // get a reference to this tab (window.opener), or it could navigate it to a fake login page
  // eslint-disable-next-line class-methods-use-this
  openStatementLinksInNewTab() {
    const links = document.querySelectorAll('.statement a[href]:not([href^="#"])');
    links.forEach((link) => {
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');
    });
  }

  // The layout chosen in the toolbar menu and the size given to the statement with its corner
  // handle are remembered for each problem. Each layout has its own statement size
  static setupLayoutMenu() {
    const menu = document.getElementById('layouts');
    const statement = document.querySelector('.problem > .description');
    const sizeKey = () => `size:${menu.elements.layout.value}`;
    // CSS resize writes the size in the style attribute. Only the width and height are kept, and
    // the browser ignores them if localStorage has invalid values
    const restoreSize = () => {
      const [width = '', height = ''] = (loadConfig(sizeKey()) || '').split(';');
      Object.assign(statement.style, { width, height });
    };
    menu.elements.layout.value = loadConfig('layout') || 'top';
    restoreSize();
    menu.addEventListener('change', () => {
      saveConfig('layout', menu.elements.layout.value);
      restoreSize();
    });
    new ResizeObserver(() => saveConfig(sizeKey(), `${statement.style.width};${statement.style.height}`))
      .observe(statement);
    // Double clicking the corner handle gives the statement back the size of its layout, the one
    // it has the first time the page is loaded. Browsers send no events of the handle itself, so
    // the double click is taken on the statement, inside the square of the handle
    statement.addEventListener('dblclick', (event) => {
      if (ProblemManager.isOnResizeHandle(statement, event)) {
        Object.assign(statement.style, { width: '', height: '' });
        saveConfig(sizeKey(), ';');
      }
    });
  }

  // True if the mouse event happened on the corner handle of the given element with CSS resize:
  // the bottom right corner, or the bottom left one when its direction is right to left
  static isOnResizeHandle(element, { clientX, clientY }) {
    const { left, right, bottom } = element.getBoundingClientRect();
    const rightToLeft = window.getComputedStyle(element).direction === 'rtl';
    const fromSide = rightToLeft ? clientX - left : right - clientX;
    const fromBottom = bottom - clientY;
    return [fromSide, fromBottom].every((distance) => distance >= 0
      && distance <= RESIZE_HANDLE_SIZE);
  }

  setupCodeEditor() {
    const codeEditor = document.getElementById('code_editor');
    const { editor } = codeEditor;
    // The language chosen in the list of the toolbar is remembered for each problem, and the
    // highlighting follows it. A problem without a language of its own starts with the last one
    // the user chose in any problem, if it offers it. Languages that the problem does not offer
    // (or invalid ones in localStorage) leave the value empty, and the next choice is tried
    const languageList = document.getElementById('language');
    languageList.value = loadConfig('language');
    if (languageList.selectedIndex < 0) {
      languageList.value = window.localStorage.getItem('language');
    }
    if (languageList.selectedIndex < 0) {
      languageList.selectedIndex = 0;
    }
    // Only a choice of the user becomes the last language, not the one a problem starts with
    languageList.addEventListener('change', () => {
      window.localStorage.setItem('language', languageList.value);
    });
    this.editors.push(editor);
    // The editor is as tall as its code (--fitted-height, between the min-height and max-height of
    // the CSS), until the user gives it another height with its corner handle, and in a split it
    // shares the height of the split. It keeps its height while the slider shows versions, so the
    // page does not jump with each one
    editor.onDidContentSizeChange(() => this.fitHeight());
    // Another tab of this problem saved its files for the chosen language: show them here too.
    // Events arrive late, so an event whose files are not the stored ones anymore is old, and it
    // is ignored. The files keep the Undo history of this tab (see showFiles())
    window.addEventListener('storage', (event) => {
      if (event.key !== `files:${languageList.value}:${window.location.pathname}`) {
        return;
      }
      // A name that the student is writing ends first, as when its field loses the focus. If it
      // makes a file, the files of this tab are newer, and they go to the other tab instead
      this.finishFileName?.('blur');
      const files = parseFiles(event.newValue, languageList.value);
      if (files && event.newValue === window.localStorage.getItem(event.key)
        && event.newValue !== JSON.stringify(this.getFiles())) {
        this.showStoredCode(() => this.showFiles(files));
      }
    });
    // Clicking a line of the diagnostics about a line of the code goes to its file and its code
    document.getElementById('diagnostics').addEventListener('click', ({ target }) => {
      const { index, file } = target.closest('button')?.dataset ?? {};
      if (index) {
        this.selectFile(file);
        codeEditor.goToDiagnostic(Number(index));
      }
    });
    this.setupFileTabs();
  }

  // The language chosen in the list of the row of the files
  static language() {
    return document.getElementById('language').value;
  }

  // The tabs of the files of the solution. Selecting a tab shows its file in the editor, the +
  // button adds a file, and double clicking a tab or F2 renames its file, and its cross or Delete
  // closes it, except the main file
  setupFileTabs() {
    const tabControl = document.querySelector('.solution > tab-control');
    // The change events of the field of a name and of the list of languages also reach it
    tabControl.addEventListener('change', ({ target, detail }) => target === tabControl
      && this.selectFile([...this.files.keys()][detail]));
    const list = tabControl.querySelector('[role="tablist"]');
    const fileOf = (target) => target.closest('[role="tab"]')?.dataset.file;
    // In the capture phase, before the tab control selects the tab of the cross
    list.addEventListener('click', (event) => {
      if (event.target.closest('.close')) {
        event.stopPropagation();
        this.closeFile(fileOf(event.target));
      }
    }, true);
    list.addEventListener('dblclick', ({ target }) => this.renameFile(fileOf(target)));
    list.addEventListener('keydown', (event) => {
      if (event.key === 'F2') {
        this.renameFile(fileOf(event.target));
      } else if (event.key === 'Delete') {
        this.closeFile(fileOf(event.target));
      }
    });
    document.getElementById('add_file').addEventListener('click', () => this.editFileName());
    this.setupSides(list, fileOf);
  }

  // A tab dragged out of a row of tabs, of the code editor or of a window, becomes a window over
  // the page with its file selected, and with the tabs of all the files, as the code editor and
  // every window, so the student pulls out the files as many times as wanted. Ctrl+\ in a tab does
  // the same, with the new window at the right of the pane of the tab. Dragging the empty part of
  // the row of the tabs of a window moves it, and its cross closes it. As the groups of editors of
  // Visual Studio Code, dropping a window on the tabs of the code editor or of another window shows
  // its file there and closes it, and dropping it on a side of a pane (the code editor or a window
  // at its side) splits the pane, as many times as the student wants. The editors share the model
  // of each file, so the code, Undo history, and diagnostics are the same in all of them
  setupSides(list, fileOf) {
    const panes = document.querySelector('.solution .panes');
    const code = document.getElementById('code_editor');
    // Where the window would go with the pointer there: in the tabs of the code editor or of
    // another window ('tabs'), or at the nearest side of a pane under the pointer when it is on its
    // outer third, as in Visual Studio Code. Null elsewhere, so the window floats
    const zone = (side, { clientX, clientY }) => {
      const others = [...panes.querySelectorAll('.side')].filter((other) => other !== side);
      const tabs = [list, ...others].find((element) => isOver((element === list ? list
        : element.querySelector('[role="tablist"]')).getBoundingClientRect(), clientX, clientY));
      if (tabs) {
        return [tabs, 'tabs'];
      }
      const pane = [code, ...others.filter((other) => !other.hasAttribute('data-floating'))]
        .find((element) => isOver(element.getBoundingClientRect(), clientX, clientY));
      const box = pane?.getBoundingClientRect();
      const distances = box && Object.entries({
        left: (clientX - box.left) / box.width,
        right: (box.right - clientX) / box.width,
        top: (clientY - box.top) / box.height,
        bottom: (box.bottom - clientY) / box.height,
      }).sort(([, first], [, second]) => first - second);
      return distances?.[0][1] < 1 / 3 ? [pane, distances[0][0]] : null;
    };
    // Moves the window that sideAt returns for each move (null while there is none yet) with the
    // pointer, which holds the point (dx, dy) of its row of tabs, or the middle of the row without
    // dx, anywhere in the page, and the place of the pane where it would go is tinted (data-drop)
    const drag = (down, sideAt, dx, dy) => {
      let side = null;
      let drop = null;
      ProblemManager.dragPointer(down, (event) => {
        side ??= sideAt(event);
        if (!side) {
          return;
        }
        if (!side.hasAttribute('data-floating')) {
          ProblemManager.floatSide(side);
        }
        const origin = side.offsetParent.getBoundingClientRect();
        side.style.setProperty('--left', `${event.clientX - origin.left - (dx ?? side.offsetWidth / 2)}px`);
        side.style.setProperty('--top', `${event.clientY - origin.top - dy}px`);
        drop?.[0].removeAttribute('data-drop');
        drop = zone(side, event);
        if (drop) {
          const [pane, where] = drop;
          pane.dataset.drop = where;
        }
      }, (released) => {
        drop?.[0].removeAttribute('data-drop');
        if (released && drop?.[1] === 'tabs') {
          this.joinSide(side, drop[0] === list ? null : drop[0]);
        } else if (released && drop) {
          ProblemManager.dockSide(side, ...drop);
        }
      });
    };
    // A tab dragged out of its row, above or below it, shows its file in a new window. A finger on
    // the tabs scrolls the page, so only a mouse or a pen drags them
    const dragTab = (down, row) => {
      const name = fileOf(down.target);
      drag(down, ({ clientY }) => {
        const { top, bottom } = row.getBoundingClientRect();
        return clientY >= top && clientY <= bottom ? null : this.newSide(name);
      }, null, 12);
    };
    list.addEventListener('pointerdown', (down) => {
      if (fileOf(down.target) && !down.target.closest('.close') && down.pointerType !== 'touch') {
        dragTab(down, list);
      }
    });
    // In a window, a tab with others in its row leaves it, and the row of the tabs moves the window
    panes.addEventListener('pointerdown', (down) => {
      const row = down.target.closest('.side > [role="tablist"]');
      if (row && fileOf(down.target) && row.children.length > 1 && down.pointerType !== 'touch') {
        dragTab(down, row);
      } else if (row) {
        const side = row.parentElement;
        const { left, top } = side.getBoundingClientRect();
        drag(down, () => side, down.clientX - left, down.clientY - top);
      }
    });
    list.closest('tab-control').addEventListener('keydown', ({ ctrlKey, key, target }) => {
      const name = fileOf(target);
      if (name && ctrlKey && key === '\\') {
        ProblemManager.dockSide(this.newSide(name), target.closest('.side:not([data-floating])') ?? code, 'right');
      }
    });
    panes.addEventListener('click', ({ target }) => {
      if (target.closest('.side > .close_window')) {
        ProblemManager.closeSide(target.closest('.side'));
        this.editors[0].focus();
      }
    });
  }

  // Follows the drag of the pointer that went down with the main button, with pointer events, which
  // work alike with a mouse, a pen, or a finger, and in every browser (the drag and drop of HTML
  // did not drop in Firefox), in the capture phase, before Monaco. Each move after the first
  // pixels calls move with its event, and the end calls end, with true if the pointer was released
  static dragPointer(down, move, end) {
    if (down.button !== 0) {
      return;
    }
    const drag = new AbortController();
    let moved = false;
    document.addEventListener('pointermove', (event) => {
      moved ||= Math.hypot(event.clientX - down.clientX, event.clientY - down.clientY) > 4;
      if (moved) {
        move(event);
      }
    }, { signal: drag.signal, capture: true });
    ['pointerup', 'pointercancel'].forEach((type) => document.addEventListener(type, () => {
      drag.abort();
      if (moved) {
        end(type === 'pointerup');
      }
    }, { signal: drag.signal, capture: true }));
  }

  // Returns a new window over the page with the tabs of all the files, and the given one selected
  // (data-file), which its tab control changes with a change event
  newSide(name) {
    const side = document.importNode(document.getElementById('side_window').content.firstElementChild, true);
    this.sideCount += 1;
    side.querySelector('monaco-editor').id = `side_editor_${this.sideCount}`;
    side.dataset.file = name;
    side.dataset.floating = '';
    side.addEventListener('change', ({ target, detail }) => {
      if (target === side) {
        side.dataset.file = [...this.files.keys()][detail];
        this.showSide(side);
      }
    });
    document.querySelector('.solution .panes').append(side);
    this.showSide(side);
    return side;
  }

  // Shows the file of the window in the other window, or in the code editor without one, and
  // closes the window
  joinSide(side, other) {
    if (other) {
      other.dataset.file = side.dataset.file;
      this.showSide(other);
    } else {
      this.selectFile(side.dataset.file);
    }
    ProblemManager.closeSide(side);
  }

  // The windows that show the file show it with its new name. Names of files are letters, digits,
  // _, -, and dots, so they fit in the selector
  static renameInSides(name, newName) {
    document.querySelectorAll(`.solution .side[data-file="${name}"]`)
      .forEach((side) => { side.dataset.file = newName; });
  }

  // Takes the window out of its split, to the end of the panes, and a split with one pane left
  // becomes that pane
  static leaveSplit(side) {
    const split = side.parentElement;
    side.closest('.panes').append(side);
    if (split.matches('.split') && split.children.length === 1) {
      split.replaceWith(split.firstElementChild);
    }
  }

  // Makes the window float over the page where it is, positioned in the page
  static floatSide(side) {
    const box = side.getBoundingClientRect();
    ProblemManager.leaveSplit(side);
    side.dataset.floating = '';
    const origin = side.offsetParent.getBoundingClientRect();
    side.style.setProperty('--left', `${box.left - origin.left}px`);
    side.style.setProperty('--top', `${box.top - origin.top}px`);
  }

  // Docks the floating window at the side ('left', 'right', 'top', or 'bottom') of the pane, in
  // the split of the pane if it goes in that direction, or in a new split in its place. The code
  // editor in a split shares its height, not the one of its corner handle
  static dockSide(side, pane, where) {
    const direction = where === 'left' || where === 'right' ? 'row' : 'column';
    let split = pane.parentElement;
    delete side.dataset.floating;
    side.removeAttribute('style');
    pane.style.removeProperty('height');
    if (!split.matches(`.split[data-direction="${direction}"]`)) {
      split = document.createElement('div');
      split.className = 'split';
      split.dataset.direction = direction;
      pane.replaceWith(split);
      split.append(pane);
    }
    if (where === 'left' || where === 'top') {
      pane.before(side);
    } else {
      pane.after(side);
    }
  }

  // Removes the window, and its editor, but not the model of its file
  static closeSide(side) {
    if (side) {
      ProblemManager.leaveSplit(side);
      side.querySelector('monaco-editor').editor.dispose();
      side.remove();
    }
  }

  // Shows the tabs of each window and its selected file
  showSides() {
    document.querySelectorAll('.solution .side').forEach((side) => this.showSide(side));
  }

  // Shows a tab for each file of the solution, and the file of the window, or the main file if the
  // solution does not have it (e.g. in a version of the slider or in another language), in its
  // editor, with its cursor and scroll there
  showSide(side) {
    const names = [...this.files.keys()];
    const { editor } = side.querySelector('monaco-editor');
    if (!names.includes(side.dataset.file)) {
      [side.dataset.file] = names;
    }
    side.querySelector('[role="tablist"]')
      .replaceChildren(...names.map((name) => ProblemManager.fileTab(name, false, false)));
    side.update();
    const model = this.files.get(side.dataset.file);
    if (model !== editor.getModel()) {
      const views = this.sideViewStates.get(side) ?? new WeakMap();
      this.sideViewStates.set(side, views);
      if (editor.getModel()) {
        views.set(editor.getModel(), editor.saveViewState());
      }
      editor.setModel(model);
      editor.restoreViewState(views.get(model) ?? null);
    }
    side.selectedIndex = names.indexOf(side.dataset.file);
    editor.updateOptions({ ariaLabel: side.dataset.file });
  }

  // The files of the solution as { name: code }, the main file first
  getFiles() {
    return Object.fromEntries([...this.files].map(([name, model]) => [name, model.getValue()]));
  }

  // Saves the files of the solution in this browser. Changing them makes them the current files
  // at the end of the slider of the versions
  saveFiles() {
    saveConfig(`files:${ProblemManager.language()}`, JSON.stringify(this.getFiles()));
    const slider = document.getElementById('version');
    if (slider && this.currentFiles !== null) {
      this.currentFiles = null;
      slider.value = slider.max;
      this.updateVersionName();
      this.fitHeight();
    }
  }

  // Makes the code editor as tall as its code, unless the slider shows a version
  fitHeight() {
    if (this.currentFiles === null) {
      const height = this.editors[0].getContentHeight();
      document.getElementById('code_editor').style.setProperty('--fitted-height', `${height}px`);
    }
  }

  // Name of the main file of the solution, its first one, which the student may rename
  mainFile() {
    return this.files.keys().next().value;
  }

  // Name of the file in the editor
  selectedFile() {
    const model = this.editors[0].getModel();
    return [...this.files].find(([, file]) => file === model)?.[0];
  }

  // Shows the file in the editor with its cursor and scroll, or the main file if there is no file
  // of that name, and selects its tab
  selectFile(name) {
    const editor = this.editors[0];
    const model = this.files.get(name) ?? this.files.values().next().value;
    if (model !== editor.getModel()) {
      const selected = this.selectedFile();
      if (selected) {
        this.viewStates.set(selected, editor.saveViewState());
      }
      editor.setModel(model);
      editor.restoreViewState(this.viewStates.get(name) ?? null);
    }
    document.querySelector('.solution > tab-control').selectedIndex = [...this.files.values()].indexOf(model);
  }

  // Shows the files ({ name: code }) in their tabs, the main file first. Files of the same name
  // keep their model, so the change is a step of their Undo history, and the others are created
  // or removed. The code of backups ({ name: code }) goes first in the history of a new file, so
  // Undo brings it back
  showFiles(files, backups = {}) {
    const selected = this.selectedFile();
    const old = this.files;
    const language = monacoLanguageFor[ProblemManager.language().toLowerCase()] || 'plaintext';
    const write = (model, text) => {
      if (model.getValue() !== text) {
        model.pushStackElement();
        model.pushEditOperations([], [{ range: model.getFullModelRange(), text }], () => null);
        model.pushStackElement();
      }
    };
    this.files = new Map(Object.entries(files).map(([name, code]) => {
      let model = old.get(name);
      if (!model) {
        model = monaco.editor.createModel(backups[name] ?? code, language, fileUri(name));
        model.updateOptions({ tabSize: 2 }); // Google code style
        // The student edits the file in any of the editors
        model.onDidChangeContent(() => {
          document.getElementById('code_editor').moveDiagnostics(model);
          if (this.savesCode) {
            this.saveFiles();
          }
          this.updateRunButton();
        });
      }
      write(model, code);
      return [name, model];
    }));
    this.showTabs();
    this.selectFile(selected);
    this.showSides();
    old.forEach((model, name) => !this.files.has(name) && model.dispose());
    // The cursors of the files that are gone are not needed anymore
    [...this.viewStates.keys()].filter((name) => !this.files.has(name))
      .forEach((name) => this.viewStates.delete(name));
    this.updateRunButton();
  }

  // Makes a tab for each file, and the + button is disabled when the solution has the most files,
  // or the language takes one file
  showTabs() {
    const main = this.mainFile();
    const tabs = [...this.files.keys()]
      .map((name) => ProblemManager.fileTab(name, name !== main, true));
    const tabControl = document.querySelector('.solution > tab-control');
    tabControl.querySelector('[role="tablist"]').replaceChildren(...tabs);
    tabControl.update();
    document.getElementById('add_file').disabled = this.files.size >= MAX_SOLUTION_FILES
      || !SOLUTION_EXTENSIONS[ProblemManager.language()]?.length;
  }

  // Returns the tab of a file: the icon of its language, its name, and a cross that closes it if it
  // is closable (not the main file in the tabs of the code editor), with a title that says what the
  // mouse and the keys do, and if it can be renamed (in the tabs of the code editor)
  static fileTab(name, closable, renamable) {
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.dataset.file = name;
    const icon = document.createElement('img');
    icon.src = fileIcon(name);
    icon.alt = '';
    // A dragged image would be dragged by the browser, not as the tab
    icon.draggable = false;
    // A long name is cut with an ellipsis, and the title shows it whole
    const label = document.createElement('span');
    label.className = 'file';
    label.textContent = name;
    tab.append(icon, label);
    // pybabel does not read _() in template literals
    const lines = [name, _('Drag it to see it in a window, or press %(keys)s to see it at the side', { keys: 'Ctrl+\\' })];
    if (renamable) {
      lines.push(closable ? _('Double click or F2 renames it, Delete closes it') : _('Double click or F2 renames it'));
    }
    if (closable) {
      const close = document.createElement('span');
      close.className = 'close material-symbols-outlined';
      close.ariaHidden = 'true';
      close.title = _('Close');
      close.textContent = 'close';
      tab.append(close);
    }
    tab.title = lines.join('\n');
    tab.setAttribute('aria-keyshortcuts', [renamable && 'F2', closable && 'Delete', 'Control+\\']
      .filter((key) => key).join(' '));
    return tab;
  }

  // Returns why the name is not valid for a new file of the solution, or for the new name of the
  // file current, or an empty text. The main file keeps the extension of the language. Names that
  // differ only in case are the same file in Windows
  fileNameError(name, current = null) {
    const extensions = fileExtensions(ProblemManager.language(), current === this.mainFile());
    const match = name.match(SOLUTION_FILE_PATTERN);
    if (!match || !extensions.includes(match[1])) {
      const list = extensions.map((extension) => `.${extension}`).join(' ');
      return _('Letters, digits, _ or - (not first), and one of the extensions %(extensions)s', { extensions: list });
    }
    const taken = [...this.files.keys()]
      .some((file) => file !== current && file.toLowerCase() === name.toLowerCase());
    return taken ? _('There is a file named %(file)s already', { file: name }) : '';
  }

  // Writes the name of a file in a field in the row of the tabs, as in Visual Studio Code: of a
  // new file at the end, or of the file of the given name in its tab. Enter keeps a valid name,
  // and shows why an invalid one is not valid. Escape, or leaving the field with an empty or
  // invalid name, cancels: a new file without a name is not created
  editFileName(name = null) {
    // One field at a time: the open one ends first
    this.finishFileName?.('blur');
    const list = document.querySelector('.solution > tab-control [role="tablist"]');
    const field = document.createElement('input');
    field.className = 'file_name';
    field.ariaLabel = name ? _('New name of %(file)s', { file: name }) : _('Name of the new file');
    field.value = name ?? '';
    field.spellcheck = false;
    const tab = name && [...list.children].find((element) => element.dataset.file === name);
    if (tab) {
      tab.replaceWith(field);
    } else {
      list.append(field);
    }
    field.focus();
    // As Visual Studio Code, the name is selected without its extension
    field.setSelectionRange(0, name ? name.lastIndexOf('.') : 0);
    let done = false;
    const finish = (keep) => {
      if (done) {
        return;
      }
      const newName = field.value.trim();
      const error = keep && newName && newName !== name ? this.fileNameError(newName, name) : '';
      if (error && keep === 'enter') {
        field.setCustomValidity(error);
        field.reportValidity();
        return;
      }
      done = true;
      this.finishFileName = null;
      if (keep && newName && newName !== name && !error) {
        // The files keep their order, with the new name in the place of the old one
        if (name) {
          ProblemManager.renameInSides(name, newName);
        }
        const files = name ? Object.fromEntries(Object.entries(this.getFiles())
          .map(([key, code]) => [key === name ? newName : key, code])) : { ...this.getFiles(), [newName]: '' };
        this.showFiles(files);
        this.selectFile(newName);
        this.saveFiles();
        this.editors[0].focus();
      } else {
        // Only the tab of the field comes back, so the rest of the row stays as it is
        if (tab) {
          field.replaceWith(tab);
        } else {
          field.remove();
        }
        // Escape or Enter give the focus back to the tabs, so the keyboard goes on there
        if (keep !== 'blur') {
          (tab || list.querySelector('[aria-selected="true"]'))?.focus();
        }
      }
    };
    this.finishFileName = finish;
    // The keys stay in the field: the arrows of the tab control and Delete do not reach the tabs
    field.addEventListener('keydown', (event) => {
      event.stopPropagation();
      if (event.key === 'Enter' || event.key === 'Escape') {
        event.preventDefault();
        finish(event.key === 'Enter' && 'enter');
      }
    });
    field.addEventListener('input', () => field.setCustomValidity(''));
    // After the click that took the focus, e.g. on another tab, so the click reaches its tab
    field.addEventListener('blur', () => setTimeout(() => finish('blur')));
  }

  // Edits the name of the file in its tab, also of the main file, which stays the first one
  renameFile(name) {
    if (this.files.has(name)) {
      this.editFileName(name);
    }
  }

  // Removes the file, after asking if it has code
  closeFile(name) {
    if (!this.files.has(name) || name === this.mainFile()) {
      return;
    }
    const question = _('Do you want to close %(file)s? Its code will be deleted.', { file: name });
    // The native dialogs of the browser are enough for a simple confirmation
    // eslint-disable-next-line no-alert
    if (this.files.get(name).getValue().trim() && !window.confirm(question)) {
      return;
    }
    const files = this.getFiles();
    delete files[name];
    this.showFiles(files);
    this.saveFiles();
    // The tab of the closed file had the focus
    document.querySelector('.solution > tab-control [aria-selected="true"]').focus();
  }

  // Run the given function, that shows code already stored in the code editor, without saving it
  showStoredCode(show) {
    this.savesCode = false;
    try {
      show();
    } finally {
      this.savesCode = true;
    }
  }

  setupTestCaseEditors() {
    this.setupTestCaseEditor('active_test_input');
    this.setupTestCaseEditor('active_test_expected_output');
    this.setupTestCaseEditor('active_test_user_output');
    this.setupTestCaseEditor('active_test_expected_error');
    this.setupTestCaseEditor('active_test_user_error');
    // The diffs show spaces and tabs as the editors do. They also show the spaces at the start or
    // end of a line, that Monaco ignores by default, because the backend compares them
    document.querySelectorAll('.test_editors [diff]').forEach(({ editor }) => {
      editor.updateOptions({ renderWhitespace: 'all', ignoreTrimWhitespace: false });
    });
    document.getElementById('args').editor.updateOptions({ renderWhitespace: 'all' });
    ProblemManager.resizeTestCaseEditorsTogether();
    this.setupTestToolbar();
  }

  // Side by side, stretching one of these editors with its corner handle stretches the others of
  // its row too, so the row stays aligned. One below the other, each one keeps its own height
  static resizeTestCaseEditorsTogether() {
    const editors = document.querySelectorAll('#active_test monaco-editor');
    const observer = new ResizeObserver(([{ target }]) => {
      const { top } = target.getBoundingClientRect();
      editors.forEach((editor) => {
        if (editor.getBoundingClientRect().top === top) {
          editor.style.height = target.style.height;
        }
      });
    });
    editors.forEach((editor) => observer.observe(editor));
  }

  // The buttons of the toolbar of the test cases show or hide each part of the selected test
  // case, and turn the diff and the word wrap on or off. They stay as the user leaves them, in all
  // the problems
  setupTestToolbar() {
    // Problems without test cases (no tabs) need other parts, e.g. the arguments, so the browser
    // keeps their buttons apart
    const toolbar = document.querySelector('.test_cases [role="tablist"]') ? 'test_toolbar' : 'input_toolbar';
    document.querySelectorAll('.test_toolbar button').forEach((button) => {
      const key = `${toolbar}:${button.dataset.part}`;
      button.ariaPressed = window.localStorage.getItem(key) ?? button.ariaPressed;
      button.addEventListener('click', () => {
        button.ariaPressed = String(button.ariaPressed !== 'true');
        window.localStorage.setItem(key, button.ariaPressed);
        this.showParts();
      });
    });
    this.showParts();
    // The test cases fold away as the user leaves them, in all the problems
    const details = document.querySelector('details.test_cases');
    details.open = window.localStorage.getItem('test_cases') !== 'false';
    details.addEventListener('toggle', () => {
      window.localStorage.setItem('test_cases', details.open);
      // Closed, the list of tabs could not scroll to the selected one
      if (details.open && this.problem?.tests.length > 0) {
        details.querySelector('tab-control').selectedIndex = this.activeTestCaseIndex;
      }
    });
  }

  // Shows the parts of the test case at the index that the toolbar asks for. With the diff on,
  // after a run, a diff takes the place of the expected and the user outputs if any of them is
  // shown, and another one of the errors
  showParts(index = this.activeTestCaseIndex) {
    // Problems without test cases have no buttons of the expected parts nor of the diff
    const on = (part) => document.querySelector(`.test_toolbar [data-part="${part}"]`)?.ariaPressed === 'true';
    const diff = on('diff') && Boolean(this.result?.results[index]);
    document.getElementById('active_test_args_wrapper').hidden = !on('args');
    document.getElementById('active_test_input_wrapper').hidden = !on('input');
    document.querySelector('.test_editors .input').hidden = !on('args') && !on('input');
    ['output', 'error'].forEach((kind) => {
      const [expected, user] = [on(`expected_${kind}`), on(`user_${kind}`)];
      const combined = diff && (expected || user);
      document.querySelector(`.test_editors .${kind}`).hidden = !expected && !user;
      document.getElementById(`active_test_expected_${kind}_wrapper`).hidden = !expected || combined;
      document.getElementById(`active_test_user_${kind}_wrapper`).hidden = !user || combined;
      document.getElementById(`${kind}_diff_wrapper`).hidden = !combined;
    });
    const wordWrap = on('word_wrap') ? 'on' : 'off';
    const diffs = [...document.querySelectorAll('.test_editors [diff]')].map(({ editor }) => editor);
    const { editor: args } = document.getElementById('args');
    [...this.editors.slice(1), args, ...diffs]
      .forEach((editor) => editor.updateOptions({ wordWrap }));
  }

  setupTestCaseEditor(id) {
    const { editor } = document.getElementById(id);
    editor.updateOptions({ renderWhitespace: 'all' });
    this.editors.push(editor);
  }

  async fetchProblem() {
    console.assert(this.problem === null);
    const message = { action: 'fetch_problem' }; // Message object
    try {
      this.problem = new Problem(await ProblemManager.sendJson(message, FETCH_TIMEOUT));
    } catch (error) {
      throw Error(`could not load the problem: ${error.message}`);
    }
  }

  // Post the object as JSON and return the JSON answer. The server answers errors with a JSON
  // object such as {error: '...'}, but proxies may answer with HTML pages, so both are thrown.
  // A request without answer after timeout milliseconds is aborted. Failed connections, timeouts,
  // and unreachable judges are thrown as ConnectionError
  static async sendJson(object, timeout, uri = '') {
    const params = ProblemManager.createMessage(object);
    params.signal = AbortSignal.timeout(timeout);
    let response = null;
    let json = null;
    try {
      response = await fetch(uri || window.location.href, params);
      json = await response.json().catch(() => null);
    } catch (error) {
      if (error.name === 'TimeoutError') {
        const seconds = timeout / 1000;
        throw new ConnectionError(_('the server did not answer in %(seconds)s seconds', { seconds }));
      }
      // fetch() rejects with a TypeError when the network or the server is down
      const { message } = error;
      throw new ConnectionError(_('could not connect to the server (%(message)s)', { message }));
    }
    if (!response.ok || !json || json.error) {
      const { status, statusText: text } = response;
      const message = json?.error || _('the server answered %(status)s %(text)s', { status, text });
      throw UNREACHABLE_STATUSES.includes(response.status)
        ? new ConnectionError(message) : new Error(message);
    }
    return json;
  }

  // TODO(jhc): Uniform with Message() object
  static createMessage(object, method = 'POST') {
    return {
      method,
      // The server rejects POST requests without the CSRF token of the session, so other sites
      // cannot run code or change grades on behalf of the student
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.getElementById('problem')?.dataset.csrfToken || '',
      },
      body: JSON.stringify(object),
    };
  }

  /// Return the milliseconds to wait for the answer of a run, from the data-run-timeout seconds
  static getRunTimeout() {
    const seconds = Number(document.getElementById('problem')?.dataset.runTimeout);
    return Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : DEFAULT_RUN_TIMEOUT;
  }

  /// Return the name of the problem from the loaded web page in browser
  static getName() {
    // Find DOM object <main id="problem" data-name="problem_name">
    const mainElement = document.getElementById('problem');
    // Return the value of data-name attribute
    return mainElement?.dataset.name;
  }

  loadTestCases() {
    console.assert(this.problem);
    // Each test case is a tab, and selecting one shows its parts in the box below the tabs
    const tabControl = document.querySelector('.test_cases tab-control');
    const { length } = tabControl.tabs;
    console.assert(length === this.problem.tests.length);
    tabControl.addEventListener('change', ({ detail: index }) => this.showTestCase(index));
    // Make the last selected test case (in local storage) as the active one. localStorage can
    // be edited by anyone, and problems may have fewer test cases now, so check the index
    if (length > 0) {
      const index = parseInt(loadConfig('test') || '0', 10);
      this.activeTestCaseIndex = index >= 0 && index < length ? index : 0;
      this.showTestCase(this.activeTestCaseIndex);
    } else {
      // Without test cases, the arguments and the input of the user are kept as the code is
      const { editor: args } = document.getElementById('args');
      [['args', args], ['stdin', this.editors[1]]].forEach(([key, editor]) => {
        editor.setValue(loadConfig(key) || '');
        editor.onDidChangeModelContent(() => saveConfig(key, editor.getValue()));
      });
    }
  }

  showTestCase(index) {
    console.assert(this.problem);
    console.assert(this.editors.length === 6);
    // Show the arguments, input, expected output, and expected error for this test case. The
    // server does not send the contents of hidden test cases
    const test = this.problem.tests[index];
    const hidden = test.hidden ? '(hidden test case)' : '';
    document.getElementById('args').editor.setValue(test.args || hidden);
    this.editors[1].setValue(test.stdin || hidden);
    this.editors[2].setValue(test.stdout || hidden);
    this.editors[4].setValue(test.stderr || hidden);
    this.showTestOutput(index);
    // Mark this test case as the selected tab, also when the page selects it
    document.querySelector('.test_cases tab-control').selectedIndex = index;
    this.activeTestCaseIndex = index;
    saveConfig('test', `${index}`);
  }

  // Shows the standard output and error of the given test case after a run
  showTestOutput(index) {
    if (this.result) {
      const test = this.result.results[index];
      // The backend does not send the output of hidden test cases
      const hidden = this.problem.tests[index].hidden ? '(hidden test case)' : '';
      this.editors[3].setValue(test?.stdout || hidden);
      this.editors[5].setValue(test?.stderr || hidden);
      // The diffs compare the expected output and error (left) with the ones of the user (right).
      // The backend trims both before comparing them, so a final newline is not a difference
      [['output_diff', 2, 3], ['error_diff', 4, 5]].forEach(([id, expected, user]) => {
        const { editor } = document.getElementById(id);
        editor.getOriginalEditor().setValue(this.editors[expected].getValue().trim());
        editor.getModifiedEditor().setValue(this.editors[user].getValue().trim());
      });
      this.showParts(index);
      this.updateVerdict(index);
    }
  }

  // The initial code of the problem for the language. The server fills it with the default code
  // of the language when the problem has none
  initialCodeFor(language) {
    return this.problem.initialCodeFor?.[language] || '';
  }

  loadUserCode() {
    console.assert(this.problem);
    this.loadFiles();
    document.getElementById('language').addEventListener('change', () => this.loadFiles());

    // Before Clear or Revert, keep a copy of the file, so Undo can bring it back after reloading
    ['clear_button', 'revert_button'].forEach((id) => {
      document.getElementById(id).addEventListener('click', () => {
        const language = ProblemManager.language();
        const key = `backup:${language}`;
        // Only the backups of the files of the solution are kept, so they do not grow forever
        const backups = Object.entries(parseFiles(loadConfig(key), language) ?? {})
          .filter(([name]) => this.files.has(name));
        saveConfig(key, JSON.stringify({
          ...Object.fromEntries(backups), [this.selectedFile()]: this.editors[0].getValue(),
        }));
      });
    });

    // The main file goes back to the initial code, and the other files to empty
    document.getElementById('revert_button').addEventListener('click', () => {
      // The native dialogs of the browser are enough for a simple confirmation
      // eslint-disable-next-line no-alert
      if (window.confirm(_('Do you want to revert to the initial code?'))) {
        // An edit instead of setValue(), so Undo can bring back the code that was replaced
        const editor = this.editors[0];
        const language = ProblemManager.language();
        const text = this.selectedFile() === this.mainFile() ? this.initialCodeFor(language) : '';
        editor.pushUndoStop();
        editor.executeEdits('revert', [{ range: editor.getModel().getFullModelRange(), text }]);
        editor.pushUndoStop();
      }
    });
  }

  // Each language keeps its own files. Show the files saved for the chosen language, or else its
  // main file with its initial code. The copies from before the last Clear or Revert go first, as
  // older steps in the history, so Undo brings them back after reloading. The language server of
  // the old language closes first, so it never gets the new files, and the new one gets them
  loadFiles() {
    const language = ProblemManager.language();
    saveConfig('language', language);
    this.languageClient?.close();
    const stored = parseFiles(loadConfig(`files:${language}`), language);
    const files = stored ?? { [MAIN_FILES[language]]: this.initialCodeFor(language) };
    const backups = parseFiles(loadConfig(`backup:${language}`), language) ?? {};
    this.viewStates.clear();
    // The backups are not the current code, so they must not be saved as such
    this.showStoredCode(() => this.showFiles(files, backups));
    this.languageClient = null;
    if (LanguageClient.supports(language)) {
      const message = { action: 'lang_server', language }; // Message object
      const getKey = () => ProblemManager.sendJson(message, FETCH_TIMEOUT);
      this.languageClient = new LanguageClient(this.editors[0], language, getKey);
      this.languageClient.start();
    }
  }

  // The slider of the toolbar shows the versions of the solution that the runs saved, and at its
  // end, the code in the editor. Editing a version makes it the code in the editor, which the next
  // run saves as a new version. Only logged users have versions
  setupVersions() {
    const slider = document.getElementById('version');
    if (!slider) {
      return;
    }
    slider.addEventListener('input', () => this.showVersion(Number(slider.value)));
    document.getElementById('language').addEventListener('change', () => this.loadVersions());
    // Without code of their own in this browser, the user gets the last version that they ran
    this.loadVersions(!loadConfig(`files:${ProblemManager.language()}`));
  }

  // Fetch the versions of the solution in the chosen language, and put the slider at its end. If
  // showLast, the editor shows the last version
  async loadVersions(showLast = false) {
    const slider = document.getElementById('version');
    if (!slider) {
      return;
    }
    const language = document.getElementById('language').value;
    let versions = [];
    try {
      const url = `${window.location.pathname}/versions?language=${encodeURIComponent(language)}`;
      const response = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT) });
      versions = response.ok ? await response.json() : [];
    } catch (error) {
      // Without versions the slider is hidden, and the rest of the page works
      console.error(error);
    }
    // The user may have chosen another language while waiting
    if (language !== document.getElementById('language').value) {
      return;
    }
    this.versions = Array.isArray(versions) ? versions : [];
    this.currentFiles = null;
    slider.max = String(this.versions.length);
    slider.value = slider.max;
    slider.closest('.versions').hidden = this.versions.length === 0;
    this.updateVersionName();
    if (showLast && this.versions.length > 0) {
      const files = await this.fetchVersion(language, this.versions[this.versions.length - 1][0]);
      if (files !== null && language === document.getElementById('language').value) {
        this.showStoredCode(() => this.showFiles(files));
      }
    }
  }

  // Return the files of the version of the given commit ({ name: code }), or null if they could
  // not be fetched
  async fetchVersion(language, commit) {
    const key = `${language}:${commit}`;
    if (!this.versionFiles.has(key)) {
      try {
        const query = `language=${encodeURIComponent(language)}`;
        const url = `${window.location.pathname}/versions/${commit}?${query}`;
        const response = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT) });
        const files = response.ok ? parseFiles(await response.text(), language) : null;
        if (!files) {
          return null;
        }
        this.versionFiles.set(key, files);
      } catch (error) {
        console.error(error);
        return null;
      }
    }
    return this.versionFiles.get(key);
  }

  // Show the files of the version at the index, or the current files at the end of the slider.
  // The files keep their Undo history (see showFiles()), and the scroll and the cursor stay
  // where they were
  async showVersion(index) {
    const editor = this.editors[0];
    let files = this.currentFiles;
    if (index < this.versions.length) {
      files = await this.fetchVersion(ProblemManager.language(), this.versions[index][0]);
      // The slider may have moved on while waiting
      if (files === null || index !== Number(document.getElementById('version').value)) {
        return;
      }
      this.currentFiles ??= this.getFiles();
    } else {
      this.currentFiles = null;
    }
    if (files !== null) {
      const view = editor.saveViewState();
      this.showStoredCode(() => this.showFiles(files));
      editor.restoreViewState(view);
    }
    this.updateVersionName();
  }

  // Name the position of the slider: the number and time of a version, e.g. "2 of 5, 11/13, 04:24
  // PM", or the code in the editor
  updateVersionName() {
    const index = Number(document.getElementById('version').value);
    const name = document.getElementById('version_name');
    if (index < this.versions.length) {
      const date = new Date(this.versions[index][1] * 1000);
      const time = date.toLocaleString(document.documentElement.lang, {
        day: 'numeric', month: 'numeric', hour: '2-digit', minute: '2-digit',
      });
      const values = { number: index + 1, count: this.versions.length, time };
      name.textContent = _('%(number)s of %(count)s, %(time)s', values);
    } else {
      name.textContent = _('Current code');
    }
  }

  setupRunEnvironment() {
    console.assert(this.editors.length > 0);
    // When the Run button is pressed, if the user is logged in
    this.runButton?.addEventListener('click', async () => {
      await this.runSolution();
    });
    // site.js checks the connection with the judge. It may have checked it before this page was
    // ready, so the last known state is read from its attribute
    const knownStatus = document.getElementById('backend_status')?.dataset.status;
    this.setOnline(knownStatus !== 'offline');
    window.addEventListener(STATUS_EVENT, (event) => this.setOnline(event.detail.online));
  }

  // Show or hide the connection error, and enable or disable the Run button
  setOnline(online) {
    this.online = online;
    document.getElementById('connection_error').hidden = online;
    this.updateRunButton();
  }

  // The Run button is enabled only if there is code to run, no run is waiting for its result, and
  // the judge can be reached
  updateRunButton() {
    if (!this.runButton) {
      return;
    }
    const hasCode = [...this.files.values()].some((model) => model.getValue().trim().length > 0);
    this.runButton.disabled = this.running || !this.online || !hasCode;
    this.runButton.textContent = this.running ? _('Running') : _('Run');
  }

  async runSolution() {
    // The language chosen in the list of the toolbar
    const language = document.getElementById('language').value;
    // The judge rejects larger solutions, so the student is told here, in their language
    const files = this.getFiles();
    const size = new TextEncoder().encode(Object.values(files).join('')).length;
    if (size > MAX_SOLUTION_BYTES) {
      this.updateCompileOutput(_('The solution is too long: at most %(size)s', { size: formatBytes(MAX_SOLUTION_BYTES) }));
      return;
    }
    // Running a version of the slider makes it the code in the editor, as editing it does, so the
    // editor, the slider, and the files saved in this browser stay the same after the run
    if (this.currentFiles !== null) {
      this.saveFiles();
    }
    // Disable the Run button while the backend is running the code
    this.running = true;
    this.updateRunButton();
    // Problems without test cases run the code with the input and arguments of the user
    const custom = this.problem.tests.length === 0;
    try {
      // Send the code to the backend and wait the result
      this.result = new ExecutionResult(await ProblemManager.sendJson({
        action: 'run',
        language,
        files,
        stdin: custom ? this.editors[1].getValue() : '',
        args: custom ? quoteLines(document.getElementById('args').editor.getValue()) : '',
      }, ProblemManager.getRunTimeout()));
      // The result has been received, update the test cases
      this.updateResult();
      // The slider may have moved to a version during the run, and it goes to its end, so the
      // current files come back
      if (this.currentFiles !== null) {
        this.showVersion(this.versions.length);
      }
      // The run saved a version if the code was new
      this.loadVersions();
    } catch (error) {
      // E.g. the network or the judge failed, or the session expired: show it as a diagnostic
      console.error(error);
      this.updateCompileOutput(_('Could not run the solution: %(error)s', { error: error.message }));
      // The output of the last run would look like the output of the input that the user changed
      if (custom) {
        this.editors[3].setValue('');
        this.editors[5].setValue('');
        document.getElementById('test_verdict').textContent = '';
      }
      // site.js checks the connection now, and disables Run until it is restored if it is lost
      if (error instanceof ConnectionError) {
        window.dispatchEvent(new Event(CHECK_EVENT));
      }
    } finally {
      // Enable the Run button again, even if the run failed, unless the connection is lost
      this.running = false;
      this.updateRunButton();
    }
  }

  updateResult() {
    console.assert(this.result);
    console.dir(this.result);
    this.updateStatistics();
    this.updateCompileOutput();
    this.updateTestCases();
    this.updateVerdict(this.activeTestCaseIndex);
  }

  // Updates the count of passed test cases and count of points after a run
  updateStatistics() {
    console.assert(this.result);

    const passedTestElement = document.getElementById('passed_test_count');
    console.assert(passedTestElement);
    passedTestElement.textContent = String(this.result.passedTestCount);

    const totalTestCount = document.getElementById('total_test_count');
    console.assert(totalTestCount);
    totalTestCount.textContent = String(this.result.results.length);
    const score = this.result.results.length > 0 ? Math.round((
      100.0 * parseFloat(this.result.passedTestCount)) / this.result.results.length) : 0;
    // Runs with the input of the user (problems without test cases) are not graded
    if (this.problem.tests.length > 0) {
      window.localStorage.setItem(this.problem.name, `${score}`);
    }
    console.log(`${this.problem.name} := ${score}`);
    console.dir(this.problem);

    const totalPointsElement = document.getElementById('user_points');
    console.assert(totalPointsElement);
    totalPointsElement.textContent = String(this.result.points);
    // The score takes the place of the hint to press Run. Runs with the input of the user
    // (problems without test cases) are not graded, so they keep the hint
    if (this.problem.tests.length > 0) {
      document.getElementById('score').hidden = false;
      document.getElementById('run_hint').hidden = true;
    }
  }

  // Shows the diagnostics of the judge and the compiler (warnings or errors), if any
  updateCompileOutput(message = null) {
    // The compiler output text
    let compileOutput = message;
    // If no message was provided, get the message of the judge for the whole run (e.g. a missing
    // word in the code, linter errors, or the total time limit) and the compiler output
    if (message === null && this.result) {
      compileOutput = [this.result.message, this.result.compileOutput]
        .filter((text) => text).join('\n\n');
    }
    // Without diagnostics, the code editor underlines nothing
    this.showDiagnostics(compileOutput || '');
    // If there is a diagnostic, show it
    if (compileOutput && compileOutput.length > 0) {
      showElement('diagnostics_wrapper');
    } else {
      hideElement('diagnostics_wrapper');
    }
  }

  // Shows the text of the diagnostics. Its lines about a line of a file of the solution are
  // buttons that go to that line, and the code editor underlines them
  showDiagnostics(text) {
    const diagnostics = [];
    const lines = text.split('\n');
    const nodes = lines.flatMap((line, index) => {
      const diagnostic = ProblemManager.parseDiagnostic(line, lines.slice(index + 1));
      const model = this.files.get(diagnostic?.file);
      // Line 0 of cpplint is about the whole file, e.g. a missing copyright
      if (!model || diagnostic.line < 1) {
        return [line, '\n'];
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.index = diagnostics.length;
      button.dataset.file = diagnostic.file;
      button.textContent = line;
      diagnostics.push({ ...diagnostic, model });
      return [button, '\n'];
    });
    // The last line break is not needed
    nodes.pop();
    document.getElementById('diagnostics').replaceChildren(...nodes);
    document.getElementById('code_editor').showDiagnostics(diagnostics);
  }

  // Return the diagnostic {file, line, column, severity, message} of a line of the compiler, the
  // linker, the linter, Python, or alecci about a line of a file, or null. The following lines
  // carry the message of Python
  static parseDiagnostic(line, nextLines) {
    const match = line.match(DIAGNOSTIC);
    if (match) {
      const [, file, row, column, section, severity, message] = match;
      // Without a severity, a line of the linker is an error, one of gcc with a column gives the
      // context of another, e.g. "required from here", and one of cpplint is a warning of style
      return {
        file,
        line: Number(row),
        column: Number(column) || 0,
        severity: severity || (section && 'error') || (column && 'note') || 'warning',
        message,
      };
    }
    const python = line.match(PYTHON_DIAGNOSTIC);
    if (python) {
      return {
        file: python[1],
        line: Number(python[2]),
        column: 0,
        severity: 'error',
        message: nextLines.find((next) => PYTHON_ERROR.test(next)) || line.trim(),
      };
    }
    const alecci = line.match(ALECCI_DIAGNOSTIC);
    if (alecci) {
      const [, file, severity, message, row] = alecci;
      return {
        file,
        line: Number(row),
        column: 0,
        severity,
        message,
      };
    }
    return null;
  }

  // Updates the test cases buttons after a run
  updateTestCases() {
    // Update the test case handlers (buttons) to show if passed or failed
    const buttons = document.querySelectorAll('.test_cases [role="tab"]');
    console.assert(this.result);
    for (let index = 0; index < buttons.length; index += 1) {
      const test = index < this.result.results.length ? this.result.results[index] : null;
      const button = buttons[index];
      if (test === null) {
        // No status for the button, possible compilation error, no test case were run
        delete button.dataset.status;
      } else {
        button.dataset.status = test.status === Status.PASSED ? 'passed' : 'failed';
      }
      // Updates the standard output/error of the selected test case
      this.showTestOutput(this.activeTestCaseIndex);
    }
    // Problems without test cases show the output of the run with the input of the user
    if (this.problem.tests.length === 0) {
      this.editors[3].setValue(this.result.results[0]?.stdout || '');
      this.editors[5].setValue(this.result.results[0]?.stderr || '');
    }
  }

  // Shows or updates the verdict message
  updateVerdict(index) {
    // The DOM element where the verdict will be shown
    const verdictElement = document.getElementById('test_verdict');
    console.assert(verdictElement);
    // The verdict text for the active test case
    let verdict = null;
    console.assert(this.result);
    // Compiler output should be identical for each test case, we take the first one
    if (this.result && index < this.result.results.length) {
      const test = this.result.results[index];
      // console.dir(test);
      const { status } = test;
      // Runs with the input of the user (problems without test cases) are not judged: they have
      // no verdict, only the message of a failure
      const judged = this.problem.tests.length > 0;
      verdict = [judged && _('Test case %(number)s verdict: %(status)s', { number: index + 1, status }),
        test.message].filter((text) => text).join(': ');
      const seconds = test.wallTime.toFixed(3);
      verdict += verdict ? _('. It took %(seconds)s s', { seconds }) : _('It took %(seconds)s s', { seconds });
      if (test.cpuTime) {
        // CPU time adds up all threads, so it is longer than the wall time in parallel code
        verdict += _(' (CPU %(seconds)s s)', { seconds: test.cpuTime.toFixed(3) });
      }
      if (test.memory) {
        verdict += _(', %(memory)s of memory', { memory: formatBytes(test.memory) });
      }
      if (test.threadCount) {
        verdict += _(', %(count)s secondary threads', { count: test.threadCount });
      }
      if (test.exitCode) {
        verdict += _(', and exited with code %(code)s', { code: test.exitCode });
      }
    }
    // If there is output text, show it
    if (verdict && verdict.length > 0) {
      verdictElement.textContent = verdict;
    } else {
      verdictElement.textContent = '';
    }
  }
}

// Not on the load event: the page may load while i18n.js waits for the translations, and then this
// listener would never run. base.html puts this module at the end of the body, after the elements
ProblemManager.main();
