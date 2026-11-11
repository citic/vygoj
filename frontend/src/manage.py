""" Manage the frontend from the command line of the server:

    python manage.py admin [username]          # make admin
    python manage.py import [users.tsv]        # make users
    python manage.py log output.zip            # the activity log and its analysis tables
    python manage.py submissions output.zip    # the code of the runs, a folder per submission

admin creates an administrator, or resets the password of a user and makes it administrator. It
runs in the server, so only who can log in the server can create administrators, never the
visitors of the web application. import creates and updates the tables of the database, and adds
the users of a TSV file that are not in the database yet; make runs it before starting the
servers. log and submissions write the archives that administrators download from the web
application. Their logic lives in users.py and activity_log.py, so the web application may
reuse it """
import csv
import getpass
import os
import sys

from werkzeug.security import generate_password_hash

from db import db
from activity_log import write_archive, log_event
from courses import CourseController
from main import app
from users import MAX_PASSWORD_LENGTH, MAX_USERNAME_LENGTH, LoginAttempt, User

USAGE = ('Usage: python manage.py admin [username] | import [users.tsv] | log output.zip'
    ' | submissions output.zip')

# Administrators can do everything, so their passwords must not be easy to guess
MIN_PASSWORD_LENGTH = 12

# Administrators ----------------------------------------------------------------------------------

def ask_text(prompt: str, max_length: int) -> str:
    """ Ask a line of text until it is not empty and it fits in the database column """
    while True:
        text = input(prompt).strip()
        if 0 < len(text) <= max_length:
            return text
        print(f'It must have between 1 and {max_length} characters')

def ask_password() -> str:
    """ Ask the new password twice, without showing it, until both are equal and valid """
    while True:
        password = getpass.getpass('New password: ')
        if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
            print(f'It must have between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} '
                'characters')
        elif password != getpass.getpass('Repeat the new password: '):
            print('Passwords do not match')
        else:
            return password

def manage_admin(username: str = None) -> int:
    """ Ask the data of the administrator and store it. Return the exit status """
    # The administrator may be the first command run on a new database
    update_database()
    username = (username.strip() if username is not None
        else ask_text('Username: ', MAX_USERNAME_LENGTH))
    if not 0 < len(username) <= MAX_USERNAME_LENGTH:
        print(f'The username must have between 1 and {MAX_USERNAME_LENGTH} characters',
            file=sys.stderr)
        return 1
    user = db.session.scalar(db.select(User).filter_by(username=username))
    event = 'user_admin' if user else 'user_create'
    if user:
        print(f'User {username} exists with role {user.role}: its password will be reset, '
            'and its role will be admin')
    else:
        print(f'User {username} does not exist: it will be created with role admin')
        user = User(username=username, fullname=ask_text('Full name: ', 128))
        db.session.add(user)
    user.password = generate_password_hash(ask_password())
    user.role = 'admin'
    # A forgotten password may have blocked the logins of the administrator
    db.session.execute(db.delete(LoginAttempt).filter(LoginAttempt.username == username))
    db.session.commit()
    log_event(event, { 'source': 'make admin' }, user=username, role='admin')
    print(f'Administrator {username} is ready, log in at /user')
    return 0

# Import ------------------------------------------------------------------------------------------

def import_users(users_file: str = None) -> int:
    """ Update the database and add the users of the given TSV file (username and password
    columns), or of USERS_FILE in DATA_FOLDER. Return the exit status """
    update_database()
    # Nobody can log in without users. The administrator is created in the server, not in the web
    if not db.session.scalar(db.select(User.id).limit(1)):
        print('manage: there are no users yet. Create the administrator with: make admin')
    if users_file is None:
        # The file has plain passwords, so it is kept out of git in the data folder
        users_file = os.path.join(app.config['DATA_FOLDER'],
            app.config['USERS_FILE'])
    # A missing file is not an error, because make runs this script before every start
    if not os.path.isfile(users_file):
        print(f'manage: no users file {users_file}, skipped')
        return 0
    with open(users_file, encoding='utf-8', newline='') as file:
        added = User.add_new(csv.DictReader(file, delimiter='\t'))
    print(f'manage: {added} new users added from {users_file}')
    return 0

def update_database():
    """ Create the tables that do not exist yet (users, their progress, single sign-on...) and
    update the users table of older databases. It runs in a single process, before the servers
    start, because the gunicorn workers would create the same tables at the same time """
    db.create_all()
    update_users_table()

def update_users_table():
    """ Add the columns that older users tables lack (existing rows get their default value),
    widen the usernames, and make passwords optional, for the users of single sign-on """
    columns = {column['name'] for column in db.inspect(db.engine).get_columns('users')}
    # The color scheme column was first named interface_mode, rename it to keep its values
    if 'interface_mode' in columns and 'color_scheme' not in columns:
        db.session.execute(db.text(
            "ALTER TABLE users RENAME COLUMN interface_mode TO color_scheme"))
    db.session.execute(db.text("ALTER TABLE users"
        " ADD COLUMN IF NOT EXISTS role VARCHAR(16) NOT NULL DEFAULT 'student',"
        " ADD COLUMN IF NOT EXISTS color_scheme VARCHAR(8) NOT NULL DEFAULT 'default',"
        " ADD COLUMN IF NOT EXISTS font VARCHAR(16) NOT NULL DEFAULT 'anaheim',"
        " ADD COLUMN IF NOT EXISTS language VARCHAR(8) NOT NULL DEFAULT 'default',"
        f" ALTER COLUMN username TYPE VARCHAR({MAX_USERNAME_LENGTH}),"
        " ALTER COLUMN password DROP NOT NULL"))
    db.session.commit()

# Activity log -----------------------------------------------------------------------------------

def export_archive(kind: str, output: str = None) -> int:
    """ Write the archive of the activity log of the given kind (log or submissions) to the output
    file. Return the exit status """
    if output is None:
        print(USAGE, file=sys.stderr)
        return 2
    with open(output, 'wb') as file:
        write_archive(kind, file, CourseController.cache_courses)
    print(f'manage: {kind} archive written to {output}')
    return 0

# Main --------------------------------------------------------------------------------------------

# Subcommands and the functions that run them with an optional argument
COMMANDS = {
    'admin': manage_admin,
    'import': import_users,
    'log': lambda output=None: export_archive('log', output),
    'submissions': lambda output=None: export_archive('submissions', output),
}

def main() -> int:
    """ Run the subcommand of the command line. Return the exit status: 0 on success """
    if not 2 <= len(sys.argv) <= 3 or sys.argv[1] not in COMMANDS:
        print(USAGE, file=sys.stderr)
        return 2
    with app.app_context():
        return COMMANDS[sys.argv[1]](*sys.argv[2:])

if __name__ == '__main__':
    try:
        STATUS = main()
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled, nothing was changed', file=sys.stderr)
        STATUS = 1
    # The only exit point. Everything was released when main() returned; the status tells the
    # shell and make whether the command failed
    sys.exit(STATUS)
