// Common JavaScript code for the VygOJ client-side JavaScript

// Encode a string to base64 format
export function encode(text) {
  // text 'int main(int argc, char* argv[]) {\n  return atoi(argv[--argc]);\n}\n'
  // btoa 'aW50IG1haW4oaW50IGFyZ2MsIGNoYXIqIGFyZ3ZbXSkgewogIHJldHVybiBhdG9pKGFyZ3ZbLS1hcmdjXSk7Cn0K'
  return window.btoa(text);
}

/// Decode a base64 encoded string to its original text
export function decode(data) {
  return window.atob(data);
}

/// Class to create enum objects serializable to JSON
class Enum {
  constructor(fields) {
    const instance = {
      // Each field will be a property of the Enum class
      ...fields,

      // Serialize this enum value to a JSON object
      toJSON: function() {
        return Object.keys(this).reduce((jsonObject, key) => {
          // Only copy string properties to the JSON object, skip methods
          if (typeof this[key] === 'string') {
            jsonObject[key] = this[key];
          }
          return jsonObject;
        }, {}); // Provide an initial empty object as reduction target
      }, // toJSON

      // Load this enum value from a JSON object
      parse: function(jsonObject) {
        if (Object.values(this).includes(jsonObject)) {
          return jsonObject;
        }
        throw new Error(`Invalid enum value: ${jsonObject}`);
      }
    };

    // Make properties of enum object inmutable
    return Object.freeze(instance);
  }
}

export class Message {
  constructor(action, error = '', language = '', code = '') {
    // Action to perform: 'run', 'fetch_problem'
    this.action = action;
    // Error message if any
    this.error = error;
    // Programming language to use, e.g. 'cpp', 'python'
    this.language = language;
    // Source code to run or submit
    this.code = code;
  }
}

// Execution status for a test case or entire submission
export const Status = new Enum({
  PENDING: 'pending',
  PASSED: 'passed',
  WRONG: 'wrong',
  TIMEOUT: 'timeout',
  COMPILER_ERROR: 'compilerError',
  RUNTIME_ERROR: 'runtimeError',
  INTERNAL_ERROR: 'internalError',
});

const MAX_THREADS = 2**15;

export class Problem {
  // TODO(jhc): Some properties are not needed in the web client, remove them from JS
  constructor(json) {
    console.assert(json);
    // Relative path identifies the problem, used only by the frontend, not the web client.
    // this.relative_path = json?.relative_path || '';
    // An identifier name for the problem, eg "uint64_adder"
    this.name = json?.name || '';
    // Title describing the problem, eg "Unsigned 64-bits adder"
    this.title = decode(json?.title || '');
    // Problem statement in HTML code
    // TODO(jhc): use problem.{en|es|...}.{md|adoc|html} files instead
    this.statement = decode(json?.statement || '');
    // Convert json test cases to TestCase objects
    this.tests = (json?.tests || []).map((test) => new TestCase(test));
    // Allowed programming languages for this problem
    this.languages = json?.languages || [];
    // Map<string, string> but not supported by JSON. A simple object used instead
    this.initialCodeFor = json?.initialCodeFor || {};
    // Minimum number of secondary threads to solve the problem. If this number
    // is one or more, additional runs will be conducted for each test case
    this.minThreads = json?.minThreads || 1;
    // There is no limit for the default number of secondary threads
    this.maxThreads = json?.maxThreads || MAX_THREADS;
    // Considers valid an output that has different order than the expected
    // Supported values: 'none', 'lines'
    this.allowIndeterminism = json?.allowIndeterminism || 'none';
    // Considers invalid a solution if it does NOT contains words in this array
    this.mustContain = json?.mustContain || [];
    // Allowed time range in seconds specified by professor for all test cases
    this.minDuration = json?.minDuration || 0.0;
    // Maximum wall time duration that user solution must spent to consider it correct
    this.maxDuration = json?.maxDuration;
    // Extra tools, one of: asan tsan ubsan memcheck helgrind
    // this.tools = json?.tools || '';

    // Decode the initial code for each language
    for (const key in this.initialCodeFor) {
      if (Object.prototype.hasOwnProperty.call(this.initialCodeFor, key)) {
        this.initialCodeFor[key] = decode(this.initialCodeFor[key] || '');
      }
    }
  }
}

