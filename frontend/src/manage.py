""" Manage the frontend from the command line of the server:

    python manage.py admin [username]                    # make admin
    python manage.py import                              # make users
    python manage.py log output.zip                      # the activity log and its analysis tables
    python manage.py submissions output.zip              # the code of the runs, by submission
    python manage.py repo-job kind username [repo_id]    # a background job of a repo of a user

admin creates an administrator, or resets the password of a user and makes it administrator. It
runs in the server, so the first administrator, and one who lost their password, never depend on
the web application, where administrators give and take the role of the others, and import
users from files. import creates and updates the tables of the database; make runs it before
starting the servers. log and submissions write the archives that administrators download from
the web application. repo-job runs a job on the student repo of a user (solutions, history, or
push), or on one of their professor repos, given by its id (pull); the web application starts it
in the background (see repo_jobs.py). Their logic lives in users.py, activity_log.py, and
repo_jobs.py, so the web application may reuse it """
import getpass
import sys

from werkzeug.security import generate_password_hash

from db import db
from activity_log import write_archive, log_event
from courses import CourseController
from main import app
from repos.repo_jobs import RepoJob
from users import MAX_PASSWORD_LENGTH, MAX_USERNAME_LENGTH, LoginAttempt, User, sorted_roles

USAGE = ('Usage: python manage.py admin [username] | import | log output.zip'
    ' | submissions output.zip | repo-job kind username [repo_id]')

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
        print(f'User {username} exists with roles {" ".join(user.roles)}: its password will be '
            'reset, and it will be admin too')
    else:
        print(f'User {username} does not exist: it will be created with role admin')
        user = User(username=username, fullname=ask_text('Full name: ', 128), roles=[])
        db.session.add(user)
    user.password = generate_password_hash(ask_password())
    # The other roles are kept, e.g. a director who is also administrator
    user.roles = sorted_roles({ *user.roles, 'admin' })
    # A suspended user made administrator must be able to log in
    user.status = 'active'
    # A forgotten password may have blocked the logins of the administrator
    db.session.execute(db.delete(LoginAttempt).filter(LoginAttempt.username == username))
    db.session.commit()
    log_event(event, { 'source': 'make admin' }, user=username, role=' '.join(user.roles))
    print(f'Administrator {username} is ready, log in at /user')
    return 0

# Import ------------------------------------------------------------------------------------------

def import_users() -> int:
    """ Create and update the tables of the database. Return the exit status """
    update_database()
    # Nobody can log in without users. The first administrator is created in the server
    if not db.session.scalar(db.select(User.id).limit(1)):
        print('manage: there are no users yet. Create the administrator with: make admin')
    return 0

def update_database():
    """ Create the tables that do not exist yet (users, their progress, single sign-on...) and
    update the users table of older databases. It runs in a single process, before the servers
    start, because the gunicorn workers would create the same tables at the same time """
    db.create_all()
    update_users_table()
    cascade_user_deletes()

def update_users_table():
    """ Add the columns that older users tables lack (existing rows get their default value),
    turn the role of each user into a list of roles, widen the usernames, and make passwords
    optional, for the users of single sign-on """
    columns = {column['name'] for column in db.inspect(db.engine).get_columns('users')}
    # The color scheme column was first named interface_mode, rename it to keep its values
    if 'interface_mode' in columns and 'color_scheme' not in columns:
        db.session.execute(db.text(
            "ALTER TABLE users RENAME COLUMN interface_mode TO color_scheme"))
    # Users had a single role, each one keeps it as their list of roles
    if 'role' in columns and 'roles' not in columns:
        db.session.execute(db.text("ALTER TABLE users ALTER COLUMN role DROP DEFAULT,"
            " ALTER COLUMN role TYPE VARCHAR(16)[] USING ARRAY[role]"))
        db.session.execute(db.text("ALTER TABLE users RENAME COLUMN role TO roles"))
    db.session.execute(db.text("ALTER TABLE users"
        " ADD COLUMN IF NOT EXISTS roles VARCHAR(16)[] NOT NULL DEFAULT '{student}',"
        " ADD COLUMN IF NOT EXISTS color_scheme VARCHAR(8) NOT NULL DEFAULT 'default',"
        " ADD COLUMN IF NOT EXISTS font VARCHAR(16) NOT NULL DEFAULT 'anaheim',"
        " ADD COLUMN IF NOT EXISTS language VARCHAR(8) NOT NULL DEFAULT 'default',"
        " ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'active',"
        f" ALTER COLUMN username TYPE VARCHAR({MAX_USERNAME_LENGTH}),"
        " ALTER COLUMN roles SET DEFAULT '{student}',"
        " ALTER COLUMN password DROP NOT NULL"))
    db.session.commit()

def cascade_user_deletes():
    """ Make the foreign keys to the users table that the models declare with ON DELETE CASCADE
    (progress, runs...) delete in cascade in older databases too, whose tables were created
    without it, so deleting a user deletes all their data. db.create_all() does not change the
    tables that exist. Names come from the models and the database, never from users """
    inspector = db.inspect(db.engine)
    for table in db.metadata.sorted_tables:
        cascades = {key.parent.name for key in table.foreign_keys
            if key.column.table.name == 'users' and key.ondelete == 'CASCADE'}
        for key in inspector.get_foreign_keys(table.name):
            columns = key['constrained_columns']
            column = columns[0] if len(columns) == 1 else None
            if (key['referred_table'] != 'users' or column not in cascades
                    or key['options'].get('ondelete', '').upper() == 'CASCADE'):
                continue
            # Dropped and added in one statement, so the table is never without the constraint
            db.session.execute(db.text(f'ALTER TABLE "{table.name}"'
                f' DROP CONSTRAINT "{key["name"]}",'
                f' ADD CONSTRAINT "{key["name"]}" FOREIGN KEY ("{column}")'
                ' REFERENCES users (id) ON DELETE CASCADE'))
            print(f'manage: {table.name}.{column} now deletes in cascade with its user')
    db.session.commit()

# Activity log -----------------------------------------------------------------------------------

def export_archive(kind: str, output: str = None) -> int:
    """ Write the archive of the activity log of the given kind (log or submissions) to the output
    file. Return the exit status """
    if output is None:
        print(USAGE, file=sys.stderr)
        return 2
    with open(output, 'wb') as file:
        write_archive(kind, file, CourseController.load_all_courses)
    print(f'manage: {kind} archive written to {output}')
    return 0

# Repos of the users -------------------------------------------------------------------------------

def run_repo_job(kind: str = None, username: str = None, repo_id: str = None) -> int:
    """ Run the job of the kind on the student repo of the user, or on their professor repo of
    the given id. Return the exit status """
    try:
        job = RepoJob(username, kind, int(repo_id) if repo_id is not None else None)
    except ValueError:
        job = None
    if not job or not username:
        print(USAGE, file=sys.stderr)
        return 2
    return job.run()

# Main --------------------------------------------------------------------------------------------

# Subcommands and the functions that run them with optional arguments: one, or the number in
# MAX_ARGUMENTS
COMMANDS = {
    'admin': manage_admin,
    'import': import_users,
    'log': lambda output=None: export_archive('log', output),
    'submissions': lambda output=None: export_archive('submissions', output),
    'repo-job': run_repo_job,
}
MAX_ARGUMENTS = { 'repo-job': 3 }

def main() -> int:
    """ Run the subcommand of the command line. Return the exit status: 0 on success """
    if (len(sys.argv) < 2 or sys.argv[1] not in COMMANDS
            or len(sys.argv) - 2 > MAX_ARGUMENTS.get(sys.argv[1], 1)):
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
