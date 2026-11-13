""" Administration of the users: administrators see the users in /admin/users, edit their data and
role, and suspend, activate, or delete them. Administrators cannot change their own role nor
status, so there is always an administrator, and nobody locks themselves out. The first
administrator, and one who lost their password, are created in the server (manage.py admin) """
import flask
import flask_wtf
from flask_babel import gettext, lazy_gettext
import wtforms
from wtforms import validators
from sqlalchemy.orm import selectinload

from db import db
from activity_log import log_event
from sso import STATUSES, SsoProvider
from users import ROLES, USER_STATUSES, User, require_admin

# Emails are optional. When given, they need a local part and a domain, without spaces
EMAIL_PATTERN = r'[^@\s]+@[^@\s]+\.[^@\s]+$'

# States of a user that the form offers: deleting a user from the form is the same as from the
# table of users
FORM_STATUSES = { **USER_STATUSES, 'deleted': lazy_gettext('Deleted') }

class UserAdminForm(flask_wtf.FlaskForm):
    """ Lets administrators change the data, role, and status of a user. Sizes are the ones of the
    columns. The username is not changed, because it identifies the user in the activity log """
    fullname = wtforms.StringField(lazy_gettext('Full name'),
        validators=[validators.DataRequired(), validators.Length(max=128)])
    email = wtforms.EmailField(lazy_gettext('Email'), validators=[validators.Optional(),
        validators.Length(max=128), validators.Regexp(EMAIL_PATTERN,
            message=lazy_gettext('Write a valid email, or leave it empty'))])
    # RadioFields reject values that are not in their choices, which edit_user() limits
    role = wtforms.RadioField(lazy_gettext('Role'), choices=[])
    status = wtforms.RadioField(lazy_gettext('Status'), choices=[])
    save = wtforms.SubmitField(lazy_gettext('Save'))

def is_self(db_user: User) -> bool:
    """ True if the given user is the logged administrator """
    user = flask.session.get('user') or {}
    return db_user.username == user.get('email')

class UserAdminController:
    """ Lets administrators see the users and change, suspend, activate, or delete them """

    @staticmethod
    def get_users():
        """ Show the page of users: the single sign-on providers and the list of users """
        require_admin()
        providers = db.session.scalars(db.select(SsoProvider).order_by(SsoProvider.name)).all()
        users = db.session.scalars(db.select(User).order_by(User.id)
            .options(selectinload(User.identities))).all()
        return flask.render_template('users_admin.html', it={
            'title': gettext('Users'),
            'user': flask.session.get('user'),
            'providers': providers,
            'statuses': STATUSES,
            'users': users,
            'roles': ROLES,
            'user_statuses': USER_STATUSES,
        })

    @staticmethod
    def edit_user(user_id: int):
        """ Show the form of the user of the given id, and save it """
        require_admin()
        db_user = UserAdminController.find_user(user_id)
        form = UserAdminForm(obj=db_user)
        # Administrators keep their own role and status, so they cannot lock themselves out
        if is_self(db_user):
            form.role.choices = [(db_user.role, ROLES.get(db_user.role, db_user.role))]
            form.status.choices = [(db_user.status, FORM_STATUSES[db_user.status])]
        else:
            form.role.choices = list(ROLES.items())
            form.status.choices = list(FORM_STATUSES.items())
        if form.validate_on_submit() and UserAdminController.check_form(form, db_user):
            if form.status.data == 'deleted':
                return UserAdminController.delete(db_user)
            return UserAdminController.save_user(form, db_user)
        return flask.render_template('user_admin.html', it={
            # The number and username identify the user and cannot change, so they are the title
            'title': gettext('User %(id)d: %(username)s', id=db_user.id, username=db_user.username),
            'user': flask.session.get('user'),
            'form': form,
            'edited_user': db_user,
            'is_self': is_self(db_user),
            'breadcrumbs': [{ 'href': flask.url_for('get_users_admin'), 'text': gettext('Users') }],
        })

    @staticmethod
    def check_form(form: UserAdminForm, db_user: User) -> bool:
        """ Check the rules that need the database, adding their errors to the form. True if the
        form is valid """
        email = (form.email.data or '').strip()
        if email and db.session.scalar(db.select(User.id).filter(User.id != db_user.id,
                db.func.lower(User.email) == email.lower())):
            form.email.errors.append(gettext('Another user has this email'))
        return not form.email.errors

    @staticmethod
    def save_user(form: UserAdminForm, db_user: User):
        """ Store the data of the valid form in the given user, and log the values that changed """
        values = {
            'fullname': form.fullname.data.strip(),
            'email': (form.email.data or '').strip() or None,
            'role': form.role.data,
        }
        changes = {name: [getattr(db_user, name), value] for name, value in values.items()
            if getattr(db_user, name) != value}
        for name, (_, value) in changes.items():
            setattr(db_user, name, value)
        db.session.commit()
        if changes:
            log_event('user_update', { 'username': db_user.username, 'changes': changes })
        if form.status.data != db_user.status:
            UserAdminController.change_status(db_user, form.status.data)
        flask.flash(gettext('User %(username)s saved.', username=db_user.username), 'success')
        return flask.redirect(flask.url_for('get_users_admin'))

    @staticmethod
    def set_status(user_id: int, status: str):
        """ Suspend or activate the user of the given id, from the table of users """
        require_admin()
        db_user = UserAdminController.find_user(user_id, changeable=True)
        if db_user.status != status:
            UserAdminController.change_status(db_user, status)
        message = (gettext('User %(username)s suspended.', username=db_user.username)
            if status == 'suspended'
            else gettext('User %(username)s activated.', username=db_user.username))
        flask.flash(message, 'warning' if status == 'suspended' else 'success')
        return flask.redirect(flask.url_for('get_users_admin'))

    @staticmethod
    def change_status(db_user: User, status: str):
        """ Store the given status of the user, and log it. Suspended users cannot log in, and the
        ones that were logged in are logged out at their next request (refresh_session) """
        db_user.status = status
        db.session.commit()
        log_event('user_suspend' if status == 'suspended' else 'user_activate',
            { 'username': db_user.username })

    @staticmethod
    def delete_user(user_id: int):
        """ Remove the user of the given id, from the table of users """
        require_admin()
        return UserAdminController.delete(UserAdminController.find_user(user_id, changeable=True))

    @staticmethod
    def delete(db_user: User):
        """ Remove the given user and their data from the database: identities of single sign-on,
        progress, and runs, which the database deletes in cascade. The activity log keeps what
        they did. The number of the user is never given again """
        username = db_user.username
        db.session.delete(db_user)
        db.session.commit()
        log_event('user_delete', { 'username': username })
        flask.flash(gettext('User %(username)s deleted.', username=username), 'warning')
        return flask.redirect(flask.url_for('get_users_admin'))

    @staticmethod
    def find_user(user_id: int, changeable: bool = False) -> User:
        """ Return the user of the given id, or stop the request with 404 if it does not exist. If
        changeable, the logged administrator is rejected with 403, because nobody suspends nor
        deletes themselves """
        db_user = User.find(user_id)
        if not db_user:
            flask.abort(404)
        if changeable and is_self(db_user):
            flask.abort(403)
        return db_user
