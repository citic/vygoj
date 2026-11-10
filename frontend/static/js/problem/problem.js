import {
  ExecutionResult, Problem, Status,
} from '../vyg.js';
import { CHECK_EVENT, STATUS_EVENT } from '../site.js';
import _ from '../i18n.js';
import '../components/monaco-editor.js';
import '../components/editor-toolbar.js';

// Milliseconds to wait for the answers of the server, so the page never waits forever. The time of
// a run depends on the limits of the judge, so the page gets it in data-run-timeout (seconds, see
// Limits.client_run_timeout() in limits.py). DEFAULT_RUN_TIMEOUT is used if it is missing
const FETCH_TIMEOUT = 30000;
const DEFAULT_RUN_TIMEOUT = 120000;
// HTTP statuses of the frontend or a proxy when the judge cannot be reached
const UNREACHABLE_STATUSES = [502, 503, 504];
// A line of the compiler, the linker, or the linter about a line of the solution, with its line,
// its column or section of the linker, its severity, and its message. E.g. "solution.c:4:18:
// error: 'y' undeclared" (gcc), "/tmp/solution.c:3:(.text+0x5): undefined reference to `foo'"
// (ld), "solution.c:5:  Missing space after ,  [whitespace/comma] [3]" (cpplint),
// "Solution.java:7: error: ';' expected" (javac), or "solution.ale:3:1: syntax error: unexpected
// token 'end'" (alecci)
const DIAGNOSTIC = /^(?:\S*\/)?[Ss]olution\.\w+:(\d+):(?:(\d+):|(\(\.[^)]*\)):)?\s*(?:(?:fatal |syntax )?(error|warning|note):)?\s*(.*)$/;
// A line of Python about a line of the solution, e.g. '  File "solution.py", line 3' of a syntax
// error. Its message is in a later line that names the error, e.g. "SyntaxError: invalid syntax"
const PYTHON_DIAGNOSTIC = /^\s*File "(?:\S*\/)?solution\.py", line (\d+)/;
const PYTHON_ERROR = /^\w*(?:Error|Exception|Warning)\b/;
// An error of alecci with its line at the end, e.g. "solution.ale: error: undefined variable 'y'
// (line 2)"
const ALECCI_DIAGNOSTIC = /^(?:\S*\/)?solution\.ale: (error|warning): (.*) \(line (\d+)\)$/;

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
  }

  setupCodeEditor() {
    const codeEditor = document.getElementById('code_editor');
    const { editor } = codeEditor;
    // The language chosen in the list of the toolbar is remembered for each problem, and the
    // highlighting follows it. An invalid language in localStorage selects the first one
    const languageList = document.getElementById('language');
    languageList.value = loadConfig('language');
    if (languageList.selectedIndex < 0) {
      languageList.selectedIndex = 0;
    }
    const setLanguage = () => {
      saveConfig('language', languageList.value);
      codeEditor.setAttribute('language', monacoLanguageFor[languageList.value.toLowerCase()] || 'plaintext');
    };
    setLanguage();
    languageList.addEventListener('change', setLanguage);
    editor.getModel().updateOptions({ tabSize: 2 }); // Google code style
    this.editors.push(editor);
    // The editor is as tall as its code, between the min-height and max-height of the CSS, until
    // the user gives it another height with its corner handle
    let fittedHeight = '';
    editor.onDidContentSizeChange(() => {
      const { style } = editor.getContainerDomNode();
      if (style.height === fittedHeight) {
        fittedHeight = `${editor.getContentHeight()}px`;
        style.height = fittedHeight;
      }
    });
    editor.onDidChangeModelContent(() => {
      if (this.savesCode) {
        saveConfig(`code:${languageList.value}`, editor.getValue());
      }
      this.updateRunButton();
    });
    // Another tab of this problem saved its code for the chosen language: show it here too.
    // Events arrive late, so an event whose code is not the stored one anymore is old, and it is
    // ignored. An edit instead of setValue() keeps the Undo history of this tab, as its own step
    window.addEventListener('storage', (event) => {
      if (event.key === `code:${languageList.value}:${window.location.pathname}`
        && event.newValue !== null && event.newValue === window.localStorage.getItem(event.key)
        && event.newValue !== editor.getValue()) {
        this.showStoredCode(() => {
          editor.pushUndoStop();
          editor.executeEdits('storage', [{ range: editor.getModel().getFullModelRange(), text: event.newValue }]);
          editor.pushUndoStop();
        });
      }
    });
    // Clicking a line of the diagnostics about a line of the code goes to its code
    document.getElementById('diagnostics').addEventListener('click', ({ target }) => {
      const index = target.closest('button')?.dataset.index;
      if (index) {
        codeEditor.goToDiagnostic(Number(index));
      }
    });
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
    ProblemManager.resizeTestCaseEditorsTogether();
  }

  // Side by side, stretching one of these editors with its corner handle stretches the others too,
  // so the row stays aligned. One below the other, each one keeps its own height
  static resizeTestCaseEditorsTogether() {
    const row = document.getElementById('active_test');
    const editors = row.querySelectorAll('monaco-editor');
    const observer = new ResizeObserver(([{ target }]) => {
      if (getComputedStyle(row).flexDirection === 'row') {
        editors.forEach((editor) => { editor.style.height = target.style.height; });
      }
    });
    editors.forEach((editor) => observer.observe(editor));
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
    const buttons = document.querySelectorAll('.test_cases button');
    console.assert(buttons.length === this.problem.tests.length);
    // Make each test case button clickable
    for (let index = 0; index < buttons.length; index += 1) {
      buttons[index].addEventListener('click', () => {
        this.showTestCase(index);
      });
    }
    // Make the last selected test case (in local storage) as the active one. localStorage can
    // be edited by anyone, and problems may have fewer test cases now, so check the index
    if (buttons.length > 0) {
      const index = parseInt(loadConfig('test') || '0', 10);
      this.activeTestCaseIndex = index >= 0 && index < buttons.length ? index : 0;
      this.showTestCase(this.activeTestCaseIndex);
    }
  }

  showTestCase(index) {
    console.assert(this.problem);
    console.assert(this.editors.length === 4);
    // Show input, expected output, and user output for this test case. The server does not
    // send the contents of hidden test cases
    const test = this.problem.tests[index];
    const hidden = test.hidden ? '(hidden test case)' : '';
    this.editors[1].setValue(test.stdin || hidden);
    this.editors[2].setValue(test.stdout || hidden);
    this.showTestOutput(index);
    // Deselect previous test case number
    const buttons = document.querySelectorAll('.test_cases button');
    console.assert(this.activeTestCaseIndex < buttons.length);
    buttons[this.activeTestCaseIndex].removeAttribute('aria-current');
    // Mark this test case as the active in the interface
    console.assert(index < buttons.length);
    this.activeTestCaseIndex = index;
    buttons[index].setAttribute('aria-current', 'true');
    saveConfig('test', `${index}`);
  }

  // Shows the standard output and error of the given test case after a run
  showTestOutput(index) {
    if (this.result) {
      // Show standard output
      const test = index < this.result.results.length ? this.result.results[index] : null;
      // The backend does not send the output of hidden test cases
      const hidden = this.problem.tests[index].hidden ? '(hidden test case)' : '';
      this.editors[3].setValue(test?.stdout || hidden);
      // But if test case was failed, show diff instead
      this.showOutputDiff(index);
      // Show standard error
      this.updateErrorOutput(index);
      // Show message if nay
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
    // Each language keeps its own code. Show the code saved for the chosen language, or else
    // its initial code. Its copy from before the last Clear or Revert goes first, as an older step
    // in the history, so Undo brings it back after reloading. Editing also updates the Run button
    const languageList = document.getElementById('language');
    const showCode = () => {
      const editor = this.editors[0];
      const language = languageList.value;
      const code = loadConfig(`code:${language}`) || this.initialCodeFor(language);
      // The backup is not the current code, so it must not be saved as such
      this.showStoredCode(() => {
        editor.setValue(loadConfig(`backup:${language}`) || code);
        editor.executeEdits('load', [{ range: editor.getModel().getFullModelRange(), text: code }]);
        editor.pushUndoStop();
      });
    };
    showCode();
    languageList.addEventListener('change', showCode);

    // Before Clear or Revert, keep a copy of the code, so Undo can bring it back after reloading
    ['clear_button', 'revert_button'].forEach((id) => {
      document.getElementById(id).addEventListener('click', () => {
        saveConfig(`backup:${languageList.value}`, this.editors[0].getValue());
      });
    });

    document.getElementById('revert_button').addEventListener('click', () => {
      // The native dialogs of the browser are enough for a simple confirmation
      // eslint-disable-next-line no-alert
      if (window.confirm(_('Do you want to revert to the initial code?'))) {
        // An edit instead of setValue(), so Undo can bring back the code that was replaced
        const editor = this.editors[0];
        const text = this.initialCodeFor(languageList.value);
        editor.pushUndoStop();
        editor.executeEdits('revert', [{ range: editor.getModel().getFullModelRange(), text }]);
        editor.pushUndoStop();
      }
    });
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
    const hasCode = this.editors[0].getValue().trim().length > 0;
    this.runButton.disabled = this.running || !this.online || !hasCode;
    this.runButton.textContent = this.running ? _('Running') : _('Run');
  }

  async runSolution() {
    // The language chosen in the list of the toolbar
    const language = document.getElementById('language').value;
    // Disable the Run button while the backend is running the code
    this.running = true;
    this.updateRunButton();
    try {
      // Send the code to the backend and wait the result
      this.result = new ExecutionResult(await ProblemManager.sendJson({
        action: 'run',
        language,
        code: this.editors[0].getValue(),
      }, ProblemManager.getRunTimeout()));
      // The result has been received, update the test cases
      this.updateResult();
    } catch (error) {
      // E.g. the network or the judge failed, or the session expired: show it as a diagnostic
      console.error(error);
      this.updateCompileOutput(_('Could not run the solution: %(error)s', { error: error.message }));
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
    this.updateErrorOutput(this.activeTestCaseIndex);
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
    window.localStorage.setItem(this.problem.name, `${score}`);
    console.log(`${this.problem.name} := ${score}`);
    console.dir(this.problem);

    const totalPointsElement = document.getElementById('user_points');
    console.assert(totalPointsElement);
    totalPointsElement.textContent = String(this.result.points);
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
    ProblemManager.showDiagnostics(compileOutput || '');
    // If there is a diagnostic, show it
    if (compileOutput && compileOutput.length > 0) {
      showElement('diagnostics_wrapper');
    } else {
      hideElement('diagnostics_wrapper');
    }
  }

  // Shows the text of the diagnostics. Its lines about a line of the code are buttons that go to
  // that line, and the code editor underlines them
  static showDiagnostics(text) {
    const diagnostics = [];
    const lines = text.split('\n');
    const nodes = lines.flatMap((line, index) => {
      const diagnostic = ProblemManager.parseDiagnostic(line, lines.slice(index + 1));
      // Line 0 of cpplint is about the whole file, e.g. a missing copyright
      if (!diagnostic || diagnostic.line < 1) {
        return [line, '\n'];
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.index = diagnostics.length;
      button.textContent = line;
      diagnostics.push(diagnostic);
      return [button, '\n'];
    });
    // The last line break is not needed
    nodes.pop();
    document.getElementById('diagnostics').replaceChildren(...nodes);
    document.getElementById('code_editor').showDiagnostics(diagnostics);
  }

  // Return the diagnostic {line, column, severity, message} of a line of the compiler, the
  // linker, the linter, Python, or alecci about a line of the solution, or null. The following
  // lines carry the message of Python
  static parseDiagnostic(line, nextLines) {
    const match = line.match(DIAGNOSTIC);
    if (match) {
      const [, row, column, section, severity, message] = match;
      // Without a severity, a line of the linker is an error, one of gcc with a column gives the
      // context of another, e.g. "required from here", and one of cpplint is a warning of style
      return {
        line: Number(row),
        column: Number(column) || 0,
        severity: severity || (section && 'error') || (column && 'note') || 'warning',
        message,
      };
    }
    const python = line.match(PYTHON_DIAGNOSTIC);
    if (python) {
      return {
        line: Number(python[1]),
        column: 0,
        severity: 'error',
        message: nextLines.find((next) => PYTHON_ERROR.test(next)) || line.trim(),
      };
    }
    const alecci = line.match(ALECCI_DIAGNOSTIC);
    if (alecci) {
      const [, severity, message, row] = alecci;
      return {
        line: Number(row),
        column: 0,
        severity,
        message,
      };
    }
    return null;
  }

  // Shows standard error output for the selected test case
  updateErrorOutput(index) {
    // The DOM element where the output will be shown
    const stderrElement = document.getElementById('stderr');
    console.assert(stderrElement);
    // The program stderr output text for the active test case
    let stderrOutput = null;
    console.assert(this.result);
    // If the test case result exists, get its message, otherwise (compilation error?) clear field
    if (index < this.result.results.length) {
      // Compiler output should be identical for each test case, we take the first one
      // TODO(jhc): Compile output is in the problem result instead of test result
      if (this.result && index < this.result.results.length) {
        stderrOutput = this.result.results[index].stderr;
      }
    }
    // If there is output text, show it
    if (stderrOutput && stderrOutput.length > 0) {
      stderrElement.textContent = stderrOutput;
      showElement('stderr_wrapper');
    } else {
      hideElement('stderr_wrapper');
    }
  }

  // Shows a diff output instead of standard output
  showOutputDiff(index) {
    // Expected output
    console.assert(this.problem);
    console.assert(index < this.problem.tests.length);
    const expectedOutput = this.problem.tests[index].stdout;
    // User output
    console.assert(this.result);
    // If the test case result exists, get its message, otherwise (compilation error?) clear field
    let userOutput = null;
    if (index < this.result.results.length) {
      userOutput = this.result.results[index].stdout;
    }
    if (userOutput && this.result.results[index].status === Status.WRONG) {
      // Hide expected output and user output and show diff element
      hideElement('active_test_expected_output_wrapper');
      hideElement('active_test_user_output_wrapper');
      showElement('output_diff_wrapper');
      // Expected output on the left, user output on the right
      const { editor } = document.getElementById('output_diff');
      editor.getOriginalEditor().setValue(expectedOutput);
      editor.getModifiedEditor().setValue(userOutput);
    } else {
      // Show expected output and user output and hide diff element
      hideElement('output_diff_wrapper');
      showElement('active_test_expected_output_wrapper');
      showElement('active_test_user_output_wrapper');
    }
  }

  // Updates the test cases buttons after a run
  updateTestCases() {
    // Update the test case handlers (buttons) to show if passed or failed
    const buttons = document.querySelectorAll('.test_cases button');
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
      verdict = _('Test case %(number)s verdict: %(status)s', { number: index + 1, status });
      if (test.message) {
        verdict += `: ${test.message}`;
      }
      verdict += _('. It took %(seconds)s s', { seconds: test.wallTime.toFixed(3) });
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

window.addEventListener('load', ProblemManager.main);
