""" Migration of the new users in a TSV file (username, password) to the users table """
import csv
import os
import sys

from werkzeug.security import generate_password_hash

from db import db
from main import app
from users import User

def get_users_file():
    """ Path of the users file: the argument, if given, or USERS_FILE in DATA_FOLDER """
    if len(sys.argv) > 2:
        sys.exit('Usage: python migrate_users.py [users.tsv]')
    if len(sys.argv) == 2:
        return sys.argv[1]
    # The file has plain passwords, so it is kept out of git in the data folder
    return os.path.join(app.config['DATA_FOLDER'],
        app.config.get('USERS_FILE', 'users-passwords.tsv'))

def migrate_users(users_file):
    """ Add the users of the given file that are not in the database yet """
    with open(users_file, encoding='utf-8', newline='') as file, app.app_context():
        for row in csv.DictReader(file, delimiter='\t'):
            username = row['username']
            # Skip users already migrated, so this script can be run again safely
            if not db.session.scalar(db.select(User).filter_by(username=username)):
                # Full name is required, but the file has none, so use the username
                db.session.add(User(username=username, fullname=username,
                    password=generate_password_hash(row['password'])))
        db.session.commit()

def main():
    """ Migrate the users file, if it exists """
    users_file = get_users_file()
    # A missing file is not an error, because make runs this script before every start
    if not os.path.isfile(users_file):
        print(f'migrate_users: no users file {users_file}, skipped')
        return
    migrate_users(users_file)

if __name__ == '__main__':
    main()
