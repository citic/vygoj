""" Activity log of the web application, and its export for statistical software.

Each event (a login, a page visit, a run...) is a row of a TSV file per month with a few fixed
columns, and a data column with the fields of each kind of event as a JSON object, so new kinds of
materials add fields, not columns. The code of each run is saved apart, in a file named by its
hash. Log folder (LOG_FOLDER in DATA_FOLDER):

    events-2026-11.tsv               # events of November 2026 (UTC), first row has the columns
    code/<hash>.cpp                  # code of the runs, named by the code field of their data

Administrators download two zip archives made on demand from the log (LogController), also written
by the command line of the server (manage.py log|submissions). The log archive has the files of
the log (log/) and these tables (analysis/), which statistical software reads and joins by their
id and course/material columns:

    analysis/events.tsv     # every event, without its data
    analysis/runs.tsv       # a row per run: language, code, commit of the course, verdicts...
    analysis/tests.tsv      # a row per test case of each run: its status and wall time
    analysis/materials.tsv  # the materials of the courses, with their parent, from the course repos

The submissions archive rebuilds what each user sent, with the problem as it was in the commit of
the course repo of the run, to run the submissions again:

    submissions.tsv                                 # index: a row per submission
    submissions/<user>/<course>/<material>/
        problem.es.adoc                             # statement (.adoc, .md, or .html)
        initial/, given/                            # initial code
        tests/input001.txt, tests/output001.txt...  # test cases
        <YYYYMMDD_HHMMSS>/solution.cpp              # code, with the extension of its language
                         /result.tsv                # verdict of each test case

See "Activity log" in readme.adoc """
import datetime
import glob
import json
import os
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

import flask
from flask import current_app as app

import vyg
from problem_loader import MAX_FILE_SIZE, ProblemLoader

# Folder inside DATA_FOLDER where the activity log is written
LOG_FOLDER = 'log'
# Subfolder of LOG_FOLDER with the code of the runs
CODE_FOLDER = 'code'

# Columns of the events files, in order. Empty cells are values that do not apply to the event:
#   time: date and time in UTC, ISO 8601 with milliseconds, e.g. 2026-11-08T14:03:12.345+00:00
#   id: random identifier of the event, to join the tables of the log archive
#   user, role: logged user and their role, or the typed username of a failed login
#   address: network address of the client (see TRUSTED_PROXIES in config.py)
#   event: what happened, see EVENTS
#   path: page of the request, e.g. /problem/CI0112/hello
#   course, material, type: the material of the event, by its name, unique in the course, and its
#   type (course, problem...). Its place in the course comes from the course repo
#   data: JSON object with the fields of the event, e.g. the language, code, and verdicts of a run
COLUMNS = ('time', 'id', 'user', 'role', 'address', 'event', 'path', 'course', 'material', 'type',
    'data')

# Events logged, as documented in readme.adoc. log_event() rejects others, so the values of the
# event column are always known by the analysis scripts
EVENTS = ('visit', 'login', 'login_failed', 'login_blocked', 'logout', 'preferences',
    'user_create', 'user_admin', 'run', 'run_repeated', 'run_rejected', 'run_failed',
    'log_download')

# Text cells longer than this are truncated, so a client cannot write large rows (e.g. a long URL)
MAX_CELL_LENGTH = 256
# The data of an event is made by the server, but a problem with many test cases makes it long. A
# longer data is replaced by an error, so a row is always written with a single system call
MAX_DATA_LENGTH = 2**16
# Spreadsheets run the cells that start with these characters as formulas. A username typed in the
# login could be a formula, so these cells start with an apostrophe, as spreadsheets expect
FORMULA_STARTS = ('=', '+', '-', '@')
# Seconds to wait for git to tell the commit of a course repo, and to write the files of a problem
# in a commit for the submissions archive
GIT_TIMEOUT = 5
GIT_ARCHIVE_TIMEOUT = 60

# Logging ------------------------------------------------------------------------------------------

