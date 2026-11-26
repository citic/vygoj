""" Administration of the users: administrators see the users in /admin/users, edit their data and
roles, and suspend, activate, or delete them. Administrators cannot remove their own administrator
role nor change their status, so there is always an administrator, and nobody locks themselves
out. They also add users from a CSV or TSV file. The first administrator, and one who lost their
password, are created in the server (manage.py admin) """
import csv
import io
import os
import re
import shutil

import flask
import flask_wtf
from flask_babel import gettext, lazy_gettext
import wtforms
from wtforms import validators
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from werkzeug.security import generate_password_hash

from db import db
from activity_log import log_event
from data_table import Column, DataTable, choice_match, request_params, text_match
from repos.git_repo import user_folder
from sso import STATUSES, SsoProvider, UserIdentity
from users import (FONTS, LANGUAGES, MAX_PASSWORD_LENGTH, MAX_USERNAME_LENGTH, ROLES,
    USER_STATUSES, User, require_admin, sorted_roles)

# Emails are optional. When given, they need a local part and a domain, without spaces
EMAIL_PATTERN = r'[^@\s]+@[^@\s]+\.[^@\s]+$'

# Largest file of users that administrators may import, in bytes, and most users in it. Hashing a
# password takes about 70 ms, so a file is imported long before the 30 seconds that gunicorn
# gives to a request
MAX_IMPORT_SIZE = 2**20
MAX_IMPORT_ROWS = 200
# Columns that a file of users may have, with the values that each one accepts, or the size of its
# column for texts. username and email are required. A file cannot make administrators, whose
# passwords must not be easy to guess (manage.py admin): they are named in the form of a user
IMPORT_COLUMNS = {
    'username': MAX_USERNAME_LENGTH, 'email': 128, 'fullname': 128,
    'password': MAX_PASSWORD_LENGTH, 'role': { role for role in ROLES if role != 'admin' },
    'status': USER_STATUSES, 'language': LANGUAGES, 'font': FONTS,
}

def with_role(role: str):
    """ Return the SQL condition of the users who have the role """
    return db.literal(role) == db.any_(User.roles)

# Columns of the table of users that are searched or sorted (data_table.py). Users are sorted by
# their highest role, so the ones of each role are together. A user may have several providers, so
# that column is searched, but not sorted. A number of more than 9 digits is not an id, and only
# decimal digits make a number: isdigit() is also true for '²', which int() rejects
USER_COLUMNS = [
    Column('id', '#', User.id,
        lambda text: User.id == int(text) if text.isdecimal() and len(text) < 10 else db.false()),
    Column('username', lazy_gettext('Username'), User.username, text_match(User.username)),
    Column('fullname', lazy_gettext('Full name'), User.fullname, text_match(User.fullname)),
    Column('email', lazy_gettext('Email'), User.email, text_match(User.email)),
    Column('roles', lazy_gettext('Roles'),
        db.case(*((with_role(role), rank) for rank, role in reversed(list(enumerate(ROLES))))),
        choice_match(ROLES, lambda roles: db.or_(*map(with_role, roles)))),
    Column('sso', lazy_gettext('SSO'), None,
        lambda text: User.identities.any(text_match(UserIdentity.provider)(text))),
    Column('status', lazy_gettext('Status'), User.status,
        choice_match(USER_STATUSES, User.status.in_)),
]

# States of a user that the form offers: deleting a user from the form is the same as from the
# table of users
FORM_STATUSES = { **USER_STATUSES, 'deleted': lazy_gettext('Deleted') }

