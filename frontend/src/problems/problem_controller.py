""" Problem management module """
import hashlib
import json
import os
import random
import re
import requests
import flask
from flask import current_app as app
from flask_babel import gettext, lazy_gettext
from itsdangerous import URLSafeTimedSerializer
from werkzeug.exceptions import HTTPException
from werkzeug.security import safe_join

import vyg
from activity_log import log_event, log_run, repo_commit, save_code
from courses.course_controller import CourseController
from repos.git_repo import GitError
from repos.student_repo import StudentRepo, check_tests, solution_filename
from limits import CONSTRAINED_FIELDS, Limits
from problems.problem_loader import ProblemLoader
from runs import Run, RunRejected
from users import Progress

# Timeout in seconds for the status of backends. It is a light health check shown to clients, so
# it must answer quickly. The timeouts of runs depend on their limits (see limits.py)
BACKEND_STATUS_TIMEOUT = 5

# Fields of a problem that the backend needs to judge a solution, besides its test cases. Others,
# such as the statement or the initial code, are not sent, so submissions are smaller. The
# constrained fields are sent with their effective values
BACKEND_FIELDS = ('allowIndeterminism', 'languages', 'maxThreads', 'minThreads', 'mustContain',
    'name', 'tools') + tuple(CONSTRAINED_FIELDS)

# Actions that the client JavaScript may ask with a POST to a problem
VALID_ACTIONS = ('fetch_problem', 'lang_server', 'run')

# Characters of the command line arguments that the backend accepts (MAX_ARGS_LENGTH)
MAX_ARGS_LENGTH = 4096

# Text of each warning about the configuration file of a problem (problem_config.py), shown to
# the professor of the course. Their parameters are the name of the file, the field, the number of
# the test case, the kind of value expected, or the error found
WARNING_TEXTS = {
    'fixed_field': lazy_gettext('%(file)s: ignored the field %(field)s, which the course sets'),
    'invalid_field': lazy_gettext('%(file)s: ignored the field %(field)s, which must be '
        '%(kind)s'),
    'invalid_file': lazy_gettext('%(file)s is not valid, so it was ignored: %(error)s'),
    'invalid_test': lazy_gettext('%(file)s: ignored the test case %(test)s of tests, which must '
        'be an object'),
    'invalid_test_field': lazy_gettext('%(file)s: ignored the field %(field)s of the test case '
        '%(test)s, which must be %(kind)s'),
    'invalid_test_key': lazy_gettext('%(file)s: ignored %(test)s of tests, which must be default '
        'or the number of a test case'),
    'no_common_language': lazy_gettext('%(file)s: none of the languages of the problem is a '
        'language of the course, so it has the ones of the course: %(languages)s'),
    'not_object': lazy_gettext('%(file)s must be an object of fields, so it was ignored'),
    'outside_repo': lazy_gettext('%(file)s is out of the repository, so it was ignored'),
    'too_big': lazy_gettext('%(file)s is larger than %(size)s bytes, so it was ignored'),
    'unknown_test': lazy_gettext('%(file)s: ignored the test case %(test)s of tests, which has no '
        'input file in the tests folder'),
}

# Kinds of values that the warnings of WARNING_TEXTS expect
KIND_TEXTS = {
    'codes': lazy_gettext('an object of texts'),
    'date': lazy_gettext('a text or a number of weeks'),
    'flag': lazy_gettext('true or false'),
    'integer': lazy_gettext('an integer'),
    'none_lines': lazy_gettext('"none" or "lines"'),
    'number': lazy_gettext('a number'),
    'overdue_policy': lazy_gettext('"hidden", "disabled", or "half"'),
    'tests': lazy_gettext('a list of test cases or an object of settings'),
    'text': lazy_gettext('a text'),
    'texts': lazy_gettext('a list of texts'),
    'threads': lazy_gettext('an integer or "stdin"'),
    'words': lazy_gettext('a text or a list of texts'),
}

def warning_texts(problem: vyg.Problem) -> list:
    """ Return the texts of the warnings of the problem, in the language of the user """
    texts = []
    for code, params in problem.get_warnings():
        params = dict(params)
        if 'kind' in params:
            params['kind'] = str(KIND_TEXTS.get(params['kind'], params['kind']))
        texts.append(str(WARNING_TEXTS[code]) % params)
    return texts

