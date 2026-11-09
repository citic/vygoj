""" Limits of the code runs. The administrator of the judge sets them in config.py: each constraint
has an absolute range (ABS_MIN_*, ABS_MAX_*) and a default (DEF_*). Professors may choose a value
in a problem or a test case; it is clamped to the range, and missing or 0 means the default. The
backend receives the effective values in the problem, so it only receives a problem and a solution
"""
import math

from flask import current_app as app

import vyg

# Fields of problems bounded by the limits, and the name of their range in config.py. The default
# of a field is DEF_ with MIN or MAX (its prefix) and the range, e.g: DEF_MAX_RUN_DURATION
CONSTRAINED_FIELDS = {
    'minDuration': 'RUN_DURATION',
    'maxDuration': 'RUN_DURATION',
    'maxTotalDuration': 'TOTAL_DURATION',
    'maxOutputSize': 'OUTPUT_SIZE',
}
# Fields that a test case may set for itself. Missing or 0 means the effective value of the problem
TEST_FIELDS = ('minDuration', 'maxDuration')

# Values used when config.py does not set them. config/config-example.py explains each one.
# Defaults (DEF_*) may be a number, or a dictionary with a number for each language
DEFAULTS = {
    'ABS_MIN_RUN_DURATION': 0,
    'ABS_MAX_RUN_DURATION': 10,
    'DEF_MIN_RUN_DURATION': 0,
    'DEF_MAX_RUN_DURATION': 2,
    'ABS_MIN_TOTAL_DURATION': 0,
    'ABS_MAX_TOTAL_DURATION': 60,
    'DEF_MAX_TOTAL_DURATION': 30,
    'ABS_MIN_OUTPUT_SIZE': 0,
    'ABS_MAX_OUTPUT_SIZE': 10 * 1024,
    'DEF_MAX_OUTPUT_SIZE': 10 * 1024,
}

# Seconds to connect to a backend
BACKEND_CONNECT_TIMEOUT = 5
# Seconds that a backend may answer after the maxTotalDuration of the submission: it creates and
# removes the container, and stops the last command. Longer than DEADLINE_GRACE in
# backend/src/execution.py
BACKEND_GRACE = 30
# Extra seconds that the browser waits for the frontend, beyond the frontend waiting the backend
CLIENT_GRACE = 10


class Limits:
    """ Effective limits of the runs, from config.py and the values chosen by professors """

    @staticmethod
    def setting(name: str):
        """ Return the value of the setting of config.py, or its default """
        return app.config.get(name, DEFAULTS[name])

    @staticmethod
    def check_config(config: dict):
        """ Raise RuntimeError if a limit in config.py is not valid, so the server does not start
        with limits that would fail every run """
        for range_name in set(CONSTRAINED_FIELDS.values()):
            low = config.get(f'ABS_MIN_{range_name}', DEFAULTS[f'ABS_MIN_{range_name}'])
            high = config.get(f'ABS_MAX_{range_name}', DEFAULTS[f'ABS_MAX_{range_name}'])
            if not Limits.is_number(low) or not Limits.is_number(high) or not 0 <= low <= high:
                raise RuntimeError(f'ABS_MIN_{range_name} and ABS_MAX_{range_name} in config.py '
                    'must be numbers with 0 <= min <= max')
        for field in CONSTRAINED_FIELDS:
            name = Limits.default_name(field)
            default = config.get(name, DEFAULTS[name])
            values = default.values() if isinstance(default, dict) else [default]
            if not all(Limits.is_number(value) for value in values):
                raise RuntimeError(f'{name} in config.py must be a number, or a dictionary with a '
                    'number for each language')
        if config.get('ABS_MAX_TOTAL_DURATION', DEFAULTS['ABS_MAX_TOTAL_DURATION']) <= 0:
            raise RuntimeError('ABS_MAX_TOTAL_DURATION in config.py must be greater than 0')

    @staticmethod
    def is_number(value) -> bool:
        """ True if value is a finite number. Values of course repos may have any JSON type """
        return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value))

    @staticmethod
    def default_name(field: str) -> str:
        """ Return the name of the setting with the default of the field, e.g: DEF_MAX_RUN_DURATION
        for maxDuration """
        return f'DEF_{field[:3].upper()}_{CONSTRAINED_FIELDS[field]}'

    @staticmethod
    def bound(field: str, value, default):
        """ Return the value chosen by a professor for the field, or default if it is missing, 0,
        or not a number, clamped to the absolute range of the field """
        if not Limits.is_number(value) or not value:
            value = default
        range_name = CONSTRAINED_FIELDS[field]
        low = Limits.setting(f'ABS_MIN_{range_name}')
        high = Limits.setting(f'ABS_MAX_{range_name}')
        return min(max(value, low), high)

    @staticmethod
    def default(field: str, language: str):
        """ Return the default of the field for the programming language """
        default = Limits.setting(Limits.default_name(field))
        if isinstance(default, dict):
            # A language without an entry gets the absolute bound of the side of the field
            side = 'MIN' if field.startswith('min') else 'MAX'
            return default.get(language, Limits.setting(f'ABS_{side}_{CONSTRAINED_FIELDS[field]}'))
        return default

    @staticmethod
    def effective_problem(problem: vyg.Problem, language: str) -> dict:
        """ Return the effective value of each constrained field of the problem for a solution in
        the language. Fields whose value is 0 are not included, as in to_dict() """
        limits = { field: Limits.bound(field, getattr(problem, field, 0),
            Limits.default(field, language)) for field in CONSTRAINED_FIELDS }
        # The output limit is a count of bytes
        limits['maxOutputSize'] = int(limits['maxOutputSize'])
        return { field: value for field, value in limits.items() if value }

    @staticmethod
    def effective_test(test: vyg.TestCase, problem_limits: dict) -> dict:
        """ Return the test case as a dictionary with its effective time range: its own values, or
        the ones of the problem """
        test_dict = vyg.to_dict(test)
        for field in TEST_FIELDS:
            value = Limits.bound(field, test_dict.get(field), problem_limits.get(field, 0))
            if value:
                test_dict[field] = value
            else:
                test_dict.pop(field, None)
        return test_dict

    @staticmethod
    def backend_timeout(problem_dict: dict) -> tuple:
        """ Return the (connect, read) timeouts in seconds to wait for the backend to judge the
        problem with its effective limits """
        return (BACKEND_CONNECT_TIMEOUT, problem_dict['maxTotalDuration'] + BACKEND_GRACE)

    @staticmethod
    def max_backend_wait() -> float:
        """ Return the longest time in seconds that the frontend waits for any run """
        return (BACKEND_CONNECT_TIMEOUT + Limits.setting('ABS_MAX_TOTAL_DURATION')
            + BACKEND_GRACE)

    @staticmethod
    def client_run_timeout() -> float:
        """ Return the seconds that the browser waits for the answer of a run. It is longer than
        the frontend waits for the backend, so the frontend always answers first """
        return Limits.max_backend_wait() + CLIENT_GRACE