def log_event(event: str, data: dict = None, **cells):
    """ Log an event with the given data and cells, named as COLUMNS. The time, id, and the user,
    address, and path of the current request (if any) are filled unless given. A failure to write
    is logged in the error log, it never stops the request """
    if event not in EVENTS or not set(cells) <= set(COLUMNS):
        raise ValueError(f'invalid event {event} or columns {list(cells)}')
    row = request_cells()
    row.update(cells, event=event, id=secrets.token_hex(6), data=format_data(data),
        time=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds'))
    line = '\t'.join(format_cell(row.get(column), column) for column in COLUMNS) + '\n'
    try:
        append_line(events_path(), line)
    except OSError:
        app.logger.exception('could not write the %s event in the activity log', event)

def request_cells() -> dict:
    """ Return the cells of the current request: logged user, role, address, and path. The command
    line (e.g. manage.py) has no request, so it returns no cells """
    if not flask.has_request_context():
        return {}
    user = flask.session.get('user') or {}
    return {
        'user': user.get('email'),
        'role': user.get('role'),
        'address': flask.request.remote_addr,
        'path': flask.request.path,
    }

def log_run(event: str, run_data: dict, result_json: str = None, **cells):
    """ Log a run event with its data (language, code...) and the verdicts of its ExecutionResult
    in JSON, if any """
    log_event(event, {**run_data, **summarize_result(result_json)}, **cells)

def summarize_result(result_json: str) -> dict:
    """ Return the fields of the ExecutionResult in JSON that the log keeps: status, passed test
    cases, and the status and wall time of each test case. Outputs are not kept. Empty if there is
    no result or it is not valid """
    try:
        result = json.loads(result_json) if result_json else None
    except ValueError:
        return {}
    if not isinstance(result, dict) or not isinstance(result.get('results', []), list):
        return {}
    passed = vyg.Status.PASSED.value
    return {
        'status': result.get('status', passed),
        'passed': result.get('passedTestCount', 0),
        'tests': [{ 'status': test.get('status', passed), 'wallTime': test.get('wallTime', 0) }
            for test in result.get('results', []) if isinstance(test, dict)],
    }

def format_data(data: dict) -> str:
    """ Return the data of an event as compact JSON, or None if there is no data. JSON escapes tabs
    and new lines, so the data fits in a cell """
    if not data:
        return None
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    if len(text) > MAX_DATA_LENGTH:
        app.logger.warning('data of an event too long for the activity log: %d', len(text))
        return json.dumps({ 'error': 'data too long' })
    return text

def format_cell(value, column: str = '') -> str:
    """ Return the value as a TSV cell: tabs, new lines, and other control characters become
    spaces, so each event is one row even if a client sent them, and long texts are truncated,
    except the data column, which is JSON made by format_data() """
    if value is None:
        return ''
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = ''.join(' ' if ord(char) < 32 or ord(char) == 127 else char for char in str(value))
    if column != 'data':
        text = text[:MAX_CELL_LENGTH]
    return "'" + text if text.startswith(FORMULA_STARTS) else text

def parse_cell(cell: str) -> str:
    """ Return the text of a cell written by format_cell(), without the apostrophe that protects
    formulas """
    return cell[1:] if cell.startswith("'") and cell[1:].startswith(FORMULA_STARTS) else cell

def save_code(code_hash: str, language: str, code: str):
    """ Save the code of a run in the file named by its hash in the code folder, unless it was saved
    before (the same submission). A failure to write is logged, it never stops the run """
    path = code_path(log_folder(), code_hash, language)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # O_EXCL fails if the file exists: two users may send the same code at the same time. Only
        # the user of the frontend may read it, as the events files (made by mkstemp)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
            file.write(code)
    except FileExistsError:
        pass
    except OSError:
        app.logger.exception('could not save the code %s in the activity log', code_hash)

def code_path(folder: str, code_hash: str, language: str) -> str:
    """ Return the path of the file with the code of the given hash in the log folder. The hash is
    hexadecimal, made by the server, so it is a safe file name """
    extension = vyg.EXTENSION_LANGUAGES.get(language, 'txt')
    return os.path.join(folder, CODE_FOLDER, f'{code_hash}.{extension}')

def repo_commit(folder: str):
    """ Return the commit of the git repo that has the folder (e.g. a course), or None if it is not
    a repo. With the commit, the statement and test cases of a run are recovered from the repo, so
    the log does not store them """
    return git_output(folder, 'rev-parse', '--verify', '--quiet', 'HEAD')

# Files --------------------------------------------------------------------------------------------

def log_folder() -> str:
    """ Return the folder of the activity log in DATA_FOLDER """
    return os.path.join(app.config['DATA_FOLDER'], LOG_FOLDER)

def events_path() -> str:
    """ Return the events file of the current month, created with the row of columns if it does
    not exist. Each month has its own file, so no file grows forever, and analyses may load only
    the months they need """
    month = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m')
    path = os.path.join(log_folder(), f'events-{month}.tsv')
    if not os.path.exists(path):
        create_file(path, '\t'.join(COLUMNS) + '\n')
    return path

def create_file(path: str, header: str):
    """ Create the file with the header, unless it exists. The gunicorn workers may create it at
    the same time, so the header is written in a temporary file and linked to the path, which
    fails if another worker linked it first. The file never has two headers or rows before it """
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(dir=folder, prefix='.events-')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
            file.write(header)
        os.link(temporary_path, path)
    except FileExistsError:
        pass
    finally:
        os.remove(temporary_path)

def append_line(path: str, line: str):
    """ Append the line to the file in a single system call. The file is opened in append mode,
    so the lines of the gunicorn workers do not overwrite or split each other """
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        os.write(descriptor, line.encode('utf-8'))
    finally:
        os.close(descriptor)

# Columns of the tables of the analysis folder. Runs and tests are joined by the id of the run
EVENT_COLUMNS = tuple(column for column in COLUMNS if column != 'data')
RUN_COLUMNS = ('id', 'time', 'user', 'course', 'material', 'event', 'language', 'code', 'commit',
    'status', 'passed', 'tests', 'wall_time', 'reason')
TEST_COLUMNS = ('run', 'test', 'status', 'wall_time')
MATERIAL_COLUMNS = ('course', 'material', 'type', 'parent', 'depth', 'title')
# Columns of the index of the submissions archive: folder has the submission, and problem the folder
# with the files of its problem in the commit of its run (empty if they could not be recovered)
SUBMISSION_COLUMNS = ('id', 'time', 'user', 'course', 'material', 'event', 'language', 'code',
    'commit', 'status', 'passed', 'tests', 'folder', 'problem')

# Run events whose code was saved, so they are submissions. Repeated runs answer the result of the
# same code, and rejected runs did not run
SUBMISSION_EVENTS = ('run', 'run_failed')
# Codes are SHA-256 hashes in hexadecimal. Others are not used to build file paths
CODE_PATTERN = re.compile('[0-9a-f]{64}')
# Commits of git: SHA-1, or SHA-256 in repos that use it. Others are not passed to git
COMMIT_PATTERN = re.compile('[0-9a-f]{40}|[0-9a-f]{64}')
# Files of a problem folder that the submissions archive takes from the course repo: the statements
# (as ProblemLoader, by extension), the initial code, and the test cases. Other files, such as the
# solutions of the professors, are left out
STATEMENT_EXTENSIONS = ('.adoc', '.html', '.md')
PROBLEM_SUBFOLDERS = ('given', 'initial', 'tests')
# Characters of usernames and material names that are kept in the folders of the submissions
UNSAFE_NAME_CHARACTERS = re.compile(r'[^\w.@-]')

# Reading ------------------------------------------------------------------------------------------

def read_events(folder: str):
    """ Yield each event of the log folder as a dictionary of its cells, in order of time, with
    its data parsed. Rows that do not have the columns of the log are skipped """
    for path in sorted(glob.glob(os.path.join(folder, 'events-*.tsv'))):
        with open(path, encoding='utf-8') as file:
            next(file, None)
            for line in file:
                cells = line.rstrip('\n').split('\t')
                if len(cells) != len(COLUMNS):
                    continue
                event = dict(zip(COLUMNS, map(parse_cell, cells)))
                event['data'] = parse_data(event['data'])
                yield event

def parse_data(cell: str) -> dict:
    """ Return the JSON object of a data cell, or an empty one if it is empty or not valid """
    try:
        data = json.loads(cell) if cell else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}

