all: debug
dev: node_modules

include ../common/Makefile

# Submissions wait for a backend, so threads keep the frontend responsive meanwhile
THREADS=16# Number of threads per gunicorn worker

# Each dependency accepts the updates of its current major version (e.g. ~=3.0 is >=3.0,<4), which
# fix bugs and security issues; a new major version may break the code, so it is updated by hand.
# Packages in version 0.x may break in any minor version, so their minor version is fixed too
DEPS+=flask-squeeze~=5.0 flask-sqlalchemy~=3.0 flask-talisman~=1.0 flask-wtf~=1.0 markdown~=3.0 \
    nh3~=0.3.0 psycopg~=3.0 psycopg-binary~=3.0 requests~=2.0

# Add the new users of the TSV file set in config.py, if it exists, to the database before running
# the web app
run: users

.PHONY: admin lint-static users
users: install
	$(ACT) && cd $(SRC) && python manage.py import

# Create an administrator, or reset the password of a user and make it administrator. Optional
# username: make admin ADMIN=name (not USER, which make takes from the environment)
admin: install
	$(ACT) && cd $(SRC) && python manage.py admin $(ADMIN)

node_modules:
	npm i

# Lint the client code in static/ besides the Python code (pylint rule of the common Makefile)
lint: lint-static

# Stylelint runs even if ESLint fails, so one run reports the problems of both, and the rule fails
# if any of them fails
lint-static: node_modules
	npx eslint static/js; status=$$?; npx stylelint 'static/css/**/*.css' || status=1; exit $$status
