""" Generic message exchanged between the JS client and the Python servers """
from vyg.utils import decode


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
        self.code = decode(json_dict.get('code', ''))
