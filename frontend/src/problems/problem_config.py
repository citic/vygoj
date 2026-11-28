""" Configuration file of a problem folder: an object with fields of vyg.Problem, e.g.
{"title": "Dining philosophers", "maxDuration": 2.0, "tools": "helgrind lint"}. The fields of
PROBLEM_FIELDS are checked, and a wrong value is skipped with a warning, without the other fields.
Fields that set what the problem is in its course (FIXED_FIELDS) are skipped with a warning, and
other fields are ignored: they are data of other tools, e.g. authors or concepts.

tests may be a list of complete test cases, or an object that sets fields of the test cases of the
files of the tests folder: 'default' for all of them, and the number of a test case for its own,
e.g. {"default": {"points": 1}, "004": {"points": 3, "hidden": true}} """

import re
import sys

import vyg
from config_file import ConfigFile

def _text(value):
    """ Return the value if it is a string. Raise ValueError otherwise """
    if not isinstance(value, str):
        raise ValueError(value)
    return value

def _flag(value):
    """ Return the value if it is a boolean. Raise ValueError otherwise """
    if not isinstance(value, bool):
        raise ValueError(value)
    return value

def _integer(value):
    """ Return the value if it is an integer. Raise ValueError otherwise """
    # bool is a subclass of int in Python, but true is not a number in JSON
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(value)
    return value

def _number(value):
    """ Return the value if it is a finite integer or real number. Raise ValueError otherwise """
    # JSON of Python and YAML accept NaN and the infinities, and integers too large for a float.
    # Comparing with the largest float rejects them all
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not abs(value) <= sys.float_info.max):
        raise ValueError(value)
    return value

def _points(value):
    """ Return the value if it is a number of points of a test case, from -MAX_POINTS to
    MAX_POINTS. Raise ValueError otherwise """
    # NaN fails every comparison, so it is rejected too
    if not -vyg.MAX_POINTS <= _number(value) <= vyg.MAX_POINTS:
        raise ValueError(value)
    return value

def _texts(value):
    """ Return the value if it is a list of strings. Raise ValueError otherwise """
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(value)
    return value

def _languages(value):
    """ Return the names of the languages of the value, if it is a list of strings, e.g.
    ['cpp', 'python'] is ['C++', 'Python']. Raise ValueError otherwise """
    return [vyg.LANGUAGE_NAMES.get(language.lower(), language) for language in _texts(value)]

def _words(value):
    """ Return the value as words separated by spaces, if it is a string or a list of strings,
    e.g. ['asan', 'lint'] is 'asan lint'. Raise ValueError otherwise """
    return value if isinstance(value, str) else ' '.join(_texts(value))

def _codes(value):
    """ Return the value if it is an object of strings, e.g. the initial code of each language,
    with the keys that are extensions or names of languages in any case as their names, as
    _languages() does. Raise ValueError otherwise """
    if not isinstance(value, dict) or not all(isinstance(item, str) for item in value.values()):
        raise ValueError(value)
    return { vyg.LANGUAGE_NAMES.get(str(key).lower(), str(key)): code
        for key, code in value.items() }

def _threads(value):
    """ Return the value if it is an integer or 'stdin' (the number is in the standard input).
    Raise ValueError otherwise """
    return value if value == 'stdin' else _integer(value)

def _date(value):
    """ Return the value if it is a string or a number (weeks). Raise ValueError otherwise """
    return value if isinstance(value, str) else _number(value)

def _choice(*options):
    """ Return a function that returns its value if it is one of the options """
    def check(value):
        if value not in options:
            raise ValueError(value)
        return value
    return check

# Fields of a problem that its configuration file may set, with the kind of their values, which
# warnings tell, and the function that checks them. tests is checked apart
PROBLEM_FIELDS = {
    'title': ('text', _text),
    'statement': ('text', _text),
    'languages': ('texts', _languages),
    'initialCodeFor': ('codes', _codes),
    'minThreads': ('threads', _threads),
    'maxThreads': ('integer', _integer),
    'allowIndeterminism': ('none_lines', _choice('none', 'lines')),
    'mustContain': ('texts', _texts),
    'minDuration': ('number', _number),
    'maxDuration': ('number', _number),
    'maxTotalDuration': ('number', _number),
    'maxOutputSize': ('number', _number),
    'tools': ('words', _words),
    'start': ('date', _date),
    'finish': ('date', _date),
    'weight': ('number', _number),
    'overdue_policy': ('overdue_policy', _choice('hidden', 'disabled', 'half')),
}

