""" Result of running a solution against one test case """
from vyg.constants import Status
from vyg.utils import decode

# Attributes of this class are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

class TestCaseResult:
    """ Result of running a test case """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['message', 'stderr', 'stdout']
    # The name starts with Test, but pytest must not collect this class as a test suite
    __test__ = False

    def __init__(self, json_dict:dict):
        """ Construct this object getting values from the given dictionary """
        # An enumeration value code of the verdict, see vyg.Status
        self.status = Status(json_dict.get('status', Status.PASSED))
        # A human-readable verdict emitted by the judge
        self.message = decode(json_dict.get('message', ''))
        # CPU time, i.e all threads added up
        self.cpuTime = json_dict.get('cpuTime', 0.0)
        # Exit code reported by the program to the operating system after running this test case
        self.exitCode = json_dict.get('exitCode', 0)
        # Memory used by the process (bytes)
        self.memory = json_dict.get('memory', 0)
        # Text produced by the user solution in the standard error
        self.stderr = decode(json_dict.get('stderr', ''))
        # Text produced by the user solution in the standard output
        self.stdout = decode(json_dict.get('stdout', ''))
        # Number of threads created by solution for this test case
        self.threadCount = json_dict.get('threadCount', 0)
        # Elapsed wall time running this test case in seconds
        self.wallTime = json_dict.get('wallTime', 0.0)
        # TODO(jhc): number_of_runs?