# Files of a problem folder that browsers may get, by extension, with their media type. They are
# the images, videos, and subtitles of the statements. Other files, such as test cases or
# solutions, are never served
FILE_TYPES = {
    'avif': 'image/avif',
    'gif': 'image/gif',
    'jpeg': 'image/jpeg',
    'jpg': 'image/jpeg',
    'mp4': 'video/mp4',
    'ogv': 'video/ogg',
    'png': 'image/png',
    'svg': 'image/svg+xml',
    'vtt': 'text/vtt',
    'webm': 'video/webm',
    'webp': 'image/webp',
}
# Seconds that browsers may keep a problem file without asking for it again
FILE_MAX_AGE = 3600

class ProblemController:
    """Controls problems

    A problem page contains:
    - a problem statement
    - a text editor to provide a solution
    - a combo box for choosing between the enabled programming languages
    - a Submit/Run button
    - a test case list
    - a test case detail control

    Users read the problem statement, write a code solution in the selected
    programming language, and submit the solution. An AJAX code asks the
    backend to run the solution. The answers are sent to the client that shows
    them to the user.

    The answer contains compiler/interpreter diagnostics. If the code produced
    no errors a report of each passed/failed test case is provided. The AJAX
    code shows these results to the user who can modify the code and submit
    a new solution. This process repeat until user solves the problem or leaves
    the page.    
    """
    def __init__(self):
        pass

    # TODO(jhc): Merge get_problem and post_problem
    @staticmethod
    def get_problem(course_name, problem_name):
        """Get the contents page for a course"""
        problem = ProblemController.fetch_problem(course_name, problem_name)
        previous, following = CourseController.neighbors(problem)
        return flask.render_template('problem.html', it={
            'stylesheet': 'problems',
            'title': problem.title,
            'user': flask.session.get('user', None),
            'breadcrumbs': [
                # TODO(I): course
                { 'href': problem.get_course().build_url(), 'text': course_name },
                { 'href': problem.build_url(), 'text': problem.name },
            ],
            'problem': problem,
            # Problems of the files of the problem folder, only for the professor of the course
            'warnings': (warning_texts(problem)
                if CourseController.is_owner(course_name) else []),
            # (number, problem) of the problems before and after this one in the course, or None
            'previous': previous,
            'next': following,
            # The browser waits for the answer of a run longer than the frontend waits a backend
            'run_timeout': Limits.client_run_timeout(),
            'scripts': [
                '<script src="/js/problem/mathjax-config.js" defer="defer"></script>',
                '<script src="https://cdn.jsdelivr.net/npm/mathjax@4/tex-chtml.js"'
                    ' defer="defer"></script>',
                '<script src="/js/problem/problem.js" type="module" async="async"></script>',
                '<script src="/js/site.js" type="module" async="async"></script>',
            ],
        })

    @staticmethod
    def get_file(course_name: str, problem_name: str, filename: str):
        """ Send an image or video of the problem folder, e.g. img/diagram.svg of the statement """
        problem = ProblemController.fetch_problem(course_name, problem_name)
        folder = problem.get_path()
        # safe_join rejects absolute paths and ../ that go out of the folder. is_inside() also
        # rejects symbolic links to other folders, even to other problems of the course. Files are
        # streamed, not loaded in memory, so large videos are allowed
        path = safe_join(folder, filename)
        file_type = FILE_TYPES.get(os.path.splitext(filename)[1][1:].lower())
        if (not path or not file_type or not os.path.isfile(path)
                or not ProblemLoader.is_inside_course(problem, path)
                or not ProblemLoader.is_inside(folder, path)):
            flask.abort(404)
        # send_file answers range requests, so students can jump to any second of a video
        return flask.send_file(os.path.realpath(path), mimetype=file_type, max_age=FILE_MAX_AGE)

    @staticmethod
    def get_course_file(course_name: str, filename: str):
        """ Send an image of the course repository, e.g. the picture or the banner of the course.
        It follows the rules of the files of problems, but only images are served. Users who see
        the card of a course get its images, also before they enroll in it """
        course = CourseController.find_course(course_name, to_enter=False)
        if not course:
            flask.abort(404)
        path = safe_join(course.folder, filename)
        file_type = FILE_TYPES.get(os.path.splitext(filename)[1][1:].lower(), '')
        if (not path or not file_type.startswith('image/') or not os.path.isfile(path)
                or not ProblemLoader.is_inside(course.folder, path)):
            flask.abort(404)
        return flask.send_file(os.path.realpath(path), mimetype=file_type, max_age=FILE_MAX_AGE)

    @staticmethod
    def post_problem(course_name: str, problem_name: str):
        """ Client JavaScript asked for an action: fetch a problem, run user solution,
        save user code, ... All communication is made with JSON objects """
        message = ProblemController.parse_message()
        if message is None:
            return ProblemController.error_response('invalid message', 400)
        # Only registered users may run code, so it cannot be abused anonymously. The problem page
        # hides the Run button from anonymous visitors, but robots post here directly
        if message.action == 'run' and not flask.session.get('user'):
            return ProblemController.error_response('Log in to run code', 401)
        try:
            return ProblemController.do_action(course_name, problem_name, message)
        except HTTPException:
            # E.g. 404 when the problem does not exist, Flask answers it
            raise
        except requests.exceptions.RequestException as error:
            # A stopped or slow backend is expected, so a line without the traceback
            app.logger.warning('backend failed running %s/%s: %s', course_name, problem_name,
                error)
            return ProblemController.error_response(
                'the judge is not available, try again later', 502)
        except Exception: # pylint: disable=broad-exception-caught
            # Details may have host paths or course data, so they go to the log, not to the client
            app.logger.exception('could not %s %s/%s', message.action, course_name, problem_name)
            return ProblemController.error_response('internal error, try again later', 500)

    @staticmethod
    def do_action(course_name: str, problem_name: str, message: vyg.Message):
        """ Answer the valid message of the client: send the problem, a key for the language
        server, or judge the solution """
        problem = ProblemController.fetch_problem(course_name, problem_name)
        if message.action == 'fetch_problem':
            return ProblemController.to_client_json(problem)
        # Only the languages enabled for the problem may be sent to the judge
        if message.language not in problem.languages:
            return ProblemController.error_response('language not enabled', 400)
        if message.action == 'lang_server':
            return lang_server_key(message.language)
        return ProblemController.judge_solution(problem, message)

    @staticmethod
    def parse_message():
        """ Return the vyg.Message in the JSON body of the request, or None if it is not valid.
        Requiring JSON also stops plain HTML forms of other sites from posting here """
        json_dict = flask.request.get_json(silent=True)
        if not isinstance(json_dict, dict) or json_dict.get('action') not in VALID_ACTIONS:
            return None
        message = vyg.Message(json_dict)
        # JSON may carry any type in these fields. The body size is bounded by MAX_CONTENT_LENGTH
        if not all(isinstance(text, str) for text in
                (message.language, message.code, message.stdin, message.args)):
            return None
        if message.tests is not None:
            message.tests = check_tests(message.tests)
            if message.tests is None:
                return None
        return message

    @staticmethod
    def error_response(message: str, status: int, headers=None):
        """ Errors are answered with a JSON object {error: message}, that the client shows """
        return flask.jsonify({ 'error': message }), status, headers or {}

    @staticmethod
    def json_response(json_text: str):
        """ Answer the JSON text as JSON. Flask would send a str as HTML, and these texts contain
        HTML and program output that browsers must not render as a page """
        return flask.Response(json_text, mimetype='application/json')

    @staticmethod
    def to_client_json(problem: vyg.Problem):
        """ Answer the JSON of the problem for the client. The input and expected output of the
        hidden test cases stay in the server, so students cannot see them. Enabled languages
        without initial code get their default code """
        client_dict = vyg.to_dict(problem)
        default_code = ProblemLoader.default_code()
        initial_code = { language: default_code[language] for language in problem.languages
            if language in default_code }
        initial_code.update({ language: code for language, code in problem.initialCodeFor.items()
            if code })
        if initial_code:
            client_dict['initialCodeFor'] = initial_code
        if 'tests' in client_dict:
            client_dict['tests'] = [{ 'hidden': True, 'points': test.points } if test.hidden
                else test for test in problem.tests]
        return ProblemController.json_response(
            json.dumps(client_dict, default=vyg.to_dict, separators=(',', ':')))

    @staticmethod
    def fetch_problem(course_name: str, problem_name: str):
        """ Return a JSON version of the problem """
        course = CourseController.find_course(course_name)
        if not course:
            flask.abort(404)
        problem = course.find_symbol(problem_name)
        if not problem or not isinstance(problem, vyg.Problem):
            flask.abort(404)
        ProblemLoader.load_folder(problem)
        return problem

    @staticmethod
    def judge_solution(problem: vyg.Problem, message: vyg.Message):
        """ Called when user input a source code solution and press Run button. Runs are limited
        per user (see runs.py), so a user or a robot cannot overload the backends """
        user_id = Run.find_user_id(flask.session['user'].get('email'))
        if user_id is None:
            return ProblemController.error_response('Log in to run code', 401)
        # The backend rejects longer arguments, so the user is told why
        if len(message.args) > MAX_ARGS_LENGTH:
            return ProblemController.error_response(
                gettext('The arguments are too long: at most %(length)d characters',
                    length=MAX_ARGS_LENGTH), 400)
        course_name = problem.get_course().name
        problem_dict = ProblemController.backend_problem(problem, message)
        code_hash = Run.hash_code(problem_dict, message.language, message.code)
        # Cells and data of the activity log of this run. The code hash names the file of its code
        log_cells = { 'course': course_name, 'material': problem.name, 'type': problem.type }
        run_data = { 'language': message.language, 'code': code_hash }
        # The same code as the last run of this problem gives the same result: answer it without
        # running it, e.g. when the student reloads the page and presses Run again. The hash
        # includes the problem sent to the backend, so the result is not reused if the professor
        # changed its test cases or the administrator changed the limits
        repeated = Run.find_repeated(user_id, course_name, problem.name, code_hash)
        if repeated:
            log_run('run_repeated', run_data, repeated, **log_cells)
            return ProblemController.json_response(repeated)
        try:
            run = Run.start(user_id, course_name, problem.name, code_hash)
        except RunRejected as rejection:
            log_event('run_rejected', { **run_data, 'reason': str(rejection) }, **log_cells)
            return ProblemController.error_response(str(rejection), 429,
                { 'Retry-After': str(rejection.retry_after) })
        # Only the code of accepted runs is saved, which are limited per user, so a robot cannot
        # fill the disk with rejected or repeated runs. A repeated run has the file of its first run
        save_code(code_hash, message.language, message.code)
        ProblemController.save_solution(flask.session['user'].get('email'), problem, message)
        # The commit of the course repo recovers the statement and test cases that judged the run.
        # Only accepted runs ask git for it, which are limited per user
        run_data['commit'] = repo_commit(problem.get_course().get_path())
        # The id of the run event joins it with the log of the backend, which gets it in the
        # context of the submission
        run_id = vyg.TsvLog.new_id()
        context = ProblemController.run_context(run_id, log_cells, run_data['commit'])
        result_json = None
        try:
            # Run the test cases and wait for the array of results. The JSON of the backend is
            # answered as it came, it is parsed only to grade it. It is stored for repeated runs
            # only after it was graded, so an invalid answer is not reused
            backend_json = ProblemController.run_solution(problem_dict, message, context)
            if problem.tests:
                Progress.store(course_name, problem.name,
                    ProblemController.grade(backend_json, len(problem.tests)))
            else:
                # Runs with the input of the user (problems without test cases) are not graded,
                # but grade() also checks that the backend answered a result
                ProblemController.grade(backend_json, 0)
            result_json = backend_json
            return ProblemController.json_response(result_json)
        finally:
            # Also when the run failed (without result), so the user can run again
            run.finish(result_json)
            log_run('run' if result_json else 'run_failed', run_data, result_json, id=run_id,
                **log_cells)

    @staticmethod
    def save_solution(username: str, problem: vyg.Problem, message: vyg.Message):
        """ Commit the code and the test cases of the user of the run to their student repo, the
        history of their solutions. A failure is logged, and the run goes on without it """
        try:
            repo = StudentRepo(username)
            repo.save(problem, solution_filename(message.language), message.code)
            if message.tests is not None:
                repo.save_tests(problem, message.tests)
        except (GitError, OSError, ValueError):
            app.logger.exception('could not save the solution of %s/%s',
                problem.get_course().name, problem.name)

    @staticmethod
    def get_versions(course_name: str, problem_name: str):
        """ Answer the versions of the solution of the logged user to the problem, in the language
        of the query, from the oldest to the newest, as [[commit, time], ...] """
        repo, problem, filename = ProblemController.solution_of_user(course_name, problem_name)
        try:
            versions = repo.versions(problem.get_course().name, problem.name, filename)
        except (GitError, OSError, ValueError):
            app.logger.exception('could not list the versions of %s/%s', course_name, problem_name)
            versions = []
        # A run adds a version, so the browser asks for the list every time
        return flask.jsonify(versions), 200, { 'Cache-Control': 'no-store' }

    @staticmethod
    def get_version(course_name: str, problem_name: str, commit: str):
        """ Answer the code of a version of the solution of the logged user to the problem, in the
        language of the query, as text. Other users never reach it: it is read from the repo of
        the logged user only """
        repo, problem, filename = ProblemController.solution_of_user(course_name, problem_name)
        try:
            code = repo.read(commit, problem.get_course().name, problem.name, filename)
        except (GitError, OSError, ValueError):
            flask.abort(404)
        # A commit never changes, so the browser keeps its code
        return flask.Response(code, mimetype='text/plain', headers={
            'Cache-Control': 'private, max-age=31536000, immutable' })

    @staticmethod
    def solution_of_user(course_name: str, problem_name: str):
        """ Return the repo of the logged user, the problem, and the file of its solution in the
        language of the query, or abort if there is no user, problem, or enabled language """
        user = flask.session.get('user')
        if not user:
            flask.abort(401)
        problem = ProblemController.fetch_problem(course_name, problem_name)
        language = flask.request.args.get('language', '')
        if language not in problem.languages:
            flask.abort(400)
        return StudentRepo(user['email']), problem, solution_filename(language)

    @staticmethod
    def grade(result_json: str, tests: int) -> int:
        """ Return the same score problem.js saves in localStorage for the ExecutionResult in JSON:
        percentage of passed test cases among the results of the first tests ones, the test cases
        of the problem. The ones that the user wrote come after them and are not graded. Raises
        ValueError if it is not a JSON object """
        result = json.loads(result_json)
        if not isinstance(result, dict):
            raise ValueError('the backend did not answer an ExecutionResult object')
        results = result.get('results')
        if not isinstance(results, list) or not results[:tests]:
            return 0
        results = results[:tests]
        passed = sum(isinstance(test, dict) and test.get('status') == vyg.Status.PASSED
            for test in results)
        # Adding 0.5 rounds halves up as JavaScript Math.round does (Python round() goes to even)
        return int(100 * passed / len(results) + 0.5)

    @staticmethod
    def backend_problem(problem: vyg.Problem, message: vyg.Message) -> dict:
        """ Return the fields of the problem that the backend needs to judge a solution in the
        language of the message, with the effective limits of the problem and of each test case.
        A problem without test cases gets one written by the user: the input and arguments of the
        message, run without comparing its outputs. The test cases that the user wrote follow the
        ones of the problem, with no points, and their output is compared only if they have one """
        problem_dict = { field: value for field, value in vyg.to_dict(problem).items()
            if field in BACKEND_FIELDS }
        # Limits of the professor out of the range of config.py, or missing, are replaced
        for field in CONSTRAINED_FIELDS:
            problem_dict.pop(field, None)
        problem_dict.update(Limits.effective_problem(problem, message.language))
        tests = problem.tests or [vyg.TestCase({ 'stdin': message.stdin, 'args': message.args,
            'custom': True })]
        tests = tests + [vyg.TestCase({ **test, 'custom': not test['stdout'] })
            for test in message.tests or []]
        problem_dict['tests'] = [Limits.effective_test(test, problem_dict) for test in tests]
        return problem_dict

    @staticmethod
    def run_context(run_id: str, log_cells: dict, commit) -> dict:
        """ Return the context of a run for the log of the backend: the id of the run event in the
        log of the frontend, the logged user, their role and address, the material, and the commit
        of its course repo. The backend does not use it to judge """
        user = flask.session['user']
        return { 'run': run_id, 'user': user.get('email'), 'role': ' '.join(user.get('roles', ())),
            'address': flask.request.remote_addr, **log_cells, 'commit': commit }

    @staticmethod
    def run_solution(problem_dict: dict, solution: vyg.Message, context: dict) -> str:
        """ Compile solution and run it against all test cases of the problem returned by
        backend_problem(). The context goes to the log of the backend (see run_context()). Return
        the ExecutionResult in JSON, as the backend answered it """
        # The backend truncates the output of visible test cases to maxOutputSize, and does not
        # send the output of hidden ones, so large outputs do not travel to the browser
        submission = vyg.to_json({ 'problem': problem_dict, 'solution': solution,
            'context': context })
        uri = f'{ProblemController.select_random_backend()}/run'
        # The submission is already JSON text. json= would encode it again as a JSON string. The
        # backend stops the run after maxTotalDuration, so this timeout is not reached
        response = requests.post(uri, data=submission.encode('utf-8'),
            headers={ 'Content-Type': 'application/json; charset=utf-8' },
            timeout=Limits.backend_timeout(problem_dict))
        response.raise_for_status()
        # The backend writes UTF-8 JSON. requests would guess the encoding of .text otherwise
        response.encoding = 'utf-8'
        # The user program is executed once for each test case
        # TODO(jhc): Run in parallel
        return response.text

    @staticmethod
    def select_random_backend():
        """ Choose a random URI from the configuration BACKENDS array. main.py checks that it is
        not empty """
        return random.choice(app.config['BACKENDS'])

