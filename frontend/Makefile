all: dev debug
install: node_modules

include ../common/Makefile

DEPS+=flask-sqlalchemy flask-wtf requests

.PHONY: dev
dev:
	npm run dev &

node_modules:
	npm ci
