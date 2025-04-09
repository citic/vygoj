""" Common classes for VygOJ backend and frontend server """
import base64
import enum
import json
import os

# Maximum number of allowed execution threads to be created by a user solution
MAX_THREADS = 2**15
# Maximum time allowed to a user solution to run in seconds
MAX_DURATION = 10 # seconds

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

def to_json(data_object):
    """ Convert the given Python object to JSON string """
    # See https://docs.python.org/3/library/json.html#json.dump
    # TODO(jhc): Check if Flask provides automatic dict-to-json conversion
    return json.dumps(data_object, default=lambda obj: obj.__dict__)

def encode(text:str):
    """ Codifies the given text to base64 in order to transport it as a JSON value """
    return str(base64.b64encode(text))

def decode(text:str):
    """ De-codifies the given text in base64 to plain text """
    return str(base64.b64decode(text))

class Message:
    """ All mMessages exchanged between the JS client and Python server are generic.
        Send { } as json_dict to init Message to empty fields """
    def __init__(self, json_dict:dict):
        # Valid actions: fetch_problem | run
        self.action = json_dict.get('action', '')
        # Used when an error happens, and the rest of the message is invalid
        self.error = json_dict.get('error', '')
        # The programming language used in field code
        self.language = json_dict.get('language', '')
        # The source code
        #self.code = base64.b64decode(json_dict.get('code', ''))
        self.code = json_dict.get('code', '')

# Attributes of these classes are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

class ExecutionResult:
    """ Result of running student solution against all test cases """
    def __init__(self):
        # Count of passed test cases
        self.passedTestCount = 0
        # Points gained by this solution
        self.points = 0
        # Total points (sum of all test cases)
        self.totalPoints = 0
        # Wall time of the largest test case
        self.maxWallTime = float('-inf')
        # Results of each test case
        self.results = [] # TestCaseResult[]

class TestCase:
    """
    A test case for black-box testing provides the input data to run a user solution code,
    and compare its output against the expected output. If they match, user gain points.
    """
    def __init__(self, json_dict:dict):
        # Text to send to user solution through stdin
        self.input = json_dict.get('input', '')
        # Expected output
        self.output = json_dict.get('output', '')
        # Points that user earn if its solution matches the expected output
        self.points = json_dict.get('points', 0)
        # If true, the test case is hidden for users, so they cannot see what is in it
        self.hidden = json_dict.get('hidden', False)
        # Minimum number of threads that user solution must create in order to consider it right
        self.minThreads = json_dict.get('minThreads', 1)
        # Maximum number of threads that user solution may create to consider it correct
        self.maxThreads = json_dict.get('maxThreads', MAX_THREADS)
        # Minimum wall time duration that user solution must spent to consider it correct
        self.minDuration = json_dict.get('minDuration', 0)
        # Maximum wall time duration that user solution must spent to consider it correct
        self.maxDuration = json_dict.get('maxDuration', MAX_DURATION)

class Problem:
    """ Represents a programming problem with statement, source code, and test cases """
    def __init__(self, relative_path:str, json_dict: dict):
        """Load the fields of this object from the given JSON file path"""
        # The relative path that identifies the problem
        self.relative_path = relative_path
        # An identifier name for the problem, eg "uint64_adder"
        self.name = json_dict.get('name')
        # Title describing the problem, eg "Unsigned 64-bits adder"
        self.title = json_dict.get('title')
        # Problem statement in HTML code
        # TODO(jhc): use problem.{en|es|...}.{md|adoc|html} files instead
        self.statement = json_dict.get('statement')
        # An array of test cases
        # TODO(jhc): Convert to an array of TestCase[]
        self.tests = Problem.load_tests(json_dict.get('tests', []))
        # TODO(jhc): enabled programming languages, e.g: c,cpp,py,...
        # Allowed programming languages for this problem
        self.languages = json_dict.get('languages', [])
        # The given initial source code for the problem and programming language
        self.initialCodeFor = json_dict.get('initialCodeFor', { })
        # Minimum number of secondary threads to solve the problem. If this number
        # is one or more, additional runs will be conducted for each test case
        self.minThreads = json_dict.get('minThreads', 0)
        # There is no limit for the default number of secondary threads
        self.maxThreads = json_dict.get('maxThreads', MAX_THREADS)
        # Considers valid an output that has different order than the expected
        # Supported values: 'lines'
        self.allowIndeterminism = json_dict.get('allowIndeterminism')
        # Considers invalid a solution if it does NOT contains words in this array
        self.mustContain = json_dict.get('mustContain')
        # Allowed time range in seconds specified by professor for all test cases
        self.minDuration = json_dict.get('minDuration')
        self.maxDuration = json_dict.get('maxDuration')
        # Remove HTML escaping for all languages
        for lang, code in self.initialCodeFor.items():
            code = code.replace('&amp;', '&')
            code = code.replace('&lt;', '<')
            code = code.replace('&gt;', '>')
            self.initialCodeFor[lang] = code

    @staticmethod
    def load_tests(json_tests):
        """ For each given test case, add it to the self.test[] array """
        tests = []
        for test in json_tests:
            tests.append(TestCase(test))
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
            return Problem(problem_path, json_dict)

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