class UserAdminForm(flask_wtf.FlaskForm):
    """ Lets administrators change the data, roles, and status of a user. Sizes are the ones of the
    columns. The username is not changed, because it identifies the user in the activity log """
    fullname = wtforms.StringField(lazy_gettext('Full name'),
        validators=[validators.DataRequired(), validators.Length(max=128)])
    email = wtforms.EmailField(lazy_gettext('Email'), validators=[validators.Optional(),
        validators.Length(max=128), validators.Regexp(EMAIL_PATTERN,
            message=lazy_gettext('Write a valid email, or leave it empty'))])
    # Checkboxes of the roles and radio buttons of the status. Both reject values that are not in
    # their choices, and edit_user() limits the statuses
    roles = wtforms.SelectMultipleField(lazy_gettext('Roles'), choices=list(ROLES.items()),
        widget=wtforms.widgets.ListWidget(), option_widget=wtforms.widgets.CheckboxInput())
    status = wtforms.RadioField(lazy_gettext('Status'), choices=[])
    save = wtforms.SubmitField(lazy_gettext('Save'))

def is_self(db_user: User) -> bool:
    """ True if the given user is the logged administrator """
    user = flask.session.get('user') or {}
    return db_user.username == user.get('email')

class UserAdminController:
    """ Lets administrators see the users and change, suspend, activate, or delete them """

    @staticmethod
    def get_users(report: list = None):
        """ Show the page of users: the single sign-on providers, the page of users that the
        search, sort, and page of the URL ask for, the newest first by default, and the report of
        the last import, if any """
        require_admin()
        providers = db.session.scalars(db.select(SsoProvider).order_by(SsoProvider.name)).all()
        users = DataTable(db.select(User).options(selectinload(User.identities)), USER_COLUMNS,
            'get_users_admin', '-id')
        return flask.render_template('users_admin.html', it={
            'title': gettext('Users'),
            'user': flask.session.get('user'),
            'providers': providers,
            'statuses': STATUSES,
            'users': users,
            # The search, sort, and page of the users, which the actions on a user keep
            'params': request_params(),
            'roles': ROLES,
            'user_statuses': USER_STATUSES,
            'report': report,
        })

    @staticmethod
    def import_users():
        """ Add the users of the CSV or TSV file sent by the administrator, and show the page of
        users with what happened to each row: imported, rejected with its reason, or skipped
        because the user exists. The file is untrusted: each value is checked """
        require_admin()
        file = flask.request.files.get('users')
        try:
            # A larger file is not read whole, so it cannot fill the memory of the server
            data = file.read(MAX_IMPORT_SIZE + 1) if file else b''
            if not data or len(data) > MAX_IMPORT_SIZE:
                raise ValueError
            text = data.decode('utf-8-sig')
            # The separator of the names of the columns: commas, tabs, or the semicolons of the CSV
            # files of spreadsheets in Spanish
            dialect = csv.Sniffer().sniff(text.partition('\n')[0], ',;\t')
            rows = csv.DictReader(io.StringIO(text), delimiter=dialect.delimiter,
                skipinitialspace=True)
            columns = set(rows.fieldnames or [])
            if not {'username', 'email'} <= columns or columns - IMPORT_COLUMNS.keys():
                raise ValueError
            return UserAdminController.get_users(UserAdminController.add_users(rows))
        except IntegrityError:
            # Another request added some of the users meanwhile, e.g. a double click, so this one
            # added none
            db.session.rollback()
            flask.flash(gettext('Another request added some of these users at the same time. '
                'Import the file again to see what happened to each row.'), 'error')
            return UserAdminController.get_users()
        except (UnicodeDecodeError, ValueError, csv.Error):
            flask.flash(gettext('The file must be a CSV or TSV file in UTF-8 of up to 1 MiB and '
                '%(rows)d users, with the columns username and email, and optionally %(columns)s.',
                rows=MAX_IMPORT_ROWS, columns=', '.join(list(IMPORT_COLUMNS)[2:])), 'error')
            return UserAdminController.get_users()

    @staticmethod
    def add_users(rows) -> list:
        """ Add the users of the rows that are valid and new, and return the report of each row as
        (line, username, result, reason), with result imported, rejected, or skipped """
        report, new_users, seen = [], [], set()
        # The users of the database, to check each row without a query
        users = db.session.execute(db.select(User.username, User.email)).all()
        usernames = { username for username, _ in users }
        owners = { email.lower(): username for username, email in users if email }
        for row in rows:
            if len(report) == MAX_IMPORT_ROWS:
                db.session.rollback()
                raise ValueError
            values = { column: value.strip() for column, value in row.items()
                if column in IMPORT_COLUMNS and isinstance(value, str) and value.strip() }
            # Emails are compared in lowercase, as the form of a user and single sign-on do
            values['email'] = values.get('email', '').lower()
            username, email = values.get('username', ''), values['email']
            reason = UserAdminController.check_row(values, seen)
            seen |= { username, email }
            if not reason and owners.get(email, username) != username:
                reason = gettext('the email belongs to the user %(username)s',
                    username=owners[email])
            if reason or username in usernames:
                # The number of the last line of the row, also after empty lines
                report.append((rows.line_num, username, 'rejected' if reason else 'skipped',
                    reason))
                continue
            password = values.pop('password', None)
            # A file gives one role per user, which becomes their list of roles
            roles = [values.pop('role', 'student')]
            db.session.add(User(**{ 'fullname': username, **values, 'roles': roles,
                'password': password and generate_password_hash(password) }))
            new_users.append((username, ' '.join(roles)))
            report.append((rows.line_num, username, 'imported', ''))
        db.session.commit()
        # Logged after the commit, so the log has only the users that the database has
        for username, roles in new_users:
            log_event('user_create', { 'source': 'import' }, user=username, role=roles)
        return report

    @staticmethod
    def check_row(values: dict, seen: set) -> str:
        """ Return why the values of a row of a file of users are not valid, or an empty string.
        seen has the usernames and emails of the rows before it """
        if not values.get('username') or not re.match(EMAIL_PATTERN, values['email']):
            return gettext('it needs a username and a valid email')
        if values['username'] in seen or values['email'] in seen:
            return gettext('the username or the email is repeated in the file')
        for column, rule in IMPORT_COLUMNS.items():
            value = values.get(column)
            if value and (len(value) > rule if isinstance(rule, int) else value not in rule):
                return gettext('invalid %(column)s', column=column)
        return ''

    @staticmethod
    def edit_user(user_id: int):
        """ Show the form of the user of the given id, and save it """
        require_admin()
        db_user = UserAdminController.find_user(user_id)
        form = UserAdminForm(obj=db_user)
        # Administrators keep their own administrator role and status, so they cannot lock
        # themselves out. Its checkbox is disabled, so browsers do not send it
        if is_self(db_user):
            form.roles.data = sorted_roles({ *form.roles.data, 'admin' })
            form.status.choices = [(db_user.status, FORM_STATUSES[db_user.status])]
        else:
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
            'breadcrumbs': [{ 'href': flask.url_for('get_users_admin', **request_params()),
                'text': gettext('Users') }],
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
            # Users without roles are students
            'roles': sorted_roles(form.roles.data) or ['student'],
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
        return flask.redirect(flask.url_for('get_users_admin', **request_params()))

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
        return flask.redirect(flask.url_for('get_users_admin', **request_params()))

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
        progress, runs, enrollments, and professor repos with their courses and the enrollments in
        them, which the database deletes in cascade, and their folder in DATA_FOLDER with their
        student repo and the clones of their professor repos. The activity log keeps what they
        did. The number of the user is never given again """
        username, folder = db_user.username, user_folder(db_user.username)
        db.session.delete(db_user)
        db.session.commit()
        # After the commit, so the folder is kept if the database did not delete the user. Only
        # backups recover it
        if os.path.isdir(folder):
            try:
                shutil.rmtree(folder)
            except OSError:
                flask.current_app.logger.exception('could not delete the folder of %s', username)
        log_event('user_delete', { 'username': username })
        flask.flash(gettext('User %(username)s deleted.', username=username), 'warning')
        return flask.redirect(flask.url_for('get_users_admin', **request_params()))

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
