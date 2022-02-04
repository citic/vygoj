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
  hidden: boolean; // TODO: clear it from server side
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

// Execution status enumeration
export enum Status {
  pending = 'pending',
  passed = 'passed',
  wrong = 'wrong',
  timeout = 'timeout',
  compilerError = 'compilerError',
  runtimeError = 'runtimeError',
  internalError = 'internalError',
};

// Messages exchanged between the client and server
export interface Message {
  action: string;
  error?: string;
  code?: string;
  language?: string;
}

export interface Judge0Submission {
  source_code: string;
  language_id: number;
  // Compiler flags: string (max. 512 chars)
  compiler_options?: string;
  stdin: string; // stdinValue,
  command_line_arguments?: string; /// commandLineArguments,
  redirect_stderr_to_stdout?: boolean; // redirectStderrToStdout
}

export type text = string | null;

export interface Judge0Response {
  additional_files?: text; // ?
  callback_url?: text;
  command_line_arguments?: text;
  compile_output: text;
  compiler_options?: text;
  cpu_extra_time?: text; // eg "1.0"
  cpu_time_limit?: text; // eg "5.0"
  created_at?: text; // eg "2022-01-28T17:44:52.789Z"
  enable_network?: boolean; // default false
  enable_per_process_and_thread_memory_limit?: boolean; // default false
  enable_per_process_and_thread_time_limit?: boolean; // default false
  exit_code?: number; // eg: 66
  exit_signal?: text; // ?
  expected_output?: text; // ?
  finished_at?: text; // eg: "2022-01-28T17:44:54.580Z"
  language?: {
      id: number; // eg: 50
      name: string; // eg: "C (GCC 9.2.0)"
  };
  language_id?: number; // eg: 50
  max_file_size?: number; // eg: 1024
  max_processes_and_or_threads?: number; // eg: 60
  memory: number; // eg: 128000
  memory_limit?: number; // eg: 128000
  message: text; // eg: "Exited with error status 66\n"
  number_of_runs?: number; // eg: 1
  redirect_stderr_to_stdout?: boolean; // eg: false
  source_code?: text;
  stack_limit?: number; // 64000
  status: {
      description: string; // eg: "Runtime Error (NZEC)"
      id: number; // eg: 11
  };
  status_id: number; // eg: 11
  stderr: text;
  stdin?: text;
  stdout: text;
  time: text; // eg: "1.404"
  token: string; // eg: "ffe8a56b-0fa1-49b9-ad60-c42925efbe19"
  wall_time?: text; // eg: "1.081"
  wall_time_limit?: text; // eg: "10.0"
}

// Result of running a test case
export interface TestCaseResult {
  // Compiler output or null if no output was generated
  compileOutput: text;
  // CPU time, i.e all threads added
  cpuTime: text;
  // Exit code reported by the program to the operating system after running this test case
  exitCode: number;
  // Memory used by the process (bytes)
  memory: number;
  // A human-readable verdict emitted by the judge
  message: text;
  // An enumeration value code of the verdict, see vyg.Status
  status: Status;
  // number_of_runs?
  // Text sent by the user solution to the standar error
  stderr: text;
  // Text sent by the user solution to the standar output
  stdout: text;
  // Number of threads created by solution for this test case
  threadCount: number;
  // Wall time
  wallTime: text;
}

export interface ExecutionResult {
  // Count of passed test cases
  passedTestCount: number;
  // Points gained by this solution
  points: number;
  // Wall time of the largest test case
  maxWallTime: number;
  // Results of each test case
  results: TestCaseResult[];
}
