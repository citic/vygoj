""" Migration of the new users in a TSV file (username, password) to the users table """
import csv
import sys

from werkzeug.security import generate_password_hash

from db import db
from main import app
from users import User

# The file has plain passwords, so it is kept out of git and its path is given as an argument
if len(sys.argv) != 2:
    sys.exit('Usage: python migrate_users.py users.tsv')

with open(sys.argv[1], encoding='utf-8', newline='') as file, app.app_context():
    for row in csv.DictReader(file, delimiter='\t'):
        username = row['username']
        # Skip users already migrated, so this script can be run again safely
        if not db.session.scalar(db.select(User).filter_by(username=username)):
            # Full name is required, but the file has none, so use the username
            db.session.add(User(username=username, fullname=username,
                password=generate_password_hash(row['password'])))
    db.session.commit()
