all: debug
dev: node_modules

include ../common/Makefile

DEPS+=flask-squeeze flask-sqlalchemy flask-wtf psycopg psycopg-binary requests talisman

# Add the new users of the TSV file set in config.py, if it exists, to the database before running
# the web app
run: users

.PHONY: users
users: install
	$(ACT) && cd $(SRC) && python migrate_users.py

node_modules:
	npm i
