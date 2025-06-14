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
 
class LoginForm(flask_wtf.FlaskForm):
    """ Login form controller class. It is rendered when user asks to login. """
    # Email field is is the user identification. The validators list are triggered when user
    # clicks the submit button. If a validator fails, the submit action is cancelled allowing user
    # fix data. DataRequired validator ensures the field is not submitted empty.
    # StringField renders <input type=text> element
    # The 'User name' is the field lab
    #username = wtforms.StringField('User name', validators=[validators.DataRequired()])
    email_validators = [validators.DataRequired(), validators.Email()]
    email = wtforms.StringField('Email', validators=email_validators)
    # Password is required
    password = wtforms.PasswordField('Password', validators=[validators.DataRequired()])
    # Login button. SubmitField renders <input type=submit> element
    submit = wtforms.SubmitField('Login')

    @staticmethod
    def get_login():
        """ Show the login form to the user """
        form = LoginForm()
        return flask.render_template('login.html', it={
            'title': 'User login',
            'form': form,
        })

    @staticmethod
    def post_login():
        return '<p>logged in</p>'
