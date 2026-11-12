""" Start frontend execution """
import os
import flask
import requests
from flask_babel import Babel, get_locale, gettext
from flask_squeeze import Squeeze
from flask_wtf.csrf import CSRFError, CSRFProtect
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix

from admin import UserAdminController
from courses import CourseController
from limits import BACKEND_CONNECT_TIMEOUT, Limits
from problems import BACKEND_STATUS_TIMEOUT, ProblemController
from sso import SsoAdminController, SsoController, SsoProvider
from users import (DEFAULT_FONT, FONTS, TRANSLATIONS_FOLDER, UserForm, client_translations,
    font_url, log_out, refresh_session, select_language)
from db import db
from activity_log import LogController, log_event

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

# Texts of the interface marked with _() are shown in the language chosen by the user or by the
# browser. Their translations are in translations/ (see "Translations" in readme.adoc), and
# base.html writes the language in <html lang>, which static/js/i18n.js reads
babel = Babel(app, locale_selector=select_language,
    default_translation_directories=TRANSLATIONS_FOLDER)
app.jinja_env.globals.update(get_locale=get_locale)

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

# Load the default configuration, and replace it with the settings of this server, if any. Every
# setting is defined in defaults.py, so the code needs no fallback values
app.config.from_pyfile(os.path.join(app_path, 'config/defaults.py'))
config_file = os.path.join(app_path, 'config/config.py')
app.config.from_pyfile(config_file, silent=True)

# The key that signs session cookies. The session holds the logged user and their role, so anyone
# who knows or guesses the key can forge a session of any user, including administrators
MIN_SECRET_KEY_LENGTH = 32
# The public example key of an old configuration file
EXAMPLE_SECRET_KEY = 'A very large and random string that is hard to guess.'

def check_secret_key(secret_key):
    """ Stop the server if the session key is missing, the one of the example file, or short """
    if (not isinstance(secret_key, str) or secret_key == EXAMPLE_SECRET_KEY
            or len(secret_key) < MIN_SECRET_KEY_LENGTH):
        raise RuntimeError(f'SECRET_KEY in {config_file} must be a random string of at least '
            f'{MIN_SECRET_KEY_LENGTH} characters, generate one with: '
            "python3 -c 'import secrets; print(secrets.token_hex(32))'")

check_secret_key(app.config['SECRET_KEY'])
# Invalid limits of runs would fail every run, so the server does not start with them
Limits.check_config(app.config)

# Behind a reverse proxy, every request comes from the address of the proxy, which adds the address
# of the client to the X-Forwarded-For header. TRUSTED_PROXIES is the number of proxies that add
# it. With 0 (clients connect directly) the header is ignored, because clients could fake it
trusted_proxies = app.config['TRUSTED_PROXIES']
if not isinstance(trusted_proxies, int) or trusted_proxies < 0:
    raise RuntimeError(f'TRUSTED_PROXIES in {config_file} must be an integer >= 0')
if trusted_proxies:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxies)

# Runs and the status of the judge need at least one backend
backends = app.config['BACKENDS']
if (not isinstance(backends, list) or not backends
        or not all(isinstance(uri, str) for uri in backends)):
    raise RuntimeError(f'BACKENDS in {config_file} must be a list of at least one URI')

# Single sign-on providers send users back to callback URLs of SITE_URL, and use their secrets
if not isinstance(app.config['SITE_URL'], str):
    raise RuntimeError(f'SITE_URL in {config_file} must be a string')
if not isinstance(app.config['SSO_CLIENT_SECRETS'], dict):
    raise RuntimeError(f'SSO_CLIENT_SECRETS in {config_file} must be a dictionary')

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
# The database object maps Python objects to DB's tuples (ORM, object-relational mapping). The
# tables are created and updated by manage.py (make users), which make runs once before starting
# the servers: the gunicorn workers import this module at the same time, and creating the same
# tables in parallel fails in all of them but one, so the server would not start
db.init_app(app)

@app.before_request
def check_session():
    """ Log out users that an administrator suspended or deleted after they logged in """
    refresh_session()

# Courses -----------------------------------------------------------------------------------------

@app.route('/')
def get_index():
    """ Homepage: list of my courses and available courses """
    # The return value of a view function is the response to the client
    log_event('visit')
    return CourseController.get_index()

