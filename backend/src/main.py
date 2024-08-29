""" Start backend execution """
from flask import Flask, g, jsonify, request#, Response, redirect
app = Flask(__name__)

# with app.app_context():
#     g.token = '200d1e038'

token = 0

@app.route('/')
def index():
    """ Homepage provide help """
    return '<p>Help</p>\n'

@app.post('/submissions')
def create_submission():
    """ Create a new submission to evaluate a problem solution. A submission token (id) is returned
    that is used to check the submission status later. """
    global token
    if request.headers.get('Content-Type').lower() == 'application/json':
        submission = request.get_json()
        # submission['token'] = g.token
        token += 1
        submission['token'] = token
        return jsonify(submission)
    else:
        return 'Error: content-type must be application/json\n', 415
