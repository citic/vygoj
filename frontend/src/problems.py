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
from problem_loader import ProblemLoader
from users import Progress

# Timeouts in seconds for requests to backends, so a hung backend cannot block a worker forever.
# A run compiles and executes every test case sequentially, each one limited by maxDuration
BACKEND_CONNECT_TIMEOUT = 5
BACKEND_RUN_TIMEOUT = 120
# The status is a light health check shown to clients, so it must answer quickly
BACKEND_STATUS_TIMEOUT = 5

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
    def post_problem(course_name: str, problem_name: str):
        """ Client JavaScript asked for an action: fetch a problem, run user solution,
        save user code, ... All communication is made with JSON objects """
        message = ProblemController.parse_message()
        if message is None:
            return ProblemController.error_response('invalid message', 400)
        try:
            problem = ProblemController.fetch_problem(course_name, problem_name)
            if message.action == 'fetch_problem':
                return ProblemController.to_client_json(problem)
            # Only the languages enabled for the problem may be sent to the judge
            if message.language not in problem.languages:
                return ProblemController.error_response('language not enabled', 400)
            vyg_log('run', f'{course_name}/{problem_name}')
            return ProblemController.judge_solution(problem, message)
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
    def parse_message():
        """ Return the vyg.Message in the JSON body of the request, or None if it is not valid.
        Requiring JSON also stops plain HTML forms of other sites from posting here """
        json_dict = flask.request.get_json(silent=True)
        if not isinstance(json_dict, dict) or json_dict.get('action') not in VALID_ACTIONS:
            return None
        try:
            message = vyg.Message(json_dict)
        except (ValueError, TypeError):
            # Invalid base64 or UTF-8 in the encoded fields (binascii.Error is a ValueError)
            return None
        if not isinstance(message.language, str):
            return None
        return message

    @staticmethod
    def error_response(message: str, status: int):
        """ Errors are answered with a JSON object {error: message}, that the client shows """
        return flask.jsonify({ 'error': message }), status

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
            json.dumps(client_dict, default=vyg.to_dict, indent=2))

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
        """ Called when user input a source code solution and press Run button """
        # Run the test cases and wait for the array of results
        result = ProblemController.run_solution(problem, message)
        # Store the same score problem.js saves in localStorage: percentage of passed test cases,
        # adding 0.5 rounds halves up as JavaScript Math.round does (Python round() goes to even)
        results = result.get('results') or []
        grade = int(100 * result.get('passedTestCount', 0) / len(results) + 0.5) if results else 0
        Progress.store(problem.get_course().name, problem.name, grade)
        return ProblemController.json_response(vyg.to_json(result))

    @staticmethod
    def run_solution(problem: vyg.Problem, solution: vyg.Message):
        """ Compile solution and run it against all test cases. Return an array of verdicts """
        submission = vyg.to_json({ 'problem': problem, 'solution': solution })
        vyg_log('run_submission', submission)
        # Create an array of results, one for each test case
        # TODO(jhc): get these args from config
        uri = f'{ProblemController.select_random_backend()}/run'
        plain_result = requests.post(uri, json=submission,
            timeout=(BACKEND_CONNECT_TIMEOUT, BACKEND_RUN_TIMEOUT))
        plain_result.raise_for_status()
        vyg_log('run_result', plain_result.text)
        # The user program is executed once for each test case
        # TODO(jhc): Run in parallel
        return plain_result.json()

    @staticmethod
    def select_random_backend():
        """ Choose a random URI from the configuration BACKENDS array """
        backends = app.config['BACKENDS']
        if not backends or len(backends) == 0:
            backends = ['http://localhost:9090']
        return random.choice(backends)