@app.route('/course/<name>')
def get_course(name):
    """ Get the contents of the course identified by name """
    # The return value of a view function is the response to the client
    log_event('visit', course=name, material=name, type='course')
    return CourseController.get_course(name)

# Problems ----------------------------------------------------------------------------------------

@app.route('/problem/<course>/<problem>')
def get_problem(course, problem):
    """ User asked for the problem page """
    log_event('visit', course=course, material=problem, type='problem')
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
    log_event('visit')
    return UserForm.show_form(SsoProvider.listed())

@app.route('/logout', methods=['POST'])
def logout():
    """ User wants to logout. Only POST with the CSRF token, so other sites cannot log users out """
    return log_out()

@app.route('/login/sso/<alias>')
def sso_login(alias):
    """ User chose to log in with a single sign-on provider: go to its login page """
    return SsoController.start(alias)

@app.route('/login/sso/<alias>/callback')
def sso_callback(alias):
    """ The single sign-on provider sent the user back after logging in """
    return SsoController.callback(alias)

# Administration ----------------------------------------------------------------------------------

@app.route('/admin/users')
def get_users_admin():
    """ Administrator asked for the page of users: login methods and the list of users """
    log_event('visit')
    return UserAdminController.get_users()

@app.route('/admin/users/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    """ Administrator asked for the form of a user, or sent it """
    return UserAdminController.edit_user(user_id)

@app.route('/admin/users/<int:user_id>/suspend', methods=['POST'])
def suspend_user(user_id):
    """ Administrator suspends a user, who cannot log in until activated again """
    return UserAdminController.set_status(user_id, 'suspended')

@app.route('/admin/users/<int:user_id>/activate', methods=['POST'])
def activate_user(user_id):
    """ Administrator activates a suspended user again """
    return UserAdminController.set_status(user_id, 'active')

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    """ Administrator removes a user and their data, but not their activity in the log """
    return UserAdminController.delete_user(user_id)

@app.route('/admin/sso/new', methods=['GET', 'POST'])
def add_sso_provider():
    """ Administrator asked for the form of a new single sign-on provider, or sent it """
    return SsoAdminController.edit_provider()

@app.route('/admin/sso/<alias>', methods=['GET', 'POST'])
def edit_sso_provider(alias):
    """ Administrator asked for the form of a single sign-on provider, or sent it """
    return SsoAdminController.edit_provider(alias)

@app.route('/admin/sso/<alias>/delete', methods=['POST'])
def delete_sso_provider(alias):
    """ Administrator removes a single sign-on provider """
    return SsoAdminController.delete_provider(alias)

@app.route('/admin/log')
def get_log():
    """ Administrator asked for the activity log and its analysis tables, as a zip file """
    return LogController.download('log', CourseController.cache_courses)

@app.route('/admin/submissions')
def get_submissions():
    """ Administrator asked for the code of the runs, a folder per submission, as a zip file """
    return LogController.download('submissions', CourseController.cache_courses)

# Misc --------------------------------------------------------------------------------------------

@app.route('/status', methods=['GET'])
def get_status():
    """ Client JS asked for backend status, propagate it """
    try:
        # TODO(jhc): summarize status of all available backends
        uris = app.config['BACKENDS']
        return requests.get(f'{uris[0]}/status',
            timeout=(BACKEND_CONNECT_TIMEOUT, BACKEND_STATUS_TIMEOUT)).json()
    except (requests.exceptions.RequestException, ValueError) as error:
        # A stopped backend is expected, and clients poll this route, so a line without the
        # traceback. The error text has the internal address of the backend: logged, not shown
        app.logger.warning('could not get the status of the backend: %s', error)
        return flask.jsonify({ 'status': 'offline', 'error': 'backend not available' }), 504

@app.route('/translations/<language>.json')
def get_translations(language):
    """ Client JavaScript asked for the translations of its texts to the language of the page """
    return flask.jsonify(client_translations(language))

@app.route('/help')
def get_help():
    """ Used in experiment to provide reference about the concepts to solve the tasks """
    log_event('visit')
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
    message = gettext('Your session expired or the request was not valid. Reload the page and '
        'try again.')
    if flask.request.is_json:
        return flask.jsonify({ 'error': message }), 400
    flask.flash(message, 'error')
    # All the forms of the site are in the user page (login, preferences, and logout)
    return flask.redirect(flask.url_for('user'))

# Headers ------------------------------------------------------------------------------------------

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
