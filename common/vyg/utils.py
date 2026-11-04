""" Helper functions for encoding and serialization """
import base64
import copy
import json


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
    """ Returns a dictionary with data attributes of data_object. If the class for the data_object
    has a static attribute named encoded fields, the values for those fields are encoded to
    base64 strings. The data_object is not modified. """
    # By the default, return the direct dictionary representation of the object
    # Because it may be modified, we make a copy to preserve the original object intact
    result = copy.deepcopy(data_object.__dict__)
    # Do not export to JSON private non-serializable attributes (starts with _) or are empty
    # Traverse original dictionary because copy will be modified
    for field in data_object.__dict__:
        if field.startswith('_') or not result[field]:
            del result[field]
    # If class has a static attribute encoded_fields as a list of strings (attribute names)
    if hasattr(data_object.__class__, 'encoded_fields'):
        # For each field to be encoded
        for field in data_object.__class__.encoded_fields:
            # If the object has a value for the attribute
            if field in result:
                # Encode the value of the attribute to the temporary dictionary
                if isinstance(result[field], dict):
                    # The field contains a dictionary, but only its values must be encoded
                    for key in result[field].keys():
                        result[field][key] = encode(result[field][key])
                else:
                    result[field] = encode(result[field])
    # Return the dictionary that will be converted to JSON
    return result

def to_json(data_object):
    """ Convert the given Python object to JSON string """
    # See https://docs.python.org/3/library/json.html#json.dump
    return json.dumps(data_object, default=to_dict, indent=2)
