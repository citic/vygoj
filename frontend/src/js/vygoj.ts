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
  commandLineArguments: string;
  input: string;
  output: string;
  stderr: string;
  points: number;
  hidden: boolean; // TODO: clear it from server side
  minThreads?: number;
  maxThreads?: number;
  minDuration?: number;
  maxDuration?: number;
}

// A problem
export interface ProblemInterface {
  // relative_path: string;
  name: string;
  title: string;
  statement: string;
  tests: TestInterface[];
  languages: string[]; // C, C++, Java, Python...
  // Map<string, string> but not supported by JSON
  initialCodeFor?: InitialCodeInterface;
  minThreads?: number;
  maxThreads?: number;
  allowIndeterminism?: string;
  mustContain?: Array<string>;
  minDuration?: number;
  maxDuration?: number;
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
  language?: string;
  code?: string;
}

export type text = string | null;

// Result of running a test case
export interface TestCaseResult {
  // An enumeration value code of the verdict, see vyg.Status
  status: Status;
  // A human-readable verdict emitted by the judge
  message: text;
  // CPU time, i.e all threads added
  cpuTime: text;
  // Exit code reported by the program to the operating system after running this test case
  exitCode: number;
  // Memory used by the process (bytes)
  memory: number;
  // number_of_runs?
  // Text sent by the user solution to the standard error
  stderr: text;
  // Text sent by the user solution to the standard output
  stdout: text;
  // Number of threads created by solution for this test case
  threadCount: number;
  // Wall time
  wallTime: text;
}

export interface ExecutionResult {
  // An enumeration value code of the verdict, see vyg.Status
  status: Status;
  // A human-readable verdict emitted by the judge
  message: text;
  // Compiler output or null if no output was generated
  compileOutput: text;
  // Count of passed test cases
  passedTestCount: number;
  // Points gained by this solution
  points: number;
  // Total points (sum of all test cases)
  totalPoints: number;
  // Wall time of the largest test case
  maxWallTime: number;
  // Results of each test case
  results: TestCaseResult[];
}
