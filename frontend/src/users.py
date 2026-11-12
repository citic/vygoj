""" Manages application users, their preferences, and courses' progress """
import datetime
import os
import urllib.parse

import flask
import flask_wtf
from babel.messages.mofile import read_mo
from flask_babel import gettext, lazy_gettext
import wtforms
from wtforms import validators
from werkzeug.security import check_password_hash, generate_password_hash

from db import db
from activity_log import log_event

# Fonts the user may choose for the site: key stored in the database, label shown in the
# preferences, and the family query of Google Fonts that loads it (None for fonts of the system).
# site.css gives the CSS font family of each key
FONTS = {
    'anaheim': ('Anaheim', 'Anaheim:wght@400..800'),
    'system': ('System UI', None),
    'atkinson': ('Atkinson Hyperlegible', 'Atkinson+Hyperlegible+Next:wght@400..800'),
    'inter': ('Inter', 'Inter:wght@400..800'),
    'lexend': ('Lexend', 'Lexend:wght@400..800'),
    'source_serif': ('Source Serif', 'Source+Serif+4:wght@400..800'),
}
DEFAULT_FONT = 'anaheim'

# Languages of the interface: code stored in the database and name shown in the preferences, in
# its own language, so users find theirs. Each one but English needs its translations/ folder
LANGUAGES = {
    'en': 'English',
    'es': 'Español',
}
DEFAULT_LANGUAGE = 'en'
# Folder with the translations of the interface, a subfolder for each language but English
TRANSLATIONS_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'translations')

def select_language() -> str:
    """ Return the language of the interface for this request: the one chosen by the logged in
    user, or else the one that the browser prefers among LANGUAGES, or else English """
    user = flask.session.get('user')
    language = user.get('language') if user else None
    if language in LANGUAGES:
        return language
    return flask.request.accept_languages.best_match(LANGUAGES) or DEFAULT_LANGUAGE

def client_translations(language: str) -> dict:
    """ Return the translations of the interface to the given language as {text: translation},
    for the texts written by JavaScript. English and unknown languages have none. The language is
    checked against LANGUAGES before building the path of its file """
    path = os.path.join(TRANSLATIONS_FOLDER, language, 'LC_MESSAGES', 'messages.mo')
    if language not in LANGUAGES or not os.path.isfile(path):
        return {}
    with open(path, 'rb') as file:
        return {message.id: message.string for message in read_mo(file)
            if message.id and message.string}

def is_admin() -> bool:
    """ True if the logged user is an administrator """
    user = flask.session.get('user')
    return bool(user) and user.get('role') == 'admin'

def require_admin():
    """ Stop the request if the logged user is not an administrator """
    if not is_admin():
        flask.abort(403)

def font_url(font: str) -> str | None:
    """ Return the URL of the Google Fonts stylesheet that loads the given font, or None if the
    font comes with the system. Unknown fonts get the default one """
    query = FONTS.get(font, FONTS[DEFAULT_FONT])[1]
    return f'https://fonts.googleapis.com/css2?family={query}&display=swap' if query else None

# Longest username, the size of its column. Emails of single sign-on users are usernames too
MAX_USERNAME_LENGTH = 128

# Roles of the users and their names in the interface
ROLES = {
    'student': lazy_gettext('Student'),
    'assistant': lazy_gettext('Assistant'),
    'professor': lazy_gettext('Professor'),
    'admin': lazy_gettext('Administrator'),
}

# States of a user: suspended users cannot log in, but their data is kept until they are active
USER_STATUSES = {
    'active': lazy_gettext('Active'),
    'suspended': lazy_gettext('Suspended'),
}

