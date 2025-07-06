""" Manages application users, their preferences, and courses' progress """
from db import db
import flask
import flask_wtf
import wtforms
import wtforms.validators as validators

'''
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
    # The user id number who made a progress (got a grade)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # The course where user got this grade
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    # The name of the evaluation solved
    evaluation = db.Column(db.String(64), nullable=False)
    # The grade obtained
    grade = db.Column(db.Float(), nullable=False)
'''

class UserForm(flask_wtf.FlaskForm):
    """ If no user is logged in, show the login form, otherwise the preferences form """
    # Email field is is the user identification. The validators list are triggered when user
    # clicks the submit button. If a validator fails, the submit action is cancelled allowing user
    # fix data. DataRequired validator ensures the field is not submitted empty.
    # StringField renders <input type=text> element
    # The 'User name' is the field lab
    #username = wtforms.StringField('User name', validators=[validators.DataRequired()])
    email = wtforms.StringField('Email', validators=[validators.DataRequired(),
        validators.Length(6, 128)]) # validators.Email(), 
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
    update = wtforms.SubmitField('Update', id='confirm_button', name='action', default='update')
    # Login button, enabled when user is not logged in
    login = wtforms.SubmitField('Login', id='login_button', name='login', default='login')
    # Logout button, when user is logged in
    logout = wtforms.SubmitField('Logout', id='reject_button', name='action', default='logout')
    # Delete account button, if it is allowed
    delete_account = wtforms.SubmitField('Delete account', id='delete_button', name='action',
        default='delete')

    @staticmethod
    def show_form():
        """ Show the login or preferences form to the user """
        form = UserForm()
        user = flask.session.get('user')
        print('>>>>>>>', user)
        # If user accepted the dialog
        if form.validate_on_submit():
            print('>>>>>>>validated on submit')
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
                flask.session['user'] = user
                flask.flash('Logged in successfully.', 'success')
        print('<<<<<<<', user)
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
