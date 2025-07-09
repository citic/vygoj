""" Common classes for VygOJ backend and frontend server """
import base64
import enum
import json
import os

# Maximum number of allowed execution threads to be created by a user solution
MAX_THREADS = 2**15

class Status(str, enum.Enum):
    """ Status of the execution of a programming solution.
    The str inheritance eases the translation to and from JSON """
    PENDING = 'pending'
    PASSED = 'passed'
    WRONG = 'wrong'
    TIMEOUT = 'timeout'
    COMPILER_ERROR = 'compilerError'
    RUNTIME_ERROR = 'runtimeError'
    INTERNAL_ERROR = 'internalError'

def get_app_path():
    """ Return the path where the docker app is located """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_problem_path():
    """ Return subfolder where programming problems are stored """
    return os.path.join(get_app_path(), 'problems')

def encode(value): # :str|dict
    """ Codifies the given text to base64 in order to transport it as a JSON value """
    if isinstance(value, dict):
        return encode_dict(value)
    return str(base64.b64encode(value.encode('utf-8')))[2:-1] if value else ''

def encode_dict(json_dict:dict):
    """ Codifies the values of dictionary to base64 in order to transport it as a JSON value """
    for key in json_dict.keys():
        json_dict[key] = encode(json_dict[key])
    return json_dict

def decode(value): # :str|dict
    """ De-codifies the given text in base64 to plain text """
    if isinstance(value, dict):
        return decode_dict(value)
    return base64.b64decode(value).decode('utf-8')

def decode_dict(json_dict:dict):
    """ De-codifies the values of the given dictionary in base64 to plain text """
    for key in json_dict.keys():
        json_dict[key] = decode(json_dict[key])
    return json_dict

def decode_if(value, cond):
    """ Decodes the given value only if the condition is true """
    return decode(value) if cond else value

def prepend(text, prefix, sep = ' '):
    """ Prepends the prefix to the text separated by sep if prefix is not empty """
    return f'{prefix}{sep}{text}' if prefix else text

def append(text, suffix, sep = ' '):
    """ Appends the suffix to the text separated by sep if suffix is not empty """
    return f'{text}{sep}{suffix}' if suffix else text

def to_dict(data_object):
    """ Returns a dictionary with data attributes of obj. If the class for the obj has a
    static attribute named encoded fields, the values for those fields are encoded to
    base64 strings. The obj is not modified. """
    # If class has a static attribute encoded_fields as a list of strings (attribute names)
    if hasattr(data_object.__class__, 'encoded_fields'):
        # Build a dictionary copying only data members from the object
        encoded_dict:dict = data_object.__dict__.copy()
        # For each filed to be encoded
        for field in data_object.__class__.encoded_fields:
            # If the object has a value for the attribute
            if field in encoded_dict:
                # Encode the value of the attribute to the temporary dictionary
                encoded_dict[field] = encode(encoded_dict[field])
        # Return the temporary encoded dictionary, original is not modified
        return encoded_dict
    # No codification is needed, return the dictionary representation of the object
    return data_object.__dict__

def to_json(data_object):
    """ Convert the given Python object to JSON string """
    # See https://docs.python.org/3/library/json.html#json.dump
    return json.dumps(data_object, default=to_dict, indent=2)


class Message:
    """ All messages exchanged between the JS client and Python server are generic.
        Send { } as json_dict to init Message to empty fields """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['code', 'error']

    def __init__(self, json_dict:dict):
        """ Construct this object getting values from the given dictionary """
        # Valid actions: fetch_problem | run
        self.action = json_dict.get('action', '')
        # Used when an error happens, and the rest of the message is invalid
        self.error = decode(json_dict.get('error', ''))
        # The programming language used in field code
        self.language = json_dict.get('language', '')
        # The source code
        #self.code = base64.b64decode(json_dict.get('code', ''))
        self.code = decode(json_dict.get('code', ''))

# Attributes of these classes are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

class TestCaseResult:
    """ Result of running a test case """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['message', 'stderr', 'stdout']

    def __init__(self, json_dict:dict):
        """ Construct this object getting values from the given dictionary """
        # An enumeration value code of the verdict, see vyg.Status
        self.status = Status(json_dict.get('status', Status.PASSED))
        # A human-readable verdict emitted by the judge
        self.message = decode(json_dict.get('message', ''))
        # CPU time, i.e all threads added up
        self.cpuTime = json_dict.get('cpuTime', '')
        # Exit code reported by the program to the operating system after running this test case
        self.exitCode = json_dict.get('exitCode', 0)
        # Memory used by the process (bytes)
        self.memory = json_dict.get('memory', 0)
        # TODO(jhc): number_of_runs?
        # Text produced by the user solution in the standard error
        self.stderr = decode(json_dict.get('stderr', ''))
        # Text produced by the user solution in the standard output
        self.stdout = decode(json_dict.get('stdout', ''))
        # Number of threads created by solution for this test case
        self.threadCount = json_dict.get('threadCount', 0)
        # Elapsed wall time running this test case in seconds
        self.wallTime = json_dict.get('wallTime', '')

