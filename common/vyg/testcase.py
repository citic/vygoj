""" Test cases of programming problems """
from vyg.constants import MAX_THREADS

# Attributes of this class are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

class TestCase:
    """ A test case for black-box testing provides the input data to run a user solution code,
        and compare its output against the expected output. If they match, user gain points. """
    # The name starts with Test, but pytest must not collect this class as a test suite
    __test__ = False

    def __init__(self, json_dict:dict):
        """ Construct this object getting values from the given dictionary. Its keys are the names
        of the attributes, as to_dict() writes them, so test cases arrive complete to the backend
        and to the client """
        # Command line arguments to send to the user solution when running this test case. They are
        # split as a shell would, e.g: 'a "b c"' are two arguments
        self.args = json_dict.get('args', '')
        # Text to send to user solution through its standard input
        self.stdin = json_dict.get('stdin', '')
        # Expected standard output
        self.stdout = json_dict.get('stdout', '')
        # Expected standard error
        # TODO(jhc): If missing (None), allow using stderr for debug, because '' must match
        self.stderr = json_dict.get('stderr', '')
        # Points that user earns if its solution matches the expected output
        self.points = json_dict.get('points', 0)
        # If true, the test case is hidden for users, so they cannot see what is in it
        self.hidden = json_dict.get('hidden', False)
        # Minimum number of threads that user solution must create in order to consider it right
        self.minThreads = json_dict.get('minThreads', 1)
        # Maximum number of threads that user solution may create to consider it correct
        self.maxThreads = json_dict.get('maxThreads', MAX_THREADS)
        # Range of wall time in seconds that the solution may spend in this test case. 0 or missing
        # means the range of the problem
        self.minDuration = json_dict.get('minDuration', 0)
        self.maxDuration = json_dict.get('maxDuration', 0)
