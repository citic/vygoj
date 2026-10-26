all: debug
dev: node_modules

include ../common/Makefile

DEPS+=flask-squeeze flask-sqlalchemy flask-wtf requests talisman

node_modules:
	npm i

# Monaco editor bundle, see monaco.js
install: static/dist
static/dist: node_modules
	npm run build