def run_tests(data: dict) -> list:
    """ Return the test cases of the data of a run that are objects """
    tests = data.get('tests')
    return [test for test in tests if isinstance(test, dict)] if isinstance(tests, list) else []

def is_number(value) -> bool:
    """ True if the value is an int or float (not a bool) """
    return isinstance(value, (int, float)) and not isinstance(value, bool)

# Analysis tables ----------------------------------------------------------------------------------

def event_rows(folder: str):
    """ Yield the rows of events.tsv """
    yield from read_events(folder)

def run_rows(folder: str):
    """ Yield the rows of runs.tsv: the fields of the data of each run event, and the count and
    total wall time of its test cases """
    for event in read_events(folder):
        if not event['event'].startswith('run'):
            continue
        data = event['data']
        tests = run_tests(data) if 'tests' in data else None
        row = { **data, **{ column: event[column] for column in EVENT_COLUMNS } }
        row['tests'] = len(tests) if tests is not None else None
        row['wall_time'] = round(sum(test['wallTime'] for test in tests
            if is_number(test.get('wallTime'))), 3) if tests else None
        yield row

def test_rows(folder: str):
    """ Yield the rows of tests.tsv: each test case of each run, numbered from 1 """
    for event in read_events(folder):
        if event['event'].startswith('run'):
            for number, test in enumerate(run_tests(event['data']), 1):
                yield { 'run': event['id'], 'test': number, 'status': test.get('status'),
                    'wall_time': test.get('wallTime') }

