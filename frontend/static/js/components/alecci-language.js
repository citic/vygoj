// Alecci language for Monaco: highlighting, comments, brackets, and indentation. It is a Monarch
// port of the TextMate grammar of the official VS Code extension (bryan-ulate.alecci-syntax), at
// https://github.com/citic/alecci/tree/main/.vscode/extensions/pseudocode-syntax
// TODO(jhc): replace with the language server of Alecci when there is one

const LANGUAGE_ID = 'alecci';

const configuration = {
  comments: { lineComment: '//', blockComment: ['/*', '*/'] },
  brackets: [['{', '}'], ['[', ']'], ['(', ')']],
  autoClosingPairs: ['{}', '[]', '()', '""', "''", '``'].map(([open, close]) => ({ open, close })),
  surroundingPairs: ['{}', '[]', '()', '""', "''", '``'].map(([open, close]) => ({ open, close })),
  indentationRules: {
    increaseIndentPattern: /^\s*(procedure|function|for|if|while)\b.*$/,
    decreaseIndentPattern: /^\s*(end|else)\b.*$/,
  },
};

const tokens = {
  keywords: [
    // Control
    'procedure', 'function', 'return', 'if', 'then', 'else', 'while', 'parallel', 'for', 'do',
    'to', 'with', 'end', 'break', 'continue', 'case', 'of', 'record', 'enum',
    // Declarations
    'shared', 'mutable', 'const', 'atomic', 'as',
    // Logical operators and constants
    'and', 'or', 'not', 'true', 'false', 'null',
  ],
  typeKeywords: ['int', 'float', 'string', 'bool', 'array', 'thread', 'mutex', 'semaphore'],
  builtins: [
    'print', 'create_thread', 'create_threads', 'join_thread', 'join_threads', 'lock', 'unlock',
    'wait', 'signal',
  ],
  brackets: [
    { open: '{', close: '}', token: 'delimiter.curly' },
    { open: '[', close: ']', token: 'delimiter.square' },
    { open: '(', close: ')', token: 'delimiter.parenthesis' },
  ],
  tokenizer: {
    root: [
      [/\/\/.*$/, 'comment'],
      [/\/\*/, 'comment', '@comment'],
      [/"/, 'string', '@doubleQuoted'],
      [/'/, 'string', '@singleQuoted'],
      [/`/, 'string', '@template'],
      [/[a-zA-Z_]\w*/, {
        cases: {
          '@typeKeywords': 'type',
          '@keywords': 'keyword',
          '@builtins': 'predefined',
          '@default': 'identifier',
        },
      }],
      [/\d+\.\d+/, 'number.float'],
      [/\d+/, 'number'],
      [/:=|==|!=|<=|>=|&&|\|\||[<>+\-*/%!]/, 'operator'],
      [/[{}()[\]]/, '@brackets'],
    ],
    comment: [
      [/[^/*]+/, 'comment'],
      [/\*\//, 'comment', '@pop'],
      [/[/*]/, 'comment'],
    ],
    doubleQuoted: [
      [/[^\\"]+/, 'string'],
      [/\\./, 'string.escape'],
      [/"/, 'string', '@pop'],
    ],
    singleQuoted: [
      [/[^\\']+/, 'string'],
      [/\\./, 'string.escape'],
      [/'/, 'string', '@pop'],
    ],
    // Template strings interpolate expressions between braces, e.g. `Worker {thread_number}`
    template: [
      [/[^\\`{]+/, 'string'],
      [/\\./, 'string.escape'],
      [/\{/, 'delimiter.curly', '@interpolation'],
      [/`/, 'string', '@pop'],
    ],
    interpolation: [
      [/\}/, 'delimiter.curly', '@pop'],
      { include: 'root' },
    ],
  },
};

// Lets the editors of the page highlight Alecci code with language="alecci"
export default function registerAlecci(monaco) {
  monaco.languages.register({ id: LANGUAGE_ID, extensions: ['.ale'], aliases: ['Alecci'] });
  monaco.languages.setLanguageConfiguration(LANGUAGE_ID, configuration);
  monaco.languages.setMonarchTokensProvider(LANGUAGE_ID, tokens);
}
