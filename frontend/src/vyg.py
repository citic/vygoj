""" Common classes for VygOJ """

import base64
import json
import os

def get_app_path():
    """ Return the path where the frontend app is located """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_problem_path():
    """ Return subfolder where programming problems are stored """
    return os.path.join(get_app_path(), 'problems')

def to_json(data_object):
    """ Convert the given Python object to JSON string """
    # See https://docs.python.org/3/library/json.html#json.dump
    return json.dumps(data_object, default=lambda obj: obj.__dict__)

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