def material_rows(load_courses):
    """ Yield the rows of materials.tsv: every material of the courses that load_courses() returns,
    as they are now in their repos, with the name of the material that contains it, and its depth
    in the course """
    try:
        courses = load_courses()
    except (OSError, ValueError, TypeError):
        app.logger.exception('could not load the courses for the materials table')
        return
    for course in courses:
        yield from walk_materials(course, course, None, 0)

def walk_materials(course, material, parent, depth: int):
    """ Yield the row of the material and of the materials it contains, depth first """
    yield { 'course': course.name, 'material': material.name, 'type': material.type or 'course',
        'parent': parent.name if parent else None, 'depth': depth, 'title': material.title }
    for child in material.contents:
        yield from walk_materials(course, child, material, depth + 1)

# Tables of the analysis folder made from the log, with their columns and the function that yields
# their rows. materials.tsv is made from the courses
TABLES = {
    'events.tsv': (EVENT_COLUMNS, event_rows),
    'runs.tsv': (RUN_COLUMNS, run_rows),
    'tests.tsv': (TEST_COLUMNS, test_rows),
}

# Archives ----------------------------------------------------------------------------------------

def write_log_archive(zip_file: zipfile.ZipFile, folder: str, load_courses):
    """ Write the files of the log folder in log/, and the analysis tables in analysis/. The
    materials table has the courses that load_courses() returns """
    for path in log_files(folder):
        zip_file.write(path, os.path.join(LOG_FOLDER, os.path.relpath(path, folder)))
    # A zip archive writes one file at a time, so each table reads the log again
    for name, (columns, rows) in TABLES.items():
        write_table(zip_file, f'analysis/{name}', columns, rows(folder))
    write_table(zip_file, 'analysis/materials.tsv', MATERIAL_COLUMNS, material_rows(load_courses))

def log_files(folder: str):
    """ Yield the paths of the regular files of the log folder. Symbolic links, which could point
    out of the log, and the temporary files of create_file() are skipped """
    for parent, _, filenames in os.walk(folder):
        for filename in sorted(filenames):
            path = os.path.join(parent, filename)
            if not filename.startswith('.') and not os.path.islink(path) and os.path.isfile(path):
                yield path

def write_table(zip_file: zipfile.ZipFile, name: str, columns: tuple, rows):
    """ Write the rows (dictionaries) as a TSV file with the given columns in the archive """
    with zip_file.open(zip_info(name), 'w') as file:
        file.write(('\t'.join(columns) + '\n').encode('utf-8'))
        for row in rows:
            line = '\t'.join(format_cell(row.get(column)) for column in columns) + '\n'
            file.write(line.encode('utf-8'))

