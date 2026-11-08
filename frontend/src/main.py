""" Start frontend execution """
import logging
import os
import time
from logging.handlers import RotatingFileHandler
import flask
import requests
from flask_squeeze import Squeeze
from flask_wtf.csrf import CSRFError, CSRFProtect
from flask_talisman import Talisman
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from courses import CourseController
from problems import BACKEND_CONNECT_TIMEOUT, BACKEND_STATUS_TIMEOUT, ProblemController
from users import DEFAULT_FONT, FONTS, User, UserForm, font_url, log_out
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

# Every page uses the font chosen by the user, base.html loads it with these names
app.jinja_env.globals.update(FONTS=FONTS, DEFAULT_FONT=DEFAULT_FONT, font_url=font_url)

# Compress responses (bzip) and minify static files
squeeze = Squeeze(app)

# Provide security headers to mitigate attacks. Problem statements come from course repos and are
# shown as HTML, so the policy must stop the scripts they could carry. Scripts may only come from
# files of this site and the CDNs that the pages use (no 'unsafe-inline', so no <script> blocks,
# onclick attributes, or javascript: URLs run). Styles keep 'unsafe-inline' because Monaco and
# MathJax inject <style> elements. Other resources (frames, images...) follow default-src
cdn = {
    'default-src': ("'self'"
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
    'script-src': "'self' cdn.jsdelivr.net cdnjs.cloudflare.com esm.sh",
    'style-src': ("'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com esm.sh"
                  ' fonts.googleapis.com'),
    'img-src': "'self' data:",
    'font-src': "'self' data: *.gstatic.com cdn.jsdelivr.net",
    'worker-src': 'blob: esm.sh',
    # Pages have no frames, and videos may only be files of this site (the folders of problems).
    # Browsers enforce these rules even if the sanitizer of statements failed
    'frame-src': "'none'",
    'media-src': "'self'",
    # Plugins (<object>, <embed>) are not used and can run code outside the policy
    'object-src': "'none'",
    # A <base> element injected in a statement could redirect the relative URLs of the scripts
    'base-uri': "'self'",
    # Forms may only be sent to this site, so injected forms cannot steal what students type
    'form-action': "'self'",
    # Only this site may embed its pages, against clickjacking (as X-Frame-Options: SAMEORIGIN)
    'frame-ancestors': "'self'",
}
talisman = Talisman(app, content_security_policy=cdn,
    # Do not serve information about who linked to this page, only the site
    referrer_policy='strict-origin',
    # Disable browser features that we do not use, also for third parties (Topics API)
    permissions_policy={'browsing-topics': '()', 'camera': '()', 'geolocation': '()',
        'microphone': '()'},
    # Browsers may only use HTTPS for this site, and its subdomains, as before this package
    strict_transport_security_preload=True)

# Images of problem folders are written by course authors. An SVG may have scripts: they do not
# run inside an <img>, but they would run if a student opened the image URL. This policy for those
# files allows only styles and images, and the sandbox treats them as coming from another origin
FILE_CSP = {
    'default-src': "'none'",
    'img-src': "'self' data:",
    'style-src': "'unsafe-inline'",
    'sandbox': '',
}

# Load configuration from a Python file with constants
config_file = os.path.join(app_path, 'config/config.py')
app.config.from_pyfile(config_file)

# The key that signs session cookies. The session holds the logged user and their role, so anyone
# who knows or guesses the key can forge a session of any user, including administrators
MIN_SECRET_KEY_LENGTH = 32
EXAMPLE_SECRET_KEY = 'A very large and random string that is hard to guess.'

def check_secret_key(secret_key):
    """ Stop the server if the session key is missing, the one of the example file, or short """
    if (not isinstance(secret_key, str) or secret_key == EXAMPLE_SECRET_KEY
            or len(secret_key) < MIN_SECRET_KEY_LENGTH):
        raise RuntimeError(f'SECRET_KEY in {config_file} must be a random string of at least '
            f'{MIN_SECRET_KEY_LENGTH} characters, generate one with: '
            "python3 -c 'import secrets; print(secrets.token_hex(32))'")

check_secret_key(app.config.get('SECRET_KEY'))

# Behind a reverse proxy, every request comes from the address of the proxy, which adds the address
# of the client to the X-Forwarded-For header. TRUSTED_PROXIES is the number of proxies that add
# it. With 0 (clients connect directly) the header is ignored, because clients could fake it
trusted_proxies = app.config.get('TRUSTED_PROXIES', 0)
if not isinstance(trusted_proxies, int) or trusted_proxies < 0:
    raise RuntimeError(f'TRUSTED_PROXIES in {config_file} must be an integer >= 0')
if trusted_proxies:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxies)

