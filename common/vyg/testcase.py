""" Test cases of programming problems """
from vyg.constants import MAX_THREADS
from vyg.utils import decode_if

# Attributes of this class are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

class TestCase:
    """ A test case for black-box testing provides the input data to run a user solution code,
        and compare its output against the expected output. If they match, user gain points. """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['args', 'input', 'output', 'error']
    # The name starts with Test, but pytest must not collect this class as a test suite
    __test__ = False

    def __init__(self, json_dict:dict, should_decode=True):
        """ Construct this object getting values from the given dictionary """
        # Command line arguments to send to the user solution when running this test case
        self.commandLineArguments = decode_if(json_dict.get('args', ''), should_decode)
        # Text to send to user solution through stdin
        self.input = decode_if(json_dict.get('input', ''), should_decode)
        # Expected output
        self.output = decode_if(json_dict.get('output', ''), should_decode)
        # Expected error
        # TODO(jhc): If missing (None), allow using stderr for debug, because '' must match
        self.stderr = decode_if(json_dict.get('error', ''), should_decode)
        # Points that user earns if its solution matches the expected output
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
