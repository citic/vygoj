all: debug
dev: node_modules

include ../common/Makefile

# Submissions wait for a backend, so threads keep the frontend responsive meanwhile
THREADS=16# Number of threads per gunicorn worker

# Each dependency accepts the updates of its current major version (e.g. ~=3.0 is >=3.0,<4), which
# fix bugs and security issues; a new major version may break the code, so it is updated by hand.
# Packages in version 0.x may break in any minor version, so their minor version is fixed too
DEPS+=authlib~=1.0 flask-babel~=4.0 flask-squeeze~=5.0 flask-sqlalchemy~=3.0 flask-talisman~=1.0 \
    flask-wtf~=1.0 markdown~=3.0 nh3~=0.3.0 psycopg~=3.0 psycopg-binary~=3.0 requests~=2.0

# Create and update the tables of the database, and add the new users of the TSV file set in
# config.py, if it exists, before running the web app. It runs once, before gunicorn starts its
# workers, which would otherwise create the same tables at the same time and fail
run release server: users

# The servers show the interface in the languages of translations/, compiled from their .po files
run release server: translations

# Folder with a subfolder for each language of the interface, e.g. translations/es/LC_MESSAGES
TRANSLATIONS=translations

.PHONY: admin lint-static translations update-translations users
users: install
	$(ACT) && cd $(SRC) && python manage.py import

# Create an administrator, or reset the password of a user and make it administrator. Optional
# username: make admin ADMIN=name (not USER, which make takes from the environment)
admin: install
	$(ACT) && cd $(SRC) && python manage.py admin $(ADMIN)

# Compile the translations (.po files) to the .mo files that the servers read
translations: install
	$(ACT) && pybabel compile -d $(TRANSLATIONS)

# Collect the texts of the interface marked with _() in the files of babel.cfg into messages.pot,
# and add the new texts to the .po file of every language, ready to be translated
update-translations: install
	$(ACT) && pybabel extract -F babel.cfg -k lazy_gettext -o $(TRANSLATIONS)/messages.pot \
		--no-location --sort-output . && pybabel update -i $(TRANSLATIONS)/messages.pot \
		-d $(TRANSLATIONS) --no-fuzzy-matching

node_modules:
	npm i

# Lint the client code in static/ besides the Python code (pylint rule of the common Makefile)
lint: lint-static

# Stylelint runs even if ESLint fails, so one run reports the problems of both, and the rule fails
# if any of them fails
lint-static: node_modules
	npx eslint static/js; status=$$?; npx stylelint 'static/css/**/*.css' || status=1; exit $$status
