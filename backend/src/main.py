""" Start backend execution """
import flask

# Flask web application instance requires the name of the application (this filename)
app = flask.Flask(__name__)

# with app.app_context():
#     flask.g.token = '200d1e038'

token = 0

# @app.route decorator calls the view function index() each time we receive an http request asking
# for path "/". It is converted to app.add_url_rule('/', 'index', index)
@app.route('/')
def index():
    """ Homepage provide help """
    # The return value of a view function is the response to the client
    return '<p>Help</p>\n'

@app.post('/submissions')
def create_submission():
    """ Create a new submission to evaluate a problem solution. A submission token (id) is returned
    that is used to check the submission status later. """
    global token
    if flask.request.headers.get('Content-Type').lower() == 'application/json':
        submission = flask.request.get_json()
        # submission['token'] = g.token
        token += 1
        submission['token'] = token
        return flask.jsonify(submission)
    else:
        return 'Error: content-type must be application/json\n', 415
