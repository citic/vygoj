""" Programming problems """
from vyg.activity import Activity
from vyg.constants import MAX_THREADS
from vyg.material import Material
from vyg.testcase import TestCase
from vyg.utils import decode_if

# Attributes of this class are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

class Problem(Activity):
    """ Represents a programming problem with statement, source code, and test cases """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = Material.encoded_fields + ['statement', 'mustContain', 'initialCodeFor']

    def __init__(self, json_dict: dict, parent: Material, should_decode: bool):
        """ Load the fields of this object from JSON dictionary """
        super().__init__(json_dict, parent, should_decode)
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
        # True when the frontend already loaded the files of the problem folder
        self.folder_loaded = False

    @staticmethod
    def load_tests(json_tests, should_decode=True):
        """ For each given test case, add it to the self.test[] array """
        tests = []
        for test in json_tests:
            tests.append(TestCase(test, should_decode))
        return tests

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

    def merge(self, json_dict: dict, should_decode: bool):
        """ Copy to this problem the non-empty fields of the given JSON dictionary """
        # Load the fields of this object from JSON dictionary to a new object
        problem = Problem(json_dict, self._parent, should_decode)
        # Copy the fields from the loaded problem to this problem. Dictionary update does
        # not work because some fields in problem are empty and would erase existing data
        # Merge non empty properties of problem into self. An object replacement
        # is problematic because self is already referenced by parent material
        for key, value in problem.__dict__.items():
            if key[0] != '_' and value:
                setattr(self, key, value)
