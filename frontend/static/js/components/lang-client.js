// Suggestions and parameter hints of the language server of VygOJ (frontend/lang-srv) in a Monaco
// editor. It talks the Language Server Protocol (LSP) through a WebSocket: it sends the code of
// the editor, and shows what the server answers. Without the server, the editor works as before
import * as monaco from 'https://esm.sh/monaco-editor';

// Solution file of each language in the server, named as the backend names it, and the name of
// the language in LSP, which the editor may not know (Monaco does not highlight every language)
const LANGUAGES = {
  C: { file: 'solution.c', id: 'c' },
  'C++': { file: 'solution.cpp', id: 'cpp' },
};
// Folder of the solution files in the containers of the language server
const ROOT = 'file:///home/student';
// Milliseconds to wait for an answer of the server, for the server to start (some take seconds),
// and between attempts to connect again
const REQUEST_TIMEOUT = 10000;
const START_TIMEOUT = 30000;
const RECONNECT_DELAY = 60000;
// Kinds of suggestions in the order of LSP, whose numbers start at 1, named as in Monaco
const KINDS = ['Text', 'Method', 'Function', 'Constructor', 'Field', 'Variable', 'Class',
  'Interface', 'Module', 'Property', 'Unit', 'Value', 'Enum', 'Keyword', 'Snippet', 'Color',
  'File', 'Reference', 'Folder', 'EnumMember', 'Constant', 'Struct', 'Event', 'Operator',
  'TypeParameter'];

// Returns the Monaco range of an LSP range, which counts lines and characters from 0
function toRange({ start, end }) {
  return new monaco.Range(start.line + 1, start.character + 1, end.line + 1, end.character + 1);
}

// Returns the range of the code that a suggestion replaces: the one of the server, unless the
// server computed it with an older version of the code (e.g. jdtls while the student types fast)
// and it does not contain the cursor, which would make Monaco ignore the suggestion
function editRange(item, position, wordRange) {
  const range = item.textEdit?.range ? toRange(item.textEdit.range) : null;
  const { lineNumber } = position;
  const fits = range?.startLineNumber === lineNumber && range.endLineNumber === lineNumber
    && range.containsPosition(position);
  return fits ? range : wordRange;
}

export default class LanguageClient {
  // True if the language server knows the language of VygOJ, e.g. 'C'
  static supports(language) {
    return Object.hasOwn(LANGUAGES, language);
  }

  // getKey is an async function that returns { url, key } from the frontend to connect
  constructor(editor, language, getKey) {
    // The editor that gets the suggestions
    this.editor = editor; // monaco.editor.IStandaloneCodeEditor
    // Address of the solution file in the language server, and its language in LSP
    this.uri = `${ROOT}/${LANGUAGES[language].file}`; // string
    this.languageId = LANGUAGES[language].id; // string
    // Function that asks the frontend for a key
    this.getKey = getKey; // async function
    // Connection with the language server, null while there is none
    this.socket = null; // WebSocket
    // True after the server accepted the code of the editor
    this.ready = false; // boolean
    // True after close(), so a connection that was starting is not used
    this.closed = false; // boolean
    // Functions that receive the answers of the server, by the id of their request
    this.pending = new Map(); // Map
    // Id of the next request, and version of the code that the server has
    this.nextId = 1; // number
    this.version = 1; // number
    // Milliseconds of the last attempt to connect, as Date.now()
    this.lastAttempt = 0; // number
    // Providers of Monaco and listeners of the editor, removed by close()
    this.disposables = []; // Array of monaco.IDisposable
    // True after the providers were registered, at the first connection
    this.registered = false; // boolean
  }

  // Sends the changes of the code to the server, and connects
  start() {
    this.disposables.push(this.editor.onDidChangeModelContent(() => this.sendCode()));
    this.connect();
  }

  // Registers the providers of suggestions and parameter hints once, with the characters that the
  // server suggests after: e.g. ':' in C++ for '::', but not in Python, where it ends lines
  register({ completionProvider, signatureHelpProvider }) {
    if (this.registered) {
      return;
    }
    this.registered = true;
    const language = this.editor.getModel().getLanguageId();
    this.disposables.push(
      monaco.languages.registerCompletionItemProvider(language, {
        triggerCharacters: completionProvider?.triggerCharacters,
        provideCompletionItems: (...args) => this.suggest(...args),
      }),
      monaco.languages.registerSignatureHelpProvider(language, {
        signatureHelpTriggerCharacters: signatureHelpProvider?.triggerCharacters,
        signatureHelpRetriggerCharacters: signatureHelpProvider?.retriggerCharacters,
        provideSignatureHelp: (model, position) => this.hint(model, position),
      }),
    );
  }

  // Disconnects and removes the providers, e.g. when the user chooses another language
  close() {
    this.closed = true;
    this.disposables.forEach((disposable) => disposable.dispose());
    this.socket?.close();
  }