# Database ----------------------------------------------------------------------------------------

# Disable watching object changes to reduce resource consumption
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Only send session cookies over HTTPS connections
app.config['SESSION_COOKIE_SECURE'] = True
# Do not allow JavaScript to access the session cookie
app.config['SESSION_COOKIE_HTTPONLY'] = True
# Browsers do not send the session cookie in POST requests started by other sites (defense in
# depth against cross-site request forgery, the CSRF tokens below are the main protection)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Reject larger request bodies (HTTP 413) before reading them, so a client cannot exhaust the
# memory of the server, the logs, or the backends. Solutions are source files, 1 MiB is plenty
app.config.setdefault('MAX_CONTENT_LENGTH', 2**20)

# Every POST request must carry the CSRF token of the session: forms in a hidden field, and fetch()
# calls in the X-CSRFToken header. Students keep problem pages open for hours, so the token lasts
# as long as the session instead of expiring after one hour
app.config.setdefault('WTF_CSRF_TIME_LIMIT', None)
csrf = CSRFProtect(app)
# The database object maps Python objects to DB's tuples (ORM, object-relational mapping)
db.init_app(app)
# Create the users and progress tables, if they do not exist yet
with app.app_context():
    db.create_all()
    # Nobody can log in without users. The administrator is created in the server, not in the web
    if not db.session.scalar(db.select(User.id).limit(1)):
        app.logger.warning('There are no users yet. Create the administrator in command line with: '
                'make admin')

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

@app.route('/problem/<course_name>/<problem_name>/files/<path:filename>')
@talisman(content_security_policy=FILE_CSP)
def get_problem_file(course_name, problem_name, filename):
    """ Browser asked for an image of the problem statement """
    return ProblemController.get_file(course_name, problem_name, filename)

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

@app.route('/logout', methods=['POST'])
def logout():
    """ User wants to logout. Only POST with the CSRF token, so other sites cannot log users out """
    return log_out()

# Misc --------------------------------------------------------------------------------------------

@app.route('/status', methods=['GET'])
def get_status():
    """ Client JS asked for backend status, propagate it """
    try:
        # TODO(jhc): summarize status of all available backends
        uris = app.config.get('BACKENDS', ['http://localhost:9090'])
        return requests.get(f'{uris[0]}/status',
            timeout=(BACKEND_CONNECT_TIMEOUT, BACKEND_STATUS_TIMEOUT)).json()
    except (requests.exceptions.RequestException, ValueError):
        # The error text has the internal address of the backend, so it is logged, not shown
        app.logger.exception('could not get the status of the backend')
        return flask.jsonify({ 'status': 'offline', 'error': 'backend not available' }), 504

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

@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    """ A POST request came without a valid CSRF token: forged by another site, or the session
    expired. JavaScript clients get a JSON error, and form users go back with a message """
    app.logger.warning('CSRF rejected %s %s: %s', flask.request.method, flask.request.path,
        error.description)
    message = 'Your session expired or the request was not valid. Reload the page and try again.'
    if flask.request.is_json:
        return flask.jsonify({ 'error': message }), 400
    flask.flash(message, 'error')
    # All the forms of the site are in the user page (login, preferences, and logout)
    return flask.redirect(flask.url_for('user'))

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

def loggable_body(request):
    """ Return the body of the request to be logged. Form bodies carry passwords and CSRF tokens,
    so they are never logged; only JSON bodies (code submissions) are """
    if not request.is_json:
        return b''
    try:
        return request.get_data()
    except RequestEntityTooLarge:
        return b'(too large)'

def log_event(request, response, method):
    ''' Log an entry '''
    timestamp = time.strftime('%y%m%d\t%H%M%S')
    user_obj = flask.session.get('user')
    username = user_obj.get('email', '') if user_obj else ''
    method('%s\t%s\t%s\t%s\t%s\t%s\t%s', timestamp, request.remote_addr, request.method,
            request.url, response.status, username, loggable_body(request))
    return response

@app.after_request
def log_request(response):
    ''' Log all http requests '''
    return log_event(flask.request, response, logger.info)

@app.after_request
def set_headers(response):
    """ Set other security policy headers that Talisman does not set. Talisman sets its headers
    after this function, so the ones it sets (e.g. Referrer-Policy) are configured in Talisman """
    # Avoid other websites to embed our resources
    response.headers['Cross-Origin-Resource-Policy'] = 'same-site'
    # Allow only embeds resources that explicitly grant permission to be loaded
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    # Avoid an attacker open our site in a new window
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    return response