class User(db.Model):
    """ Users are database models with personal data, credentials, and course progress """
    # SQLAlchemy uses the class name for the table, we prefer overriding it to add plural
    __tablename__ = 'users'
    # Users are identified using incremental integer numbers, assigned by the database sequence,
    # which never gives the number of a deleted user again
    id = db.Column(db.Integer, primary_key=True)
    # Username must be unique. Users created by single sign-on (sso.py) get their email
    username = db.Column(db.String(MAX_USERNAME_LENGTH), unique=True, nullable=False)
    # Password hash as first authentication method, never the plain password. None for users who
    # only log in with single sign-on, so their password logins always fail
    password = db.Column(db.String(256))
    # Email must be valid, and a number sent to it is second authentication method
    email = db.Column(db.String(128), unique=True)
    # Full name including last name(s)
    fullname = db.Column(db.String(128), nullable=False)
    # Role: one of the keys of ROLES
    role = db.Column(db.String(16), nullable=False, default='student')
    # One of USER_STATUSES. Administrators suspend and activate users in /admin/users
    status = db.Column(db.String(16), nullable=False, default='active')
    # Color scheme: 'default' follows the operating system, 'light' or 'dark' force one
    color_scheme = db.Column(db.String(8), nullable=False, default='default')
    # Font of the site, one of the keys of FONTS
    font = db.Column(db.String(16), nullable=False, default=DEFAULT_FONT)
    # Language of the interface: 'default' follows the browser, or one of the keys of LANGUAGES
    language = db.Column(db.String(8), nullable=False, default='default')
    # Access all grades this user got in evaluations
    # backref adds a reference to this user in the Progress model. The database deletes the
    # progress of a deleted user (ON DELETE CASCADE), so SQLAlchemy does not load it to delete it
    progress = db.relationship('Progress', backref='role', passive_deletes=True)

    def __repr__(self):
        """ Readable string representation for debugging/testing """
        return f'<User {self.username}>'

    @staticmethod
    def find(user_id: int) -> 'User | None':
        """ Return the user of the given id, or None. Ids out of the range of the column are None,
        instead of an error of the database """
        if not isinstance(user_id, int) or not 0 < user_id < 2**31:
            return None
        return db.session.get(User, user_id)

    @staticmethod
    def add_new(rows) -> int:
        """ Add the users of the given rows that are not in the database yet, and return how many
        were added. Each row is a dictionary with username and password, e.g. the rows of a TSV
        file read by csv.DictReader. Existing users are skipped, so a file can be added again """
        new_users = []
        for row in rows:
            username = row['username']
            if not db.session.scalar(db.select(User).filter_by(username=username)):
                # Full name is required, but the file has none, so use the username
                db.session.add(User(username=username, fullname=username,
                    password=generate_password_hash(row['password'])))
                new_users.append(username)
        db.session.commit()
        # Logged after the commit, so the log has only the users that the database has
        for username in new_users:
            log_event('user_create', { 'source': 'import' }, user=username, role='student')
        return len(new_users)

class Progress(db.Model):
    """ The progress is the grade user got for each evaluation """
    # SQLAlchemy uses the class name for the table, we override it for lowercase
    __tablename__ = 'progress'
    # Progress are identified using incremental integer numbers
    id = db.Column(db.Integer, primary_key=True)
    # The user id number who made a progress (got a grade). Deleting the user deletes it
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    # Name of the course where user got this grade, as in vygoj.json, e.g. 'CI0112'
    course = db.Column(db.String(64), nullable=False)
    # The name of the evaluation solved
    evaluation = db.Column(db.String(64), nullable=False)
    # The grade obtained
    grade = db.Column(db.Float(), nullable=False)

    @staticmethod
    def store(course: str, evaluation: str, grade: float):
        """ Save the last grade the logged user got in an evaluation, replacing the previous one """
        user = flask.session.get('user')
        user_id = user and db.session.scalar(
            db.select(User.id).filter_by(username=user['email']))
        if not user_id:
            return
        progress = db.session.scalar(db.select(Progress).filter_by(
            user_id=user_id, course=course, evaluation=evaluation))
        if not progress:
            progress = Progress(user_id=user_id, course=course, evaluation=evaluation)
            db.session.add(progress)
        progress.grade = grade
        db.session.commit()

    @staticmethod
    def load(course: str) -> dict:
        """ Return the grades of the logged user in the given course as {evaluation: grade} """
        user = flask.session.get('user')
        if not user:
            return {}
        rows = db.session.execute(db.select(Progress.evaluation, Progress.grade).join(User)
            .filter(User.username == user['email'], Progress.course == course))
        return {evaluation: round(grade) for evaluation, grade in rows}

