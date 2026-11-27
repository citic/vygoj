""" Helper functions for texts and serialization """
import json
import re

from vyg.constants import (EXTENSION_LANGUAGES, MAX_SOLUTION_BYTES, MAX_SOLUTION_FILES,
    SOLUTION_EXTENSIONS, Status)

# Names of the files of a solution: no folders, spaces, or dots but the one of the extension, so
# they are safe file names in the container, the logs, and the student repo. They never start with
# -, so commands such as gcc do not take them as options
SOLUTION_FILE_PATTERN = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,63}\.([a-z]{1,8})')


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

def solution_files_error(files, language: str) -> str:
    """ Return why the files of a solution, {name: code} as they come in JSON, are not valid for
    the language, or an empty text if they are valid. The first file is the main file, which the
    student names, with the extension of the language (e.g. tree.c) """
    if not isinstance(files, dict) or not files:
        return 'Missing source code'
    if len(files) > MAX_SOLUTION_FILES:
        return f'A solution has at most {MAX_SOLUTION_FILES} files'
    extensions = SOLUTION_EXTENSIONS.get(language, ())
    for index, (name, code) in enumerate(files.items()):
        match = SOLUTION_FILE_PATTERN.fullmatch(name)
        if not match or (match[1] != EXTENSION_LANGUAGES.get(language) if index == 0
                else match[1] not in extensions):
            return f'Invalid file name for {language}: {name[:64]}'
        if not isinstance(code, str):
            return 'Invalid source code'
    size = sum(len(code.encode('utf-8')) for code in files.values())
    # Names that differ only in case would be the same file in zips opened in Windows or macOS
    same_names = len({name.lower() for name in files}) < len(files)
    return ('Two files have the same name' if same_names
        else f'Source code exceeds {MAX_SOLUTION_BYTES} bytes' if size > MAX_SOLUTION_BYTES else '')

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
