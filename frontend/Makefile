all: dev debug
install: node_modules

include ../common/Makefile

DEPS+=flask-sqlalchemy flask-wtf requests

.PHONY: dev
dev:
	npm run dev &

node_modules:
	npm i

# Run the frontend as a web service
server: install
	$(ACT) && cd src && gunicorn -w $(THREADS) --bind $(HOST):$(PORT) main:app --daemon &
