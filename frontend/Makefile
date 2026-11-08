all: debug
dev: node_modules

include ../common/Makefile

# Submissions wait for a backend, so threads keep the frontend responsive meanwhile
THREADS=16# Number of threads per gunicorn worker

DEPS+=flask-squeeze flask-sqlalchemy flask-wtf markdown nh3 psycopg psycopg-binary requests talisman

# Add the new users of the TSV file set in config.py, if it exists, to the database before running
# the web app
run: users

.PHONY: admin users
users: install
	$(ACT) && cd $(SRC) && python manage_users.py import

# Create an administrator, or reset the password of a user and make it administrator. Optional
# username: make admin ADMIN=name (not USER, which make takes from the environment)
admin: install
	$(ACT) && cd $(SRC) && python manage_users.py admin $(ADMIN)

node_modules:
	npm i