# Failed logins are counted during this time. When a limit is reached, logins are rejected until
# the oldest failures are older than this
LOGIN_WINDOW = datetime.timedelta(minutes=15)
# Failed logins allowed in the window for a user from the same address. It stops a student from
# guessing the password of a classmate
MAX_FAILURES_PER_USER = 5
# Failed logins allowed in the window from the same address, for any users. It stops robots that
# try many users. It is larger because a whole laboratory may share the same public address
MAX_FAILURES_PER_ADDRESS = 30

class LoginAttempt(db.Model):
    """ A failed login, kept for a while to limit password guessing. Counts are stored in the
    database, so all the gunicorn workers share them, and they survive restarts """
    __tablename__ = 'login_attempts'
    # Attempts are identified using incremental integer numbers
    id = db.Column(db.Integer, primary_key=True)
    # Username typed, even if no user has it, so the limit does not reveal which users exist
    username = db.Column(db.String(128), nullable=False, index=True)
    # Network address of the client. Behind a reverse proxy, see TRUSTED_PROXIES in config.py
    address = db.Column(db.String(64), nullable=False, index=True)
    # When the attempt failed
    time = db.Column(db.DateTime(timezone=True), nullable=False, index=True)

    @staticmethod
    def is_blocked(username: str, address: str) -> bool:
        """ True if the given user from the given address cannot try to log in for a while. The
        limit is not per username alone, otherwise anybody could lock the account of a classmate
        by typing wrong passwords before an exam """
        recent = (db.select(db.func.count()).select_from(LoginAttempt)
            .filter(LoginAttempt.time > LoginAttempt.now() - LOGIN_WINDOW,
                LoginAttempt.address == address))
        if db.session.scalar(recent) >= MAX_FAILURES_PER_ADDRESS:
            return True
        failures = db.session.scalar(recent.filter(LoginAttempt.username == username))
        return failures >= MAX_FAILURES_PER_USER

    @staticmethod
    def record_failure(username: str, address: str):
        """ Remember a failed login of the given user from the given address """
        now = LoginAttempt.now()
        # Forget the attempts out of the window, so the table does not grow forever
        db.session.execute(db.delete(LoginAttempt).filter(LoginAttempt.time <= now - LOGIN_WINDOW))
        db.session.add(LoginAttempt(username=username, address=address, time=now))
        db.session.commit()

    @staticmethod
    def clear(username: str, address: str):
        """ Forget the failed logins of the given user from the given address, after a success """
        db.session.execute(db.delete(LoginAttempt).filter(LoginAttempt.username == username,
            LoginAttempt.address == address))
        db.session.commit()

    @staticmethod
    def now() -> datetime.datetime:
        """ Current time with time zone, as stored in the database """
        return datetime.datetime.now(datetime.timezone.utc)

logged_users = set()

# Maximum length of the passwords. Hashing is slow on purpose, so huge passwords would let a client
# keep the server busy
MAX_PASSWORD_LENGTH = 256

# Hash of a password nobody has. Login checks it when the user does not exist, so the response
# takes the same time for existing and missing users, and timing does not reveal the usernames
_MISSING_USER_HASH = generate_password_hash('this user does not exist')

# Longest URL accepted in the next parameter of the login page
MAX_NEXT_URL_LENGTH = 512

def safe_next_url(url):
    """ Return the given URL if it is a page of this site where to go after logging in, or None.
    The URL comes from the query string of the login page (/user?next=/problem/C/p), so anybody
    could write a link to the login page of VygOJ that redirects to a fake site after logging in
    (open redirect). Only paths of this site are accepted, such as /problem/CI0112/hello """
    if not isinstance(url, str) or len(url) > MAX_NEXT_URL_LENGTH:
        return None
    # Browsers read //host and /\host as other sites, and they remove tabs and new lines from
    # URLs, so /<tab>/host becomes //host. Control characters are rejected for that reason
    if (not url.startswith('/') or url.startswith('//') or '\\' in url
            or any(ord(char) < 32 or ord(char) == 127 for char in url)):
        return None
    parts = urllib.parse.urlsplit(url)
    return url if not parts.scheme and not parts.netloc else None

def log_out():
    """ Remove the logged user and the rest of the session (e.g. its CSRF token) """
    log_event('logout')
    flask.session.clear()
    flask.flash(gettext('User logged out'), 'warning')
    return flask.redirect(flask.url_for('get_index'))

