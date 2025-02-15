""" Start frontend execution """
import flask
import logging
import os
import time
from logging.handlers import RotatingFileHandler

from users import User
from courses import Course

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

# Courses -----------------------------------------------------------------------------------------

@app.route('/')
def get_index():
    """ Homepage: list of my courses and available courses """
    # The return value of a view function is the response to the client
    return Course.get_index()

# Users -------------------------------------------------------------------------------------------

@app.route('/user/login')
def get_login():
    """ Get the login dialog """
    return User.get_login()

@app.route('/user/login', methods=['POST'])
def post_login():
    """ User provided credentials for logging in """
    return User.post_login()

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