/// A test case inside a problem
export class TestCase {
  constructor(json) {
    console.assert(json);
    // Command line arguments to send to the user solution when running this test case
    this.commandLineArguments = decode(json?.args || '');
    // Text to send to user solution through stdin
    this.input = decode(json?.input || '');
    // Expected output
    this.output = decode(json?.output || '');
    // Expected error
    // TODO(jhc): If missing (None), allow using stderr for debug, because '' must match
    this.stderr = decode(json?.stderr || '');
    // Points that user earns if its solution matches the expected output
    this.points = json?.points || 0;
    // If true, the test case is hidden for users, so they cannot see what is in it
    this.hidden = json?.hidden || false;
    // Minimum number of threads that user solution must create in order to consider it right
    this.minThreads = json?.minThreads || 1;
    // Maximum number of threads that user solution may create to consider it correct
    this.maxThreads = json?.maxThreads || MAX_THREADS;
    // Minimum wall time duration that user solution must spent to consider it correct
    this.minDuration = json?.minDuration || 0.0;
    // Maximum wall time duration that user solution must spent to consider it correct
    // Undefined means no limit
    this.maxDuration = json?.maxDuration;
  }
}

/// Result of running a user solution against all test cases
export class ExecutionResult {
  /// This object is created by the backend after running a user solution for a problem.
  /// The json object is created by the backend and always must be provided.
  constructor(json) {
    // An enumeration value code of the global verdict. For example if all test cases pass
    // except one, the status will be 'wrong'.
    this.status = Status.parse(json?.status) || Status.PENDING;
    // A human-readable verdict emitted by the judge
    this.message = decode(json?.message || ''); // text
    // Compiler output or null if no output was generated
    this.compileOutput = decode(json?.compileOutput || ''); // text
    // Count of passed test cases
    this.passedTestCount = json?.passedTestCount || 0; // int
    // Points gained by this solution
    // TODO(jhc): Used?
    this.points = json?.points || 0; // int
    // Total points (sum of all test cases)
    this.totalPoints = json?.totalPoints || 0; // int
    // Wall time of the largest test case
    this.maxWallTime = json?.maxWallTime || -1.0; // elapsed seconds
    // Load the result of each test case
    this.results = (json?.results || []).map((result) => {
      return new TestCaseResult(result);
    });

    // TODO: Change LC_ALL=en_US in compiler environment to avoid Unicode quotes
    this.compileOutput = this.compileOutput.replace(/â/g, '‘');
  }
}

/// Result of running a test case
export class TestCaseResult {
  /// This object is created by the backend after running a the user solution of a problem.
  /// The jsonObject is created by the backend and always must be provided.
  constructor(json) {
    console.assert(json);
    // An enumeration value code of the verdict, see vyg.Status
    this.status = Status.parse(json?.status) || Status.PENDING;
    // A human-readable verdict emitted by the judge
    this.message = decode(json?.message || ''); // text
    // CPU time, i.e all threads added
    this.cpuTime = json?.cpuTime || 0.0; // elapsed seconds
    // Exit code reported by the program to the operating system after running this test case
    this.exitCode = json?.exitCode || 0; // int
    // Memory used by the process (bytes)
    this.memory = json?.memory || 0; // Used bytes
    // Text sent by the user solution to the standard output
    this.stdout = decode(json?.stdout || ''); // text
    // Text sent by the user solution to the standard error
    this.stderr = decode(json?.stderr || ''); // text
    // Number of threads created by solution for this test case
    this.threadCount = json?.threadCount || 0; // int
    // Wall time in seconds
    this.wallTime = json?.wallTime || 0.0; // elapsed seconds
    // number_of_runs?
  }
}