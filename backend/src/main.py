""" Start backend execution """
import flask

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

RESULT = {
    'totalDuration': 0.420019,
    'threadCount': 1,
    'outputs': [
        { 'passed': False, 'output': 'Hello\n' },
        { 'passed': True, 'output': '0' },
        { 'passed': False, 'output': 'world!\n' },
    ],
}

@app.post('/run')
def run_solution():
    """ Create a new submission to evaluate a problem solution. A submission token (id) is returned
    that is used to check the submission status later. """
    if flask.request.headers.get('Content-Type').lower() != 'application/json':
        flask.abort(415, 'Error: content-type must be application/json\n')
    submission = flask.request.get_json()
    print(submission)
    return flask.jsonify(RESULT)
