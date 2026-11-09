""" Problem management module """
import json
import os
import random
import requests
import flask
from flask import current_app as app
from werkzeug.exceptions import HTTPException
from werkzeug.security import safe_join

import vyg
from vyg_log import vyg_log
from courses import CourseController
from limits import CONSTRAINED_FIELDS, Limits
from problem_loader import ProblemLoader
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
VALID_ACTIONS = ('fetch_problem', 'run')

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
        It follows the rules of the files of problems, but only images are served """
        course = CourseController.find_course(course_name)
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
        except requests.exceptions.RequestException:
            app.logger.exception('backend failed running %s/%s', course_name, problem_name)
            return ProblemController.error_response(
                'the judge is not available, try again later', 502)
        except Exception: # pylint: disable=broad-exception-caught
            # Details may have host paths or course data, so they go to the log, not to the client
            app.logger.exception('could not %s %s/%s', message.action, course_name, problem_name)
            return ProblemController.error_response('internal error, try again later', 500)

    @staticmethod
    def do_action(course_name: str, problem_name: str, message: vyg.Message):
        """ Answer the valid message of the client: send the problem, or judge the solution """
        problem = ProblemController.fetch_problem(course_name, problem_name)
        if message.action == 'fetch_problem':
            return ProblemController.to_client_json(problem)
        # Only the languages enabled for the problem may be sent to the judge
        if message.language not in problem.languages:
            return ProblemController.error_response('language not enabled', 400)
        vyg_log('run', f'{course_name}/{problem_name}')
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
        if not isinstance(message.language, str) or not isinstance(message.code, str):
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
        hidden test cases stay in the server, so students cannot see them """
        client_dict = vyg.to_dict(problem)
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
        course_name = problem.get_course().name
        problem_dict = ProblemController.backend_problem(problem, message.language)
        code_hash = Run.hash_code(problem_dict, message.language, message.code)
        # The same code as the last run of this problem gives the same result: answer it without
        # running it, e.g. when the student reloads the page and presses Run again. The hash
        # includes the problem sent to the backend, so the result is not reused if the professor
        # changed its test cases or the administrator changed the limits
        repeated = Run.find_repeated(user_id, course_name, problem.name, code_hash)
        if repeated:
            vyg_log('run_repeated', f'{course_name}/{problem.name}')
            return ProblemController.json_response(repeated)
        try:
            run = Run.start(user_id, course_name, problem.name, code_hash)
        except RunRejected as rejection:
            vyg_log('run_rejected', f'{course_name}/{problem.name}')
            return ProblemController.error_response(str(rejection), 429,
                { 'Retry-After': str(rejection.retry_after) })
        result_json = None
        try:
            # Run the test cases and wait for the array of results. The JSON of the backend is
            # answered as it came, it is parsed only to grade it. It is stored for repeated runs
            # only after it was graded, so an invalid answer is not reused
            backend_json = ProblemController.run_solution(problem_dict, message)
            Progress.store(course_name, problem.name, ProblemController.grade(backend_json))
            result_json = backend_json
            return ProblemController.json_response(result_json)
        finally:
            # Also when the run failed (without result), so the user can run again
            run.finish(result_json)

    @staticmethod
    def grade(result_json: str) -> int:
        """ Return the same score problem.js saves in localStorage for the ExecutionResult in JSON:
        percentage of passed test cases. Raises ValueError if it is not a JSON object """
        result = json.loads(result_json)
        if not isinstance(result, dict):
            raise ValueError('the backend did not answer an ExecutionResult object')
        results = result.get('results')
        passed = result.get('passedTestCount', 0)
        if not isinstance(results, list) or not results or not isinstance(passed, int):
            return 0
        # Adding 0.5 rounds halves up as JavaScript Math.round does (Python round() goes to even)
        return int(100 * passed / len(results) + 0.5)

    @staticmethod
    def backend_problem(problem: vyg.Problem, language: str) -> dict:
        """ Return the fields of the problem that the backend needs to judge a solution in the
        language, with the effective limits of the problem and of each test case """
        problem_dict = { field: value for field, value in vyg.to_dict(problem).items()
            if field in BACKEND_FIELDS }
        # Limits of the professor out of the range of config.py, or missing, are replaced
        for field in CONSTRAINED_FIELDS:
            problem_dict.pop(field, None)
        problem_dict.update(Limits.effective_problem(problem, language))
        problem_dict['tests'] = [Limits.effective_test(test, problem_dict)
            for test in problem.tests]
        return problem_dict

    @staticmethod
    def run_solution(problem_dict: dict, solution: vyg.Message) -> str:
        """ Compile solution and run it against all test cases of the problem returned by
        backend_problem(). Return the ExecutionResult in JSON, as the backend answered it """
        # The backend truncates the output of visible test cases to maxOutputSize, and does not
        # send the output of hidden ones, so large outputs do not travel to the browser
        submission = vyg.to_json({ 'problem': problem_dict, 'solution': solution })
        vyg_log('run_submission', submission)
        uri = f'{ProblemController.select_random_backend()}/run'
        # The submission is already JSON text. json= would encode it again as a JSON string. The
        # backend stops the run after maxTotalDuration, so this timeout is not reached
        response = requests.post(uri, data=submission.encode('utf-8'),
            headers={ 'Content-Type': 'application/json; charset=utf-8' },
            timeout=Limits.backend_timeout(problem_dict))
        response.raise_for_status()
        # The backend writes UTF-8 JSON. requests would guess the encoding of .text otherwise
        response.encoding = 'utf-8'
        vyg_log('run_result', response.text)
        # The user program is executed once for each test case
        # TODO(jhc): Run in parallel
        return response.text

    @staticmethod
    def select_random_backend():
        """ Choose a random URI from the configuration BACKENDS array. main.py checks that it is
        not empty """
        return random.choice(app.config['BACKENDS'])