def zip_info(name: str) -> zipfile.ZipInfo:
    """ Return the information of a new file of a zip archive, compressed and dated now. A file
    without date would be dated in 1980 """
    info = zipfile.ZipInfo(name, datetime.datetime.now().timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    return info

def write_submissions_archive(zip_file: zipfile.ZipFile, folder: str, load_courses):
    """ Write a folder for each problem that each user ran, with the statement, initial code, and
    test cases of the problem as they were in the commit of the course repo of their first run, and
    a folder for each submission with its code and the verdict of each test case. A submission
    judged by another commit of the problem has its own copy of those files. submissions.tsv is
    the index of the submissions """
    with tempfile.TemporaryDirectory() as cache_folder:
        problems = ProblemFiles(load_course_names(load_courses), cache_folder)
        used_folders = set()
        index = []
        for event in read_events(folder):
            data = event['data']
            code = data.get('code')
            if (event['event'] not in SUBMISSION_EVENTS or not isinstance(code, str)
                    or not CODE_PATTERN.fullmatch(code)):
                continue
            submission = submission_folder(event, used_folders)
            if not submission:
                continue
            write_submission(zip_file, folder, submission, data)
            problem_folder = problems.write_for(zip_file, submission,
                (event['course'], event['material'], data.get('commit')))
            index.append({ **data, **event, 'folder': submission, 'problem': problem_folder,
                'tests': len(run_tests(data)) if 'tests' in data else None })
        write_table(zip_file, 'submissions.tsv', SUBMISSION_COLUMNS, index)

def write_submission(zip_file: zipfile.ZipFile, folder: str, submission: str, data: dict):
    """ Write the code of the submission (its run data) and the verdict of each test case in its
    folder of the archive. The extension of the code is the one of its language """
    code_file = code_path(folder, data['code'], data.get('language'))
    if os.path.isfile(code_file) and not os.path.islink(code_file):
        zip_file.write(code_file, f'{submission}/solution{os.path.splitext(code_file)[1]}')
    tests = [{ 'test': number, 'status': test.get('status'), 'wall_time': test.get('wallTime') }
        for number, test in enumerate(run_tests(data), 1)]
    if tests:
        write_table(zip_file, f'{submission}/result.tsv', TEST_COLUMNS[1:], tests)

def submission_folder(event: dict, used_folders: set):
    """ Return the folder of the submission in the archive, named by its user, course, material,
    and time, or None if its time is not valid. Names come from users and URLs, so they are made
    safe for file systems. A second submission at the same second gets the id of its event """
    try:
        time = datetime.datetime.fromisoformat(event['time'])
    except ValueError:
        return None
    parts = [safe_name(event[column]) for column in ('user', 'course', 'material')]
    folder = '/'.join(['submissions', *parts, time.strftime('%Y%m%d_%H%M%S')])
    if folder in used_folders:
        folder += f'_{safe_name(event["id"])}'
    used_folders.add(folder)
    return folder

def safe_name(name: str) -> str:
    """ Return the name as a folder name: characters other than letters, digits, and .@-_ become
    underscores, and names that are empty or start with a dot get an underscore before """
    name = UNSAFE_NAME_CHARACTERS.sub('_', name)
    return '_' + name if not name or name.startswith('.') else name

# Problems -----------------------------------------------------------------------------------------

def load_course_names(load_courses) -> dict:
    """ Return the courses that load_courses() returns by their name, or none if they cannot be
    loaded. The problems of the submissions are found in them """
    try:
        return { course.name: course for course in load_courses() }
    except (OSError, ValueError, TypeError):
        app.logger.exception('could not load the courses for the submissions archive')
        return {}

class ProblemFiles:
    """ The files of problems in commits of their course repos, for the submissions archive. Each
    problem folder is taken once per commit with git archive, in a tar file of a temporary folder,
    and its statement, initial code, and test cases are copied to the archive as many times as
    needed """

    def __init__(self, courses: dict, cache_folder: str):
        """ Find the problems in the given courses by name, and keep their tar files in the given
        temporary folder """
        self.courses = courses
        self.cache_folder = cache_folder
        # (tar path, problem folder in the repo) by (course, material, commit), None if not found
        self.tars = {}
        # Commit of the problem files in the folder of each user and problem, None if they failed
        self.folder_commits = {}

    def write_for(self, zip_file: zipfile.ZipFile, submission: str, key: tuple):
        """ Write the files of the problem (course, material, commit) of the submission folder, and
        return the folder of the archive that has them, or None if they are not available. The
        folder of the user and problem (the parent of the submission) gets the files of the commit
        of its first submission, and later submissions judged by another commit get their own """
        user_folder = os.path.dirname(submission)
        commit = key[2]
        if user_folder not in self.folder_commits:
            written = self.write(zip_file, key, user_folder)
            self.folder_commits[user_folder] = commit if written else None
        folder_commit = self.folder_commits[user_folder]
        if folder_commit is not None and folder_commit == commit:
            return user_folder
        return submission if self.write(zip_file, key, submission) else None

    def write(self, zip_file: zipfile.ZipFile, key: tuple, target: str) -> bool:
        """ Write the statement, initial code, and test cases of the problem (course, material,
        commit) in the target folder of the archive. Return False if they are not available """
        if key not in self.tars:
            self.tars[key] = self.fetch(*key)
        if not self.tars[key]:
            return False
        tar_path, problem_path = self.tars[key]
        with tarfile.open(tar_path) as tar:
            for member in tar:
                path = os.path.relpath(os.path.normpath(member.name), problem_path)
                if member.isreg() and member.size <= MAX_FILE_SIZE and is_problem_file(path):
                    with tar.extractfile(member) as source, zip_file.open(
                            zip_info(f'{target}/{path}'), 'w') as destination:
                        shutil.copyfileobj(source, destination)
        return True

    def fetch(self, course_name: str, material: str, commit):
        """ Return the tar file of the problem folder in the commit of its course repo, and the
        path of the problem folder in the repo, or None if the commit is not valid, or the problem
        is not in the course now (its folder is found in the course as it is now) or was not in
        that commit. git archive is stopped after GIT_ARCHIVE_TIMEOUT """
        course = self.courses.get(course_name)
        problem = course.find_symbol(material) if course else None
        if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit) or not problem:
            return None
        # Problems out of their course repo are not taken
        repo = git_output(course.folder, 'rev-parse', '--show-toplevel')
        if not repo or not ProblemLoader.is_inside_course(problem, problem.get_path()):
            return None
        # Repos may be symbolic links (e.g. vygdata/u13/pexercises), so real paths are compared
        problem_path = os.path.relpath(os.path.realpath(problem.get_path()),
            os.path.realpath(repo))
        if problem_path.startswith('..'):
            return None
        tar_path = os.path.join(self.cache_folder, f'{len(self.tars)}.tar')
        try:
            with open(tar_path, 'wb') as tar_file:
                process = subprocess.run(['git', '-C', repo, 'archive', '--format=tar', commit,
                    '--', problem_path], stdout=tar_file, stderr=subprocess.PIPE,
                    timeout=GIT_ARCHIVE_TIMEOUT, check=False)
        except (OSError, subprocess.TimeoutExpired):
            app.logger.exception('could not get %s of %s in commit %s', material, course_name,
                commit)
            return None
        if process.returncode != 0:
            app.logger.warning('problem %s of %s not in commit %s', material, course_name, commit)
            return None
        return tar_path, problem_path

