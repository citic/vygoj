""" Start frontend execution """
import flask
import os
from users import User
from courses import Course

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
