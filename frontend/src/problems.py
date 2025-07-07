""" Problem management module """
import json
import random
import requests
import flask
from flask import current_app as app

import vyg

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

    @staticmethod
    def get_problem(path):
        """Get the contents page for a course"""
        problem = vyg.Problem.load(path)
        if not problem:
            flask.abort(404)
        return flask.render_template('problem.html', it={
            'stylesheet': 'problems',
            'title': problem.title,
            'user': {'name': 'You', 'role': 'admin'}, # TODO(I): flask.q.session.user,
            'breadcrumbs': [
                # TODO(I): course
                { 'href': f'/course/{path}', 'text': 'CI0117a' },
                { 'href': f'/problem/{problem.relative_path}', 'text': problem.name },
            ],
            'problem': problem,
            'scripts': [
                ('<script src="https://cdn.jsdelivr.net/npm/ace-builds@1.4.13/src-min/ace.js"'
                    ' crossorigin="anonymous" async="async"'
                    ' integrity="sha256-bS3VAQePcKYmsvI+8BdG2QJAVb9FbiZLgM5vK2/+TcM="></script>'),
                ('<script src="https://cdn.jsdelivr.net/npm/ace-diff@3.0.3/dist/ace-diff.min.js"'
                    'async="async"></script>'),
                '<script src="/js/problem/problem.js" type="module" async="async"></script>',
                '<script src="/js/site.js" type="module" async="async"></script>',
            ],
        })

    @staticmethod
    def post_problem(problem_path):
        """Client JavaScript asked for an action: fetch a problem, run user solution,
        save user code, ... All communication is made with JSON objects
        """
        try:
            message = vyg.Message(json.loads(flask.request.get_data()))
            print(problem_path, ' --> ', message.__dict__)
            if message.action == 'fetch_problem':
                return ProblemController.fetch_problem(problem_path)
            elif message.action == 'run':
                return ProblemController.judge_solution(problem_path, message)
            else:
                return flask.jsonify({ 'error': 'invalid action' })
        except Exception as error:
            return flask.jsonify({ 'error': 'invalid action: ' + str(error) })

    @staticmethod
    def fetch_problem(problem_path: str):
        """ Return a JSON version of the problem """
        return vyg.to_json(vyg.Problem.load(problem_path))

    @staticmethod
    def judge_solution(problem_path: str, message: vyg.Message):
        """ Called when user input a source code solution and press Run button """
        # Load the problem
        problem = vyg.Problem.load(problem_path)
        # Run the test cases and wait for the array of results
        result = ProblemController.run_solution(problem, message)
        # Store progress
        # TODO(I): assert req.session.user
        #progress = 100.0 * result.points / result.totalPoints
        # TODO(I): req.session.user?.storeProgress(problem.name, progress);
        return vyg.to_json(result)

    @staticmethod
    def run_solution(problem: vyg.Problem, solution: vyg.Message):
        """ Compile solution and run it against all test cases. Return an array of verdicts """
        submission = vyg.to_json({ 'problem': problem, 'solution': solution })
        print('-----------------------submission----------------\n', submission, '\n------------------------------------------')
        # Create an array of results, one for each test case
        # TODO(jhc): get these args from config
        uri = f'{ProblemController.select_random_backend()}/run'
        plain_result = requests.post(uri, timeout=10000, json=submission)
        print('-----------------------plain_result----------------\n', plain_result, '\n------------------------------------------')
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
