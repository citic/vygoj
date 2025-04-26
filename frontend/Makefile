DEPS+=requests# Python dependencies to be installed with pip install

all: dev debug
install: node_modules

include ../common/Makefile

.PHONY: dev
dev:
	npm run dev &

node_modules:
	npm ci