def suspended_message() -> str:
    """ Return the message for suspended users who try to log in, or who were logged in when an
    administrator suspended them, in the language of the request """
    return gettext('Your account is suspended. Ask the administrator.')

def refresh_session():
    """ Log out the logged user if an administrator suspended or deleted them after they logged in,
    and take the changes of their full name and role. Sessions are signed cookies that the server
    cannot revoke, so every request checks the user in the database """
    user = flask.session.get('user')
    # Static files do not need the user, and they are most of the requests
    if not user or flask.request.endpoint in (None, 'static'):
        return
    db_user = db.session.scalar(db.select(User).filter_by(username=user.get('email')))
    if not db_user or db_user.status != 'active':
        log_event('logout', { 'reason': 'suspended' if db_user else 'deleted' })
        flask.session.clear()
        logged_users.discard(user.get('email'))
        flask.flash(suspended_message() if db_user else gettext('Your account was deleted.'),
            'error')
        return
    if (user.get('fullname'), user.get('role')) != (db_user.fullname, db_user.role):
        user.update(fullname=db_user.fullname, role=db_user.role)
        flask.session['user'] = user

class UserForm(flask_wtf.FlaskForm):
    """ If no user is logged in, show the login form, otherwise the preferences form """
    # Email field is is the user identification. The validators list are triggered when user
    # clicks the submit button. If a validator fails, the submit action is cancelled allowing user
    # fix data. DataRequired validator ensures the field is not submitted empty.
    # StringField renders <input type=text> element
    # The 'User name' is the field lab
    #username = wtforms.StringField('User name', validators=[validators.DataRequired()])
    email = wtforms.StringField(lazy_gettext('Username/Email'),
        validators=[#validators.DataRequired(),
        validators.Length(3, 128)]) # validators.Email(),
    # Password is required to login or to change password
    password = wtforms.PasswordField(lazy_gettext('Password'),
        validators=[validators.Length(max=MAX_PASSWORD_LENGTH)])
    # Used only when user wants to change password
    new_password = wtforms.PasswordField(lazy_gettext('Password'),
        validators=[validators.Length(max=MAX_PASSWORD_LENGTH)])
    # Asked to make user be sure the new password is well typed
    confirm_password = wtforms.PasswordField(lazy_gettext('Confirm new password'),
        validators=[validators.EqualTo('new_password',
            message=lazy_gettext('Passwords must match'))])
    # Full name of the user, needed to professors know their students and vice versa. The limit
    # is the size of its database column
    fullname = wtforms.StringField(lazy_gettext('Full name'),
        validators=[validators.Length(max=128)])
    # Color scheme preference: default follows the operating system, light or dark force one
    color_scheme = wtforms.RadioField(lazy_gettext('Color scheme'), choices=[
        ('default', lazy_gettext('Default')),
        ('light', lazy_gettext('Light mode')),
        ('dark', lazy_gettext('Dark mode')),
    ], default='default')
    # Font of the site. RadioField rejects values that are not in the choices
    font = wtforms.RadioField(lazy_gettext('Font'),
        choices=[(key, label) for key, (label, _) in FONTS.items()], default=DEFAULT_FONT)
    # Language of the interface: default follows the browser, the others force one
    language = wtforms.RadioField(lazy_gettext('Language'),
        choices=[('default', lazy_gettext('Default')), *LANGUAGES.items()], default='default')
    # Save button. SubmitField renders <input type=submit> element
    update = wtforms.SubmitField(lazy_gettext('Save'), id='confirm_button')
    # Login button, enabled when user is not logged in
    login = wtforms.SubmitField(lazy_gettext('Login'), id='login_button', name='login')
    # Logout button, when user is logged in
    logout = wtforms.SubmitField(lazy_gettext('Logout'), id='reject_button', name='action')
    # Delete account button, if it is allowed
    delete_account = wtforms.SubmitField(lazy_gettext('Delete account'), id='delete_button',
        name='action')

    @staticmethod
    def show_form(providers: list = ()):
        """ Show the login or preferences form to the user. The login form offers the given
        single sign-on providers too """
        user = flask.session.get('user')
        # Page to go after logging in, e.g. the problem where the student wanted to run code. The
        # login form has no action, so it posts to this URL and keeps the next parameter
        next_url = safe_next_url(flask.request.args.get('next'))
        # Fill the form with the data of the logged in user, if any
        form = UserForm(data=user)
        # If user accepted the dialog
        if form.validate_on_submit():
            if form.logout.data:
                return log_out()
            # If user was logged in, update preferences, otherwise try to log in
            if user:
                return UserForm.update_preferences(form, user)
            return UserForm.log_in(form, next_url)
        if user:
            # User is logged in, and wants to change preferences, update some labels
            form.password.label = gettext('Current password')
        else:
            # User is not logged in, the password field is required to login. The list of
            # validators is shared by every form, so it is replaced instead of extended: otherwise
            # one visit to the login page makes the password required in the preferences too
            form.password.validators = [*form.password.validators, validators.DataRequired()]
        # Show the versatile form
        return flask.render_template('user.html', it={
            'title': gettext('User preferences') if user else gettext('User login'),
            'form': form,
            'user': user,
            'providers': providers,
            'next_url': next_url,
        })

    @staticmethod
    def update_preferences(form: 'UserForm', user: dict):
        """ Save the preferences chosen in the form for the logged in user """
        # Save the chosen color scheme, font, and language in the database and in the session
        preferences = {
            'color_scheme': form.color_scheme.data,
            'font': form.font.data,
            'language': form.language.data,
        }
        db.session.execute(db.update(User).filter_by(username=user['email'])
            .values(**preferences))
        db.session.commit()
        user.update(preferences)
        flask.session['user'] = user
        log_event('preferences', preferences)
        # TODO(I): Update the other user preferences in the database
        flask.flash(gettext('Preferences updated successfully.'), 'success')
        return flask.redirect(flask.url_for('user'))

    @staticmethod
    def log_in(form: 'UserForm', next_url: str):
        """ Log in the user typed in the form if the password matches, and go to next_url """
        name = form.email.data
        address = (flask.request.remote_addr or '')[:64]
        # Do not even check the password while blocked, so guessing gives no information
        if LoginAttempt.is_blocked(name, address):
            log_event('login_blocked', user=name, role=None)
            flask.flash(gettext('Too many failed logins. Wait %(minutes)d minutes and try again.',
                minutes=LOGIN_WINDOW.seconds // 60), 'error')
            return flask.redirect(flask.url_for('user', next=next_url))
        # Find the user in the database and compare the typed password with its hash
        db_user = db.session.scalar(db.select(User).filter_by(username=name))
        password_hash = (db_user.password if db_user and db_user.password
            else _MISSING_USER_HASH)
        password_ok = check_password_hash(password_hash, form.password.data or '')
        if not db_user or not password_ok:
            LoginAttempt.record_failure(name, address)
            log_event('login_failed', user=name, role=None)
            flask.flash(gettext('Invalid user or password'), 'error')
            return flask.redirect(flask.url_for('user', next=next_url))
        LoginAttempt.clear(name, address)
        # Checked after the password, so only the owner of the account learns that it is suspended
        if db_user.status != 'active':
            log_event('login_failed', { 'reason': 'suspended' }, user=name, role=db_user.role)
            flask.flash(suspended_message(), 'error')
            return flask.redirect(flask.url_for('user', next=next_url))
        return start_session(db_user, next_url)

def start_session(db_user: User, next_url: str | None, provider: str = None):
    """ Log in the given user, authenticated by password or by the single sign-on provider of
    the given key, and go to next_url """
    # A new session for the logged user, so nothing stored before the login (such as a CSRF
    # token that an attacker could have planted) is kept
    flask.session.clear()
    flask.session['user'] = {
        'email': db_user.username,
        'fullname': db_user.fullname,
        'role': db_user.role,
        'color_scheme': db_user.color_scheme,
        'font': db_user.font,
        'language': db_user.language,
    }
    if provider:
        # The preferences hide the password of users who logged in with single sign-on
        flask.session['user']['sso'] = provider
    logged_users.add(db_user.username)
    flask.flash(gettext('Logged in successfully.'), 'success')
    log_event('login', { 'provider': provider } if provider else None)
    return flask.redirect(next_url or flask.url_for('get_index'))
