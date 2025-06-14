""" Start frontend execution """
import flask
import logging
import os
import requests
import time
from logging.handlers import RotatingFileHandler

from courses import Course
from problems import ProblemController
from users import LoginForm
from db import db

# Constants ---------------------------------------------------------------------------------------
DATA_DIR = './data'
LOG_FILENAME = DATA_DIR + '/vygoj.tsv'

# Web application ---------------------------------------------------------------------------------

# Directories for templates, static files, are relative to parent folder instead of src/
app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_path = os.path.join(app_path, 'templates/')
static_path = os.path.join(app_path, 'static/')

# Flask web application instance requires the name of the application (this filename)
app = flask.Flask(__name__, template_folder=template_path,
        static_url_path='', static_folder=static_path)

# Secret encription key used by Flask-WTF extension to protect sessions against cross-site request
# forgery (CSRF) attacks
# TODO(jhc): Store secret key in environment variable
app.config['SECRET_KEY'] = 'skFVgOf.1sBi0ffM$'

# Database ----------------------------------------------------------------------------------------

# Database is stored in vygoj/frontend/data/frontend.sqlite
db_pathname = os.path.join(app_path, 'data/frontend.sqlite')
# SQLAlchemy looks for the database URI in configuration variable
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_pathname}'
# Disable watching object changes to reduce resource consumption
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# The database object maps Python objects to DB's tuples (ORM, object-relational mapping)
db.init_app(app)

# Courses -----------------------------------------------------------------------------------------

@app.route('/')
def get_index():
    """ Homepage: list of my courses and available courses """
    # The return value of a view function is the response to the client
    return Course.get_index()

@app.route('/course/<course_id>')
def get_course(course_id):
    """ Homepage: list of my courses and available courses """
    # The return value of a view function is the response to the client
    return Course.get_course(course_id)

# Problems ----------------------------------------------------------------------------------------

@app.route('/problem/<path>')
def get_problem(path):
    """ User asked for the problem page """
    return ProblemController.get_problem(path)

@app.route('/problem/<path>', methods=['POST'])
def post_problem(path):
    """ Client JavaScript asked for an action: fetch problem, run code, save code... """
    return ProblemController.post_problem(path)


# Users -------------------------------------------------------------------------------------------

@app.route('/user/login')
def get_login():
    """ Get the login dialog """
    return LoginForm.get_login()

@app.route('/user/login', methods=['POST'])
def post_login():
    """ User provided credentials for logging in """
    return LoginForm.post_login()

# Misc --------------------------------------------------------------------------------------------

@app.route('/status', methods=['GET'])
def get_status():
    """ Client JS asked for backend status, propagate it """
    return requests.get('http://localhost:9090/status', timeout=1000).json()


# Errors ------------------------------------------------------------------------------------------

@app.errorhandler(404)
def get_not_found(_): # error
    ''' Get the not found page for a 404 error '''
    return flask.render_template('not_found.html', it={ }), 404

# Logging -----------------------------------------------------------------------------------------

# Adapted from https://gist.github.com/alexaleluia12/e40f1dfa4ce598c2e958611f67d28966

# If data/ dir does not exist, create it
if not os.path.exists(DATA_DIR):
    os.mkdir(DATA_DIR)
# If log file does not exist, create it and add its header
if not os.path.exists(LOG_FILENAME):
    with open(LOG_FILENAME, 'a', encoding='utf8') as log_file:
        log_file.write('date\ttime\tip\tscheme\turl\tstatus_code\tbody\n')
# This object manages the log and slices it each 1MB
log_handler = RotatingFileHandler(LOG_FILENAME, maxBytes=10**6, backupCount=1000)
# Set the handler as the default
logger = logging.getLogger('vygoj')
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

def log_event(request, response, method):
    '''' Log an entry '''
    timestamp = time.strftime('%y%m%d\t%H%M%S')
    method('%s\t%s\t%s\t%s\t%s\t%s', timestamp, request.remote_addr, request.method,
            request.url, response.status, request.get_data()) # TODO(jhc): user
    return response

@app.after_request
def log_request(response):
    ''' Log all http requests '''
    return log_event(flask.request, response, logger.info)