def is_problem_file(path: str) -> bool:
    """ True if the path, relative to the problem folder, is a statement, initial code, or test
    case, that the submissions archive takes """
    path = os.path.normpath(path)
    if path.startswith('..') or os.path.isabs(path):
        return False
    parts = path.split('/')
    if len(parts) == 1:
        return os.path.splitext(path)[1] in STATEMENT_EXTENSIONS
    return parts[0] in PROBLEM_SUBFOLDERS

def git_output(folder: str, *args) -> str:
    """ Return the output of the git command in the folder, or None if it failed """
    try:
        process = subprocess.run(['git', '-C', folder, *args], capture_output=True, text=True,
            timeout=GIT_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        app.logger.exception('git %s failed in %s', args[0], folder)
        return None
    if process.returncode != 0:
        return None
    return process.stdout.strip() or None

# Archives that may be exported, with the function that writes them
ARCHIVES = {
    'log': write_log_archive,
    'submissions': write_submissions_archive,
}

def write_archive(kind: str, file, load_courses):
    """ Write the archive of the given kind of ARCHIVES in the binary file. load_courses() returns
    the courses for the materials table. The callers pass it, because the module of courses
    imports this one (through users.py) """
    with zipfile.ZipFile(file, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        ARCHIVES[kind](zip_file, log_folder(), load_courses)

# Download -----------------------------------------------------------------------------------------

class LogController:
    """ Lets administrators download the activity log """

    @staticmethod
    def download(kind: str, load_courses):
        """ Send the archive of the given kind (log or submissions) as a zip file to an
        administrator, with the courses that load_courses() returns. It is built in a temporary
        file, not in memory, because the log grows with the use of the judge """
        user = flask.session.get('user')
        if not user or user.get('role') != 'admin':
            flask.abort(403)
        log_event('log_download', { 'archive': kind })
        archive = tempfile.TemporaryFile()
        try:
            write_archive(kind, archive, load_courses)
        except OSError:
            archive.close()
            app.logger.exception('could not build the %s archive', kind)
            flask.abort(500)
        archive.seek(0)
        date = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
        # send_file closes the archive after sending it, and the system deletes the temporary file
        return flask.send_file(archive, mimetype='application/zip', as_attachment=True,
            download_name=f'vygoj-{kind}-{date}.zip')