def user_tests(course_name: str, problem_name: str):
    """ Answer the test cases that the logged user wrote for the problem, from their student repo,
    as [{args, stdin, stdout}, ...] """
    user = flask.session.get('user')
    if not user:
        flask.abort(401)
    problem = ProblemController.fetch_problem(course_name, problem_name)
    try:
        tests = StudentRepo(user['email']).read_tests(problem.get_course().name, problem.name)
    except (GitError, OSError, ValueError):
        app.logger.exception('could not read the test cases of %s/%s', course_name, problem_name)
        tests = []
    # A run may change them, so the browser asks for them every time
    return flask.jsonify(tests), 200, { 'Cache-Control': 'no-store' }

def lang_server_key(language: str):
    """ Answer the address of a language server and a key to connect to it with the code editor
    of a problem in the language. Only the users who may open the problem get it (do_action()
    calls fetch_problem() before), and the language server accepts it for a minute (KEY_MAX_AGE),
    so a suspended user cannot connect again. The key is signed with the secret shared with the
    language servers, which check it with the same salt. Without language servers it answers an
    empty object, and the editor only suggests the words of the code """
    if not app.config['LANG_SERVERS']:
        return flask.jsonify({})
    user = flask.session['user'].get('email')
    keys = URLSafeTimedSerializer(app.config['LANG_SERVER_SECRET'], salt='langserv')
    key = keys.dumps({'user': user, 'language': language})
    return flask.jsonify({'url': choose_lang_server(user), 'key': key})

def lang_server_status_url() -> str:
    """ Answer the address of the status of the language server of the logged user, which the
    footer of the pages shows, or an empty string for visitors and without language servers """
    user = flask.session.get('user')
    if not user or not app.config['LANG_SERVERS']:
        return ''
    return lang_server_http_url(choose_lang_server(user.get('email'))).rstrip('/') + '/status'

def lang_server_http_url(url: str) -> str:
    """ Answer the HTTP address of a language server from the WebSocket one of LANG_SERVERS, e.g.
    https://vygoj.ucr.ac.cr/langserv/ from wss://vygoj.ucr.ac.cr/langserv/ """
    return re.sub(r'^ws', 'http', url)

def choose_lang_server(user: str) -> str:
    """ Choose the language server of the user among LANG_SERVERS, which main.py checks that is
    not empty. Each server limits the editors of a user (MAX_USER_SESSIONS) in its own memory, so
    a user always gets the same one. hash() is not used because it changes in each process """
    servers = app.config['LANG_SERVERS']
    digest = hashlib.sha256(str(user).encode()).digest()
    return servers[int.from_bytes(digest[:8], 'big') % len(servers)]
