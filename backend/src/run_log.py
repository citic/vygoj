""" Log of the submissions that the backend receives, with their verdicts and the resources that
their test cases used. It is a vyg.TsvLog, as the activity log of the frontend: a TSV file per month
in data/log/ (next to the logs of gunicorn) with fixed columns and the other fields of each event
as JSON in the data column, and the code of each submission in data/log/code/<hash>.<ext>:

    data/log/runs-2026-11.tsv
    data/log/code/<hash>.cpp

The frontend sends a context with each submission: the id of the run in its activity log (the id
column here, which joins both logs), the user, their role and address, the course, the material,
and the commit of the course repo. The backend does not use the context to judge. See "Run log" in
readme.adoc """
import hashlib
import os

import flask

import vyg

# Folder of the log: data/log of the backend, where make server writes the logs of gunicorn
LOG_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data',
    'log')

# Columns of the log files, in order. Empty cells are values that do not apply or that the frontend
# did not send:
#   time: date and time in UTC, ISO 8601 with milliseconds, e.g. 2026-11-08T14:03:12.345+00:00
#   id: the id of the run in the activity log of the frontend (context run), or a random one
#   frontend: network address of the frontend that sent the submission
#   event: run (it was judged) or run_invalid (rejected with HTTP 400, data has the reason)
#   user, role, address, course, material, type: of the context sent by the frontend
#   data: JSON object with the language, the code hash, the seconds the submission took, the status
#   and passed test cases, the resources of each test case, and the other fields of the context
COLUMNS = ('time', 'id', 'frontend', 'event', 'user', 'role', 'address', 'course', 'material',
    'type', 'data')
# Fields of the context that have their own column. Others go to the context field of data
CONTEXT_COLUMNS = ('user', 'role', 'address', 'course', 'material', 'type')
# Fields of each test case of a run that the log keeps. Outputs are not kept
TEST_FIELDS = ('status', 'wallTime', 'cpuTime', 'memory', 'threadCount', 'exitCode')

# Limits of the context, which the frontend sends but the backend does not need to judge, so a
# large context cannot fill the log
MAX_CONTEXT_FIELDS = 32
MAX_CONTEXT_NAME = 64
MAX_CONTEXT_TEXT = 256

def run_log() -> vyg.TsvLog:
    """ Return the log of the submissions """
    return vyg.TsvLog(LOG_FOLDER, COLUMNS, 'runs')

def parse_context(value):
    """ Return the context of a submission as a dictionary, or None if it is not valid: an object
    of up to MAX_CONTEXT_FIELDS fields with short names, whose values are short texts, numbers,
    booleans, or null. A missing context is an empty one """
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_CONTEXT_FIELDS:
        return None
    for name, field in value.items():
        if len(name) > MAX_CONTEXT_NAME or not (field is None
                or isinstance(field, (bool, int, float))
                or isinstance(field, str) and len(field) <= MAX_CONTEXT_TEXT):
            return None
    return value

def log_submission(event: str, context: dict, data: dict):
    """ Log a submission event with its context and data. A failure to write is logged, it never
    stops the request """
    cells = { column: context.get(column) for column in CONTEXT_COLUMNS }
    others = { name: value for name, value in context.items()
        if name not in CONTEXT_COLUMNS and name != 'run' }
    if others:
        data = { **data, 'context': others }
    run_id = context.get('run')
    run_log().write({ **cells, 'id': run_id if isinstance(run_id, str) else None,
        'frontend': flask.request.remote_addr, 'event': event, 'data': data })

def log_run(context: dict, language: str, code: str, result_json: str, duration: float):
    """ Log a judged submission: save its code by its hash, and log its result in JSON and the
    seconds it took """
    code_hash = hashlib.sha256(f'{language}\0{code}'.encode('utf-8')).hexdigest()
    run_log().save_code(code_hash, language, code)
    log_submission('run', context, { 'language': language, 'code': code_hash,
        'duration': round(duration, 3), **vyg.summarize_result(result_json, TEST_FIELDS) })
