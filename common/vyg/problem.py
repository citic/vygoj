""" Programming problems """
from vyg.activity import Activity
from vyg.constants import MAX_THREADS
from vyg.material import Material
from vyg.testcase import TestCase

# Attributes of this class are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

# A data model with an attribute for each field of its JSON, not a class with behavior
class Problem(Activity, material_type='problem'): # pylint: disable=too-many-instance-attributes
    """ Represents a programming problem with statement, source code, and test cases """
    def __init__(self, json_dict: dict, parent: Material):
        """ Load the fields of this object from JSON dictionary """
        super().__init__(json_dict, parent)
        # Problem statement in HTML code
        # TODO(jhc): use problem.{en|es|...}.{md|adoc|html} files instead
        self.statement = json_dict.get('statement', '')
        # An array of test cases
        self.tests = Problem.load_tests(json_dict.get('tests', []))
        # The given initial source code for the problem and programming language
        self.initialCodeFor = json_dict.get('initialCodeFor', { })
        # Minimum number of secondary threads to solve the problem. If this number
        # is one or more, additional runs will be conducted for each test case
        self.minThreads = json_dict.get('minThreads', 0)
        # There is no limit for the default number of secondary threads
        self.maxThreads = json_dict.get('maxThreads', MAX_THREADS)
        # Considers valid an output that has different order than the expected
        # Supported values: 'none', 'lines'
        self.allowIndeterminism = json_dict.get('allowIndeterminism', 'none')
        # Considers invalid a solution if it does NOT contains words in this array
        self.mustContain = json_dict.get('mustContain', '')
        # Range of wall time in seconds that the solution may spend in each test case. Test cases
        # may set their own. 0 or missing in a statement means the default of the judge, and the
        # frontend sends the backend the effective values (see frontend/src/limits.py)
        self.minDuration = json_dict.get('minDuration', 0)
        self.maxDuration = json_dict.get('maxDuration', 0)
        # Maximum seconds for the whole submission: compiling and running all test cases. The
        # test cases that do not fit are not run
        self.maxTotalDuration = json_dict.get('maxTotalDuration', 0)
        # Bytes of the standard output and error of each visible test case, and of the compiler
        # output, sent back to the student. Longer outputs are truncated
        self.maxOutputSize = json_dict.get('maxOutputSize', 0)
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
        # Title in the heading that starts the statement, which the frontend takes out of it when
        # it loads the folder, e.g. 'Formateador de fecha'. Empty if the statement has none
        self.statement_title = ''

    @staticmethod
    def load_tests(json_tests):
        """ For each given test case, add it to the self.test[] array """
        tests = []
        for test in json_tests:
            tests.append(TestCase(test))
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
        # minThreads may be 'stdin' or come from untrusted JSON with any type
        if self.minThreads == 'stdin':
            return True
        return isinstance(self.minThreads, (int, float)) and self.minThreads >= 1

    def merge(self, json_dict: dict):
        """ Copy to this problem the non-empty fields of the given JSON dictionary """
        # Load the fields of this object from JSON dictionary to a new object
        problem = Problem(json_dict, self._parent)
        # Copy the fields from the loaded problem to this problem. Dictionary update does
        # not work because some fields in problem are empty and would erase existing data
        # Merge non empty properties of problem into self. An object replacement
        # is problematic because self is already referenced by parent material
        for key, value in problem.__dict__.items():
            if key[0] != '_' and value:
                setattr(self, key, value)
