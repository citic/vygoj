""" Start backend execution """
import json
import logging
import flask

import execution

# Maximum size of a /run request body. Larger requests are rejected with 413
MAX_REQUEST_BYTES = 16 * 1024 * 1024

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
# Flask rejects larger request bodies before reading them
app.config['MAX_CONTENT_LENGTH'] = MAX_REQUEST_BYTES
logging.basicConfig(level=logging.INFO)

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
    """ Compile and run a solution against the test cases of a problem. Return the
    ExecutionResult as JSON """
    if flask.request.mimetype != 'application/json':
        flask.abort(415, 'Error: content-type must be application/json\n')
    submission = parse_submission(flask.request.get_data(cache=False))
    if not submission:
        flask.abort(400, 'Error: expected a JSON object with problem and solution objects\n')
    try:
        job = execution.Execution(submission['problem'], submission['solution'])
    except execution.InvalidSubmission as error:
        # The message of InvalidSubmission is written by the backend and does not reveal details
        flask.abort(400, f'Error: {error}\n')
    Backend.job_count += 1
    try:
        result = job.execute()
    finally:
        Backend.job_count -= 1
    return flask.Response(result, mimetype='application/json')

def parse_submission(body:bytes):
    """ Return the submission dictionary with problem and solution dictionaries, or None if body
        is malformed """
    try:
        submission = json.loads(body)
    except (ValueError, RecursionError):
        # Invalid JSON or UTF-8, or nesting too deep
        return None
    if (isinstance(submission, dict) and isinstance(submission.get('problem'), dict)
            and isinstance(submission.get('solution'), dict)):
        return submission
    return None
