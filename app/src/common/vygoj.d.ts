/* judge0:/languages/
45: "Assembly (NASM 2.14.02)"
46: "Bash (5.0.0)"
47: "Basic (FBC 1.07.1)"
75: "C (Clang 7.0.1)"
76: "C++ (Clang 7.0.1)"
48: "C (GCC 7.4.0)"
52: "C++ (GCC 7.4.0)"
49: "C (GCC 8.3.0)"
53: "C++ (GCC 8.3.0)"
50: "C (GCC 9.2.0)"
54: "C++ (GCC 9.2.0)"
86: "Clojure (1.10.1)"
51: "C# (Mono 6.6.0.161)"
77: "COBOL (GnuCOBOL 2.2)"
55: "Common Lisp (SBCL 2.0.0)"
56: "D (DMD 2.089.1)"
57: "Elixir (1.9.4)"
58: "Erlang (OTP 22.2)"
44: "Executable"
87: "F# (.NET Core SDK 3.1.202)"
59: "Fortran (GFortran 9.2.0)"
60: "Go (1.13.5)"
88: "Groovy (3.0.3)"
61: "Haskell (GHC 8.8.1)"
62: "Java (OpenJDK 13.0.1)"
63: "JavaScript (Node.js 12.14.0)"
78: "Kotlin (1.3.70)"
64: "Lua (5.3.5)"
89: "Multi-file program"
79: "Objective-C (Clang 7.0.1)"
65: "OCaml (4.09.0)"
66: "Octave (5.1.0)"
67: "Pascal (FPC 3.0.4)"
85: "Perl (5.28.1)"
68: "PHP (7.4.1)"
43: "Plain Text"
69: "Prolog (GNU Prolog 1.4.5)"
70: "Python (2.7.17)"
71: "Python (3.8.1)"
80: "R (4.0.0)"
72: "Ruby (2.7.0)"
73: "Rust (1.40.0)"
81: "Scala (2.13.2)"
82: "SQL (SQLite 3.27.2)"
83: "Swift (5.2.3)"
74: "TypeScript (3.7.4)"
*/
export interface LanguageDefault {
  id: number;
  compiler_options: string;
}

export interface LanguageDefaults {
  readonly [index: string]: LanguageDefault;
}

// Interface for Initial/given code
// To support a new programming language:
// 1. Add its name to this InitialCodeInterface
// 2. Add the default code in client JS public/problem/problem.ts
// 3. Add compiler options in server JS controllers/problemController.ts
export interface InitialCodeInterface {
  C?: string;
  'C++'?: string;
}

// A test case
export interface TestInterface {
  input: string;
  output: string;
  points: number;
  hidden: boolean = false; // TODO: clear it from server side
}

// A problem
export interface ProblemInterface {
  name: string;
  title: string;
  statement: string;
  tests: TestInterface[];
  languages: string[]; // C, C++, Java, Python...
  // Map<string, string> but not supported by JSON
  initialCodeFor?: InitialCodeInterface;
}

// The output for a test case
export interface OutputInterface {
  passed: boolean;
  output: string;
}

// Messages exchanged between the client and server
interface Message {
  action: string;
  error?: string;
  code?: string;
  language?: string;
}

// Result of running a test case
export interface RunResultInterface {
  totalDuration: number;
  threadCount: number;
  outputs: OutputInterface[];
}

export interface Judge0Submission {
  source_code: string;
  language_id: number;
  // Compiler flags: string (max. 512 chars)
  compiler_options?: string;
  stdin: stdinValue,
  command_line_arguments?: commandLineArguments,
  redirect_stderr_to_stdout?: redirectStderrToStdout
}

export interface Judge0Response {
  stdout: string | null;
  time: number;
  memory: number;
  stderr: string | null;
  token: string;
  compile_output: string | null;
  message: string | null;
  status: {
    id: number;
    description: string;
  };
}
