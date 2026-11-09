""" Helper functions for texts and serialization """
import json

from vyg.constants import Status


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

def summarize_result(result_json: str, test_fields: tuple) -> dict:
    """ Return the fields of the ExecutionResult in JSON that logs keep: its status, the count of
    passed test cases, and the given fields of each test case (e.g. status and wallTime). Outputs
    are not kept. Empty if there is no result or it is not valid """
    try:
        result = json.loads(result_json) if result_json else None
    except ValueError:
        return {}
    if not isinstance(result, dict) or not isinstance(result.get('results', []), list):
        return {}
    tests = [test for test in result.get('results', []) if isinstance(test, dict)]
    return {
        'status': result.get('status', Status.PASSED.value),
        'passed': result.get('passedTestCount', 0),
        # Status is always kept, it is omitted in JSON when it is passed (the default)
        'tests': [{ field: test.get(field, Status.PASSED.value if field == 'status' else None)
            for field in test_fields if field == 'status' or field in test } for test in tests],
    }
