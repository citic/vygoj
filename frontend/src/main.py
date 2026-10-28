""" Start frontend execution """
import logging
import os
import time
from logging.handlers import RotatingFileHandler
import flask
import requests
from flask_squeeze import Squeeze
from talisman import Talisman, GOOGLE_CSP_POLICY

from courses import CourseController
from problems import ProblemController
from users import User, UserForm
from db import db
from vyg_log import vyg_log

# Web application ---------------------------------------------------------------------------------

# Directories for templates, static files, are relative to parent folder instead of src/
app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_path = os.path.join(app_path, 'templates/')
static_path = os.path.join(app_path, 'static/')

# Flask web application instance requires the name of the application (this filename)
app = flask.Flask(__name__, template_folder=template_path,
        static_url_path='', static_folder=static_path)

# Compress responses (bzip) and minify static files
squeeze = Squeeze(app)

# Provide security headers to mitigate attacks
cdn = {
    'default-src': ("'self' 'unsafe-inline'"
                    ' *.google-analytics.com'
                    ' *.googleanalytics.com'
                    ' *.gstatic.com'
                    ' ajax.googleapis.com'
                    ' cdn.jsdelivr.net'
                    ' cdnjs.cloudflare.com'
                    ' esm.sh'
                    ' fonts.googleapis.com'
                    ' themes.googleusercontent.com'
                    ' www.google.com'
                    ' www.youtube.com'),
    'img-src': "'self' data:",
    'font-src': "'self' data: *.gstatic.com",
    'worker-src': 'blob: esm.sh',
}
# GOOGLE_CSP_POLICY['default-src'] += f" {CDN_URL}"
Talisman(app, content_security_policy=cdn)

# Load configuration from a Python file with constants
config_file = os.path.join(app_path, 'config/config.py')
app.config.from_pyfile(config_file)

# Database ----------------------------------------------------------------------------------------

# Disable watching object changes to reduce resource consumption
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Only send session cookies over HTTPS connections
app.config['SESSION_COOKIE_SECURE'] = True
# Do not allow JavaScript to access the session cookie
app.config['SESSION_COOKIE_HTTPONLY'] = True
# The database object maps Python objects to DB's tuples (ORM, object-relational mapping)
db.init_app(app)
# Create only the users table, if it does not exist yet
with app.app_context():
    User.__table__.create(db.engine, checkfirst=True)

# Courses -----------------------------------------------------------------------------------------

@app.route('/')
def get_index():
    """ Homepage: list of my courses and available courses """
    # The return value of a view function is the response to the client
    vyg_log('visit', '/')
    return CourseController.get_index()

@app.route('/course/<name>')
def get_course(name):
    """ Get the contents of the course identified by name """
    # The return value of a view function is the response to the client
    vyg_log('visit', f'/course/{name}')
    return CourseController.get_course(name)

# Problems ----------------------------------------------------------------------------------------

@app.route('/problem/<course>/<problem>')
def get_problem(course, problem):
    """ User asked for the problem page """
    vyg_log('visit', f'/problem/{course}/{problem}')
    return ProblemController.get_problem(course, problem)

@app.route('/problem/<course_name>/<problem_name>', methods=['POST'])
def post_problem(course_name, problem_name):
    """ Client JavaScript asked for an action: fetch problem, run code, save code... """
    return ProblemController.post_problem(course_name, problem_name)


# Users -------------------------------------------------------------------------------------------

@app.route('/user', methods=['GET', 'POST'])
def user():
    """ Get/post the login or preferences dialog """
    vyg_log('visit', '/user')
    return UserForm.show_form()

@app.route('/logout')
def logout():
    """ User wants to logout, remove user from session """
    user_obj = flask.session.get('user')
    username = user_obj.get('email', '') if user_obj else ''
    vyg_log('logout', username)
    flask.session.pop('user', None)
    flask.flash('User logged out', 'warning')
    return flask.redirect(flask.url_for('get_index'))

# Misc --------------------------------------------------------------------------------------------

@app.route('/status', methods=['GET'])
def get_status():
    """ Client JS asked for backend status, propagate it """
    try:
        # TODO(jhc): summarize status of all available backends
        uris = app.config.get('BACKENDS', ['http://localhost:9090'])
        return requests.get(f'{uris[0]}/status', timeout=1000).json()
    except requests.exceptions.RequestException as error:
        return flask.jsonify({ 'status': 'offline', 'error': str(error) }), 504

@app.route('/help')
def get_help():
    """ Used in experiment to provide reference about the concepts to solve the tasks """
    vyg_log('visit', '/help')
    return flask.render_template('help.html', it={ })


# Errors ------------------------------------------------------------------------------------------

@app.errorhandler(404)
def get_not_found(_): # error
    ''' Get the not found page for a 404 error '''
    return flask.render_template('not_found.html', it={ }), 404

# Logging -----------------------------------------------------------------------------------------

# Adapted from https://gist.github.com/alexaleluia12/e40f1dfa4ce598c2e958611f67d28966

# If data/ dir does not exist, create it
data_dir = app.config.get('DATA_FOLDER', './data')
if not os.path.exists(data_dir):
    os.mkdir(data_dir)
# If log file does not exist, create it and add its header
log_filename = os.path.join(data_dir, 'vygoj.tsv')
if not os.path.exists(log_filename):
    with open(log_filename, 'a', encoding='utf8') as log_file:
        log_file.write('date\ttime\tip\tscheme\turl\tstatus_code\tuser\tbody\n')
# This object manages the log and slices it each 1MB
log_handler = RotatingFileHandler(log_filename, maxBytes=10**6, backupCount=1000)
# Set the handler as the default
logger = logging.getLogger('vygoj')
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

def log_event(request, response, method):
    '''' Log an entry '''
    timestamp = time.strftime('%y%m%d\t%H%M%S')
    user_obj = flask.session.get('user')
    username = user_obj.get('email', '') if user_obj else ''
    method('%s\t%s\t%s\t%s\t%s\t%s\t%s', timestamp, request.remote_addr, request.method,
            request.url, response.status, username, request.get_data())
    return response

@app.after_request
def log_request(response):
    ''' Log all http requests '''
    return log_event(flask.request, response, logger.info)

@app.after_request
def set_headers(response):
    """ Set other security policy headers that Talisman does not set """
    # Do not serve information about who linked to this page
    response.headers['Referrer-Policy'] = 'strict-origin'
    # Disable browser features that we do not use
    response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=()'
    # Avoid other websites to embed our resources
    response.headers['Cross-Origin-Resource-Policy'] = 'same-site'
    # Allow only embeds resources that explicitly grant permission to be loaded
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    # Avoid an attacker open our site in a new window
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    return response