# Fields of a test case that the configuration file may set, as PROBLEM_FIELDS
TEST_FIELDS = {
    'args': ('text', _text),
    'stdin': ('text', _text),
    'stdout': ('text', _text),
    'stderr': ('text', _text),
    'points': ('points', _points),
    'hidden': ('flag', _flag),
    'minThreads': ('integer', _integer),
    'maxThreads': ('integer', _integer),
    'minDuration': ('number', _number),
    'maxDuration': ('number', _number),
}

# Fields that the course sets: the folder of a problem cannot change its name, place, or type
FIXED_FIELDS = ('type', 'folder', 'name', 'contents')

# Key of tests with the fields of all the test cases of the files of the tests folder
DEFAULT_TEST = 'default'
# Number of a test case in tests, as in its files, e.g. 004 for input004.txt. ASCII digits only,
# and a few of them, so int() never fails
TEST_NUMBER = re.compile(r'[0-9]{1,9}')

class ProblemConfig(ConfigFile):
    """ The configuration file of a problem folder """

    def __init__(self, root: str):
        super().__init__(root)
        # Fields of the test cases of the tests folder, by their number, e.g. {'004': {...}}, and
        # the ones of all of them in DEFAULT_TEST
        self.test_settings = {}
        # Numbers of test_settings whose test case was found by test_fields()
        self.used_numbers = set()
        # Languages that the problem supports, which the problem loader combines with the ones of
        # the course, or empty if the file has none
        self.languages = []

    def interpret(self, data: dict) -> dict:
        """ Return the valid fields of the problem in the object of the file, to merge them into
        the problem. The settings of the test cases of files go to test_settings, and the languages
        to languages """
        fields = {}
        for field, value in data.items():
            if field in FIXED_FIELDS:
                self.warn('fixed_field', field=field)
            elif field == 'tests':
                self.interpret_tests(value, fields)
            elif field in PROBLEM_FIELDS:
                checked = self.check(PROBLEM_FIELDS[field], value, field=field)
                # The problem loader combines the languages with the ones of the course
                if field == 'languages' and checked is not None:
                    self.languages = self.known_languages(checked)
                elif checked is not None:
                    fields[field] = checked
        return fields

    def known_languages(self, names: list) -> list:
        """ Return the names that are languages of VygOJ, with a warning for the others, e.g. a
        typo, which would break the problem page """
        unknown = [name for name in names if name not in vyg.EXTENSION_LANGUAGES]
        if unknown:
            self.warn('unknown_languages', languages=', '.join(unknown))
        return [name for name in names if name in vyg.EXTENSION_LANGUAGES]

    def check(self, kind: tuple, value, **params):
        """ Return the value checked by the function of its kind (name, function), or None with a
        warning if it is not valid """
        name, check = kind
        try:
            return check(value)
        except ValueError:
            code = 'invalid_test_field' if 'test' in params else 'invalid_field'
            self.warn(code, kind=name, **params)
            return None

    def interpret_tests(self, tests, fields: dict):
        """ Put a list of complete test cases in the fields of the problem, or else an object of
        settings in test_settings """
        if isinstance(tests, list):
            checked = (self.check_test(test, str(index)) for index, test in enumerate(tests, 1))
            fields['tests'] = [test for test in checked if test is not None]
        elif isinstance(tests, dict):
            for number, test in tests.items():
                if number != DEFAULT_TEST and not TEST_NUMBER.fullmatch(number):
                    self.warn('invalid_test_key', test=number)
                    continue
                # A number without fields (004: in YAML) changes nothing
                checked = self.check_test({} if test is None else test, number)
                if checked is not None:
                    self.test_settings[number] = checked
        else:
            self.warn('invalid_field', field='tests', kind='tests')

    def check_test(self, test, number: str) -> dict | None:
        """ Return the valid fields of the test case, or None with a warning if it is not an
        object """
        if not isinstance(test, dict):
            self.warn('invalid_test', test=number)
            return None
        checked = {}
        for field, value in test.items():
            if field in TEST_FIELDS:
                value = self.check(TEST_FIELDS[field], value, test=number, field=field)
                if value is not None:
                    checked[field] = value
        return checked

    def test_fields(self, number: str) -> dict:
        """ Return the settings of the test case of the given number of its files (e.g. '004'):
        the default ones, replaced by its own. Numbers are compared as integers, so '4' is '004' """
        fields = dict(self.test_settings.get(DEFAULT_TEST, {}))
        for key, settings in self.test_settings.items():
            if key != DEFAULT_TEST and int(key) == int(number):
                fields.update(settings)
                self.used_numbers.add(key)
        return fields

    def warn_unused_tests(self):
        """ Warn about the settings of test cases whose files test_fields() did not find """
        for key in self.test_settings:
            if key != DEFAULT_TEST and key not in self.used_numbers:
                self.warn('unknown_test', test=key)
