""" Manages application users, their preferences, and courses' progress """
import flask
import flask_wtf
import wtforms
from wtforms import validators

from db import db
from vyg_log import vyg_log

class User(db.Model):
    """ Users are database models with personal data, credentials, and course progress """
    # SQLAlchemy uses the class name for the table, we prefer overriding it to add plural
    __tablename__ = 'users'
    # Users are identified using incremental integer numbers
    id = db.Column(db.Integer, primary_key=True)
    # Username must be unique
    username = db.Column(db.String(64), unique=True, nullable=False)
    # Password as first authentication method
    password = db.Column(db.String(64), nullable=False)
    # Email must be valid, and a number sent to it is second authentication method
    email = db.Column(db.String(128), unique=True)
    # Full name including last name(s)
    fullname = db.Column(db.String(128), nullable=False)
    # Access all grades this user got in evaluations
    # backref adds a reference to this user in the Progress model
    progress = db.relationship('Progress', backref='role')

    def __repr__(self):
        """ Readable string representation for debugging/testing """
        return f'<User {self.username}>'

class Progress(db.Model):
    """ The progress is the grade user got for each evaluation """
    # SQLAlchemy uses the class name for the table, we override it for lowercase
    __tablename__ = 'progress'
    # Progress are identified using incremental integer numbers
    id = db.Column(db.Integer, primary_key=True)
    # The user id number who made a progress (got a grade)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # The course where user got this grade
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    # The name of the evaluation solved
    evaluation = db.Column(db.String(64), nullable=False)
    # The grade obtained
    grade = db.Column(db.Float(), nullable=False)

users = {
    's01': {'password': 'G45dk8'},
    's02': {'password': 'HHu77a'},
    's03': {'password': 'nBt00e'},
    's04': {'password': '8RYfHA'},
    's05': {'password': '4M6uds'},
    's06': {'password': '29XxbL'},
    's07': {'password': 'eeM8Ej'},
    's08': {'password': 'zDnRw4'},
    's09': {'password': 'ASzta8'},
    's10': {'password': 'vA6nfP'},
    's11': {'password': 'rK2Xhw'},
    's12': {'password': 'zVY6hc'},
    's13': {'password': 'T8T62h'},
    's14': {'password': '3r5xQg'},
    's15': {'password': 'LJWFe5'},
    's16': {'password': 'zUA25H'},
    's17': {'password': 'H3WzHc'},
    's18': {'password': 'X2YAc2'},
    's19': {'password': 'jABZq5'},
    's20': {'password': 'XM6nB2'},
    's21': {'password': 'a7AA2h'},
    's22': {'password': 'xNhG5u'},
    's23': {'password': 'z7y2K5'},
    's24': {'password': 'f25zQY'},
    's25': {'password': 'hc9S64'},
    's26': {'password': 'Tse9Pg'},
    's27': {'password': 'UavaU9'},
    's28': {'password': 'FPEbu3'},
    's29': {'password': 'nwUx6a'},
    's30': {'password': '6fRDER'},
    's31': {'password': '6JTFFt'},
    's32': {'password': 'UnfsF5'},
    's33': {'password': '2DQPBv'},
    's34': {'password': '6XxeHQ'},
    's35': {'password': '2RCWr6'},
    's36': {'password': '6EC96x'},
    's37': {'password': '8PP9bk'},
    's38': {'password': 'u3aJYD'},
    's39': {'password': 'Nm6j8q'},
    's40': {'password': 'VjJ3tT'},
    's41': {'password': 'LB6eeR'},
    's42': {'password': '6cSrp4'},
    's43': {'password': '8rHMUg'},
    's44': {'password': 'KfP6xP'},
    's45': {'password': 'Cz5PeE'},
    's46': {'password': 'G2T7q7'},
    's47': {'password': 'kJ4Yp9'},
    's48': {'password': '7G5VVv'},
    's49': {'password': 'Zz24LD'},
    's50': {'password': '3LS6qm'},
    's51': {'password': '7ghEgK'},
    's52': {'password': '2rDbyE'},
    's53': {'password': 'Afe5de'},
    's54': {'password': 'h9QKCF'},
    's55': {'password': 'AbgK3x'},
}

logged_users = set()

class UserForm(flask_wtf.FlaskForm):
    """ If no user is logged in, show the login form, otherwise the preferences form """
    # Email field is is the user identification. The validators list are triggered when user
    # clicks the submit button. If a validator fails, the submit action is cancelled allowing user
    # fix data. DataRequired validator ensures the field is not submitted empty.
    # StringField renders <input type=text> element
    # The 'User name' is the field lab
    #username = wtforms.StringField('User name', validators=[validators.DataRequired()])
    email = wtforms.StringField('Username/Email', validators=[#validators.DataRequired(),
        validators.Length(3, 128)]) # validators.Email(),
    # Password is required to login or to change password
    password = wtforms.PasswordField('Password')
    # Used only when user wants to change password
    new_password = wtforms.PasswordField('Password')
    # Asked to make user be sure the new password is well typed
    confirm_password = wtforms.PasswordField('Confirm new password',
        validators=[validators.EqualTo('new_password', message='Passwords must match')])
    # Full name of the user, needed to professors know their students and vice versa
    fullname = wtforms.StringField('Full name')
    # Interface mode preference: light or dark
    interface_mode = wtforms.RadioField('Interface mode', choices=[
        ('light', 'Light mode'),
        ('dark', 'Dark mode'),
    ], default='light')
    # Update button. SubmitField renders <input type=submit> element
    update = wtforms.SubmitField('Update', id='confirm_button', name='action')
    # Login button, enabled when user is not logged in
    login = wtforms.SubmitField('Login', id='login_button', name='login')
    # Logout button, when user is logged in
    logout = wtforms.SubmitField('Logout', id='reject_button', name='action')
    # Delete account button, if it is allowed
    delete_account = wtforms.SubmitField('Delete account', id='delete_button', name='action')

    @staticmethod
    def show_form():
        """ Show the login or preferences form to the user """
        form = UserForm()
        user = flask.session.get('user')
        # If user accepted the dialog
        if form.validate_on_submit():
            if form.logout.data:
                # User wants to logout, remove user from session
                flask.session.pop('user', None)
                flask.flash('User logged out', 'warning')
                return flask.redirect(flask.url_for('get_index'))
            # If user was logged in, update preferences
            if user:
                # TODO(I): Update user preferences in the database
                flask.flash('Preferences updated successfully.', 'success')
            else:
                # User is not logged in, try to login
                # TODO(I): Check credentials in the database
                user = {
                    'email': form.email.data,
                    'fullname': form.fullname.data,
                    'interface_mode': form.interface_mode.data,
                }
                name = form.email.data
                if name in users and form.password.data == users[name]['password']:
                    flask.session['user'] = user
                    logged_users.add(name)
                    flask.flash('Logged in successfully.', 'success')
                    vyg_log('login', name)
                    return flask.redirect(flask.url_for('get_index'))
                else:
                    # User is not logged in, show an error message
                    flask.flash('Invalid user or password', 'error')
                    return flask.redirect(flask.url_for('user'))
        if user:
            # User is logged in, and wants to change preferences, update some labels
            form.password.label = 'Current password'
        else:
            # User is not logged in, the password field is required to login
            form.password.validators += (validators.DataRequired(), )
        # Show the versatile form
        return flask.render_template('user.html', it={
            'title': f'User {"preferences" if user else "login"}',
            'form': form,
            'user': user
        })
