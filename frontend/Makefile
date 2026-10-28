all: debug
dev: node_modules

include ../common/Makefile

DEPS+=flask-squeeze flask-sqlalchemy flask-wtf psycopg psycopg-binary requests talisman

# Add the new users of the TSV file, if it exists, to the database before running the web app
run: users

.PHONY: users
users: install
	if [ -f ../users-passwords.tsv ]; then $(ACT) && cd $(SRC) && python migrate_users.py ../../users-passwords.tsv; fi

node_modules:
	npm i
