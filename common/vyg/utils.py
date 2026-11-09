""" Helper functions for texts and serialization """
import json


def prepend(text, prefix, sep = ' '):
    """ Prepends the prefix to the text separated by sep. The separator is not added if the text
    or the prefix is empty """
    if not text or not prefix:
        return text or prefix
    return f'{prefix}{sep}{text}'

def append(text, suffix, sep = ' '):
    """ Appends the suffix to the text separated by sep. The separator is not added if the text
    or the suffix is empty """
    if not text or not suffix:
        return text or suffix
    return f'{text}{sep}{suffix}'

def to_dict(data_object):
    """ Returns a dictionary with the public, non-empty data attributes of data_object, to be
    converted to JSON. Texts travel as they are: JSON strings carry any Unicode character. The
    data_object is not modified """
    # Private attributes (start with _) are not serializable, e.g. the parent of a material
    # references the whole course. Empty values are skipped to make messages shorter; readers use
    # the same defaults. The dictionary is new, but its values are shared with the object: callers
    # must replace them, not modify them
    return {field: value for field, value in data_object.__dict__.items()
        if not field.startswith('_') and value}

def to_json(data_object):
    """ Convert the given Python object to a compact JSON string, without spaces or indentation,
    because it travels between servers and to the browser, and it is stored in logs """
    # See https://docs.python.org/3/library/json.html#json.dump
    return json.dumps(data_object, default=to_dict, separators=(',', ':'))
