""" Result of running a solution against all test cases """
from vyg.constants import Status
from vyg.testcase_result import TestCaseResult

# Attributes of this class are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

class ExecutionResult:
    """ Result of running student solution against all test cases """

    def __init__(self, json_dict:dict):
        """ Construct this object getting values from the given dictionary """
        # We suppose student's code solves the problem, until a test fails
        self.status = Status(json_dict.get('status', Status.PASSED))
        # A human-readable verdict emitted by the judge
        self.message = json_dict.get('message', '')
        # Compiler output or null if no output was generated
        self.compileOutput = json_dict.get('compileOutput', '')
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