class ExecutionResult:
    """ Result of running student solution against all test cases """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['message', 'compileOutput']

    def __init__(self, json_dict:dict):
        """ Construct this object getting values from the given dictionary """
        # We suppose student's code solves the problem, until a test fails
        self.status = Status(json_dict.get('status', Status.PASSED))
        # A human-readable verdict emitted by the judge
        self.message = decode(json_dict.get('message', ''))
        # Compiler output or null if no output was generated
        self.compileOutput = decode(json_dict.get('compileOutput', ''))
        # Count of passed test cases
        self.passedTestCount = json_dict.get('passedTestCount', 0)
        # Points gained by this solution
        # TODO(jhc): used?
        self.points = json_dict.get('points', 0)
        # Total points (sum of all test cases)
        self.totalPoints = json_dict.get('totalPoints', 0)
        # Wall time of the largest test case
        self.maxWallTime = json_dict.get('maxWallTime', -1.0)
        # Results of each test case
        self.results:TestCaseResult = []
        for test_result_json in json_dict.get('results', []):
            self.results.append(TestCaseResult(test_result_json))

class TestCase:
    """ A test case for black-box testing provides the input data to run a user solution code,
        and compare its output against the expected output. If they match, user gain points. """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['args', 'input', 'output', 'error']

    def __init__(self, json_dict:dict, should_decode=True):
        """ Construct this object getting values from the given dictionary """
        # Command line arguments
        self.commandLineArguments = decode_if(json_dict.get('args', ''), should_decode)
        # Text to send to user solution through stdin
        self.input = decode_if(json_dict.get('input', ''), should_decode)
        # Expected output
        self.output = decode_if(json_dict.get('output', ''), should_decode)
        # Expected error
        # TODO(jhc): If missing (None), allow using stderr for debug, '' must match
        self.stderr = decode_if(json_dict.get('error', ''), should_decode)
        # Points that user earn if its solution matches the expected output
        self.points = json_dict.get('points', 0)
        # If true, the test case is hidden for users, so they cannot see what is in it
        self.hidden = json_dict.get('hidden', False)
        # Minimum number of threads that user solution must create in order to consider it right
        self.minThreads = json_dict.get('minThreads', 1)
        # Maximum number of threads that user solution may create to consider it correct
        self.maxThreads = json_dict.get('maxThreads', MAX_THREADS)
        # Minimum wall time duration that user solution must spent to consider it correct
        self.minDuration = json_dict.get('minDuration')
        # Maximum wall time duration that user solution must spent to consider it correct
        self.maxDuration = json_dict.get('maxDuration')

class Problem:
    """ Represents a programming problem with statement, source code, and test cases """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['title', 'statement', 'mustContain', 'initialCodeFor']

    def __init__(self, relative_path:str, json_dict: dict, should_decode = True):
        """ Load the fields of this object from JSON dictionary, relative_path is just stored """
        # The relative path that identifies the problem
        self.relative_path = relative_path
        # An identifier name for the problem, eg "uint64_adder"
        self.name = json_dict.get('name', '')
        # Title describing the problem, eg "Unsigned 64-bits adder"
        self.title = decode_if(json_dict.get('title', ''), should_decode)
        # Problem statement in HTML code
        # TODO(jhc): use problem.{en|es|...}.{md|adoc|html} files instead
        self.statement = decode_if(json_dict.get('statement', ''), should_decode)
        # An array of test cases
        self.tests = Problem.load_tests(json_dict.get('tests', []), should_decode)
        # Allowed programming languages for this problem
        self.languages = json_dict.get('languages', [])
        # The given initial source code for the problem and programming language
        self.initialCodeFor = decode_if(json_dict.get('initialCodeFor', { }), should_decode)
        # Minimum number of secondary threads to solve the problem. If this number
        # is one or more, additional runs will be conducted for each test case
        self.minThreads = json_dict.get('minThreads', 0)
        # There is no limit for the default number of secondary threads
        self.maxThreads = json_dict.get('maxThreads', MAX_THREADS)
        # Considers valid an output that has different order than the expected
        # Supported values: 'none', 'lines'
        self.allowIndeterminism = json_dict.get('allowIndeterminism', 'none')
        # Considers invalid a solution if it does NOT contains words in this array
        self.mustContain = decode_if(json_dict.get('mustContain', ''), should_decode)
        # Allowed time range in seconds specified by professor for all test cases
        self.minDuration = json_dict.get('minDuration', '')
        # Maximum wall time duration that user solution must spent to consider it correct
        self.maxDuration = json_dict.get('maxDuration')
        # Extra tools, one of: asan tsan ubsan memcheck helgrind
        self.tools = json_dict.get('tools', '')
        # Remove HTML escaping for all languages
        # for lang, code in self.initialCodeFor.items():
        #     code = code.replace('&amp;', '&')
        #     code = code.replace('&lt;', '<')
        #     code = code.replace('&gt;', '>')
        #     self.initialCodeFor[lang] = code

    @staticmethod
    def load_tests(json_tests, should_decode=True):
        """ For each given test case, add it to the self.test[] array """
        tests = []
        for test in json_tests:
            tests.append(TestCase(test, should_decode))
        return tests

    @staticmethod
    def load(problem_path:str):
        """ Creates a new Problem object from the given relative path problem eg: uint64_adder """
        # Problems are stored in data/path/vygoj.json
        abs_path = f'{get_problem_path()}/{problem_path}/vygoj.json'
        # Read the contents of the file
        with open(abs_path, encoding='utf8') as file:
            # Load the fields from the json file
            json_dict = json.load(file)
            # Do not decode problems when loaded from files, they are create manually (for now)
            return Problem(problem_path, json_dict, should_decode=False)
        raise RuntimeError(f'could not find problem {problem_path}')

    def calculate_total_points(self):
        """ Calculates the total amount of points from the test cases """
        total = 0
        for test in self.tests:
            # If test has no a points property, we use 0
            total += test.points
        return total

    def has_proofs(self):
        """ Returns true if this problem requires the solution to pass extra proofs """
        return self.minThreads >= 1

# pylint: enable=invalid-name
