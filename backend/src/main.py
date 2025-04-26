""" Start backend execution """
import flask
import json

import execution

class Backend:
    """ Backend general controller object """
    # Software version of the backend
    VERSION = '0.1.0'
    # Number of concurrent execution jobs
    job_count = 0

    @staticmethod
    def status():
        """ Return a dictionary with the status and statistics of the backend """
        return {
            'status': 'online',
            'version': Backend.VERSION,
            'jobs': Backend.job_count,
        }


# Flask web application instance requires the name of the application (this filename)
app = flask.Flask(__name__)

# with app.app_context():
#     flask.g.token = '200d1e038'

# @app.route decorator calls the view function index() each time we receive an http request asking
# for path "/". It is converted to app.add_url_rule('/', 'index', index)
@app.route('/')
def index():
    """ Homepage provide help """
    # The return value of a view function is the response to the client
    return '<p>Help</p>\n'

@app.route('/status')
def status():
    """ Frontend wants to know if backend is running and some load statistics """
    # The return value of a view function is the response to the client
    return flask.jsonify(Backend.status())

@app.post('/run')
def run_solution():
    """ Create a new submission to evaluate a problem solution. A submission token (id) is returned
    that is used to check the submission status later. """
    if flask.request.headers.get('Content-Type').lower() != 'application/json':
        flask.abort(415, 'Error: content-type must be application/json\n')
    submission = json.loads(flask.request.get_json())
    print('-----------------------submission----------------\n', submission, '\n------------------------------------------')
    problem_json = submission.get('problem')
    solution_json = submission.get('solution')
    if problem_json and solution_json:
        Backend.job_count += 1
        result = execution.Execution(problem_json, solution_json).execute()
        Backend.job_count -= 1
        return result
    flask.abort(403, '')