  // Connects with a new key, and sends the code when the server is ready. Errors leave the
  // editor without the server, and a later change of the code tries again
  async connect() {
    this.lastAttempt = Date.now();
    try {
      const { url, key } = await this.getKey();
      // Without a language server, the frontend sends no address, and Monaco suggests the words
      // of the code again when the providers are removed
      if (!url) {
        this.close();
      }
      if (this.closed) {
        return;
      }
      const socket = new WebSocket(url);
      this.socket = socket;
      socket.addEventListener('message', ({ data }) => {
        const { id, result } = JSON.parse(data);
        this.pending.get(id)?.(result ?? null);
      });
      socket.addEventListener('close', () => {
        this.socket = null;
        this.ready = false;
        this.pending.forEach((resolve) => resolve(null));
      });
      await new Promise((resolve, reject) => {
        socket.addEventListener('open', resolve);
        socket.addEventListener('close', reject);
        setTimeout(reject, START_TIMEOUT);
      });
      socket.send(key);
      // Monaco shows the documentation as Markdown
      const capabilities = {
        textDocument: {
          completion: { completionItem: { documentationFormat: ['markdown'] } },
          signatureHelp: {
            signatureInformation: {
              documentationFormat: ['markdown'],
              parameterInformation: { labelOffsetSupport: true },
            },
          },
        },
      };
      const params = { processId: null, rootUri: ROOT, capabilities };
      const result = await this.request('initialize', params, START_TIMEOUT);
      if (!result) {
        throw new Error('The language server did not start');
      }
      this.register(result.capabilities ?? {});
      this.notify('initialized', {});
      const { uri, languageId, version } = this;
      const textDocument = {
        uri, languageId, version, text: this.editor.getValue(),
      };
      this.notify('textDocument/didOpen', { textDocument });
      this.ready = true;
    } catch {
      this.socket?.close();
    }
  }

  // Sends the whole code to the server after each change, or connects again if the connection
  // was lost (e.g. the student did not type for a while)
  sendCode() {
    if (this.ready) {
      this.version += 1;
      this.notify('textDocument/didChange', {
        textDocument: { uri: this.uri, version: this.version },
        contentChanges: [{ text: this.editor.getValue() }],
      });
    } else if (!this.socket && !this.closed && Date.now() - this.lastAttempt > RECONNECT_DELAY) {
      this.connect();
    }
  }

  // Sends a notification, which has no answer
  notify(method, params) {
    this.socket?.send(JSON.stringify({ jsonrpc: '2.0', method, params }));
  }

  // Sends a request and returns its result, or null if the server does not answer in time
  request(method, params, timeout = REQUEST_TIMEOUT) {
    const id = this.nextId;
    this.nextId += 1;
    this.socket?.send(JSON.stringify({
      jsonrpc: '2.0', id, method, params,
    }));
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        resolve(null);
      }, timeout);
      this.pending.set(id, (result) => {
        clearTimeout(timer);
        this.pending.delete(id);
        resolve(result);
      });
    });
  }

  // Returns the request parameters for the position of the cursor in the solution file
  at(position) {
    return {
      textDocument: { uri: this.uri },
      position: { line: position.lineNumber - 1, character: position.column - 1 },
    };
  }

  // Returns the suggestions of the server for the position of the cursor
  async suggest(model, position, { triggerKind, triggerCharacter }) {
    if (model !== this.editor.getModel() || !this.ready) {
      return null;
    }
    // Why the editor asks, e.g. a ':' that is not part of '::', so the server may answer nothing.
    // The kinds of LSP count from 1, and the ones of Monaco from 0
    const context = { triggerKind: triggerKind + 1, triggerCharacter };
    const result = await this.request('textDocument/completion', { ...this.at(position), context });
    const items = Array.isArray(result) ? result : result?.items ?? [];
    const word = model.getWordUntilPosition(position);
    const { lineNumber } = position;
    const range = new monaco.Range(lineNumber, word.startColumn, lineNumber, word.endColumn);
    const { CompletionItemKind } = monaco.languages;
    return {
      // The server sends part of the suggestions, and Monaco asks again while the student types
      incomplete: Boolean(result?.isIncomplete),
      suggestions: items.map((item) => ({
        label: item.label.trim(),
        kind: CompletionItemKind[KINDS[item.kind - 1]] ?? CompletionItemKind.Text,
        detail: item.detail,
        documentation: item.documentation,
        insertText: item.textEdit?.newText ?? item.insertText ?? item.label.trim(),
        filterText: item.filterText,
        sortText: item.sortText,
        range: editRange(item, position, range),
        // E.g. the #include of a function of another header, added when the student chooses it
        additionalTextEdits: item.additionalTextEdits?.map((edit) => ({
          range: toRange(edit.range), text: edit.newText,
        })),
      })),
    };
  }

  // Returns the parameters of the function called at the position of the cursor, with the one
  // that the cursor is in highlighted
  async hint(model, position) {
    if (model !== this.editor.getModel() || !this.ready) {
      return null;
    }
    const result = await this.request('textDocument/signatureHelp', this.at(position));
    if (!result?.signatures?.length) {
      return null;
    }
    const value = {
      signatures: result.signatures,
      activeSignature: result.activeSignature ?? 0,
      activeParameter: result.activeParameter ?? 0,
    };
    return { value, dispose: () => {} };
  }
}
