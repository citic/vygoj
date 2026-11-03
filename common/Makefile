# Flask Makefile v1.2.0
VENV=.venv# Folder where the virtual environment is installed
ACT=. $(VENV)/bin/activate# Python command to activate the virtual environment
SRC=src#Folder where web application source code is
MAIN=$(SRC)/main.py# Start point of the backend source code
DEPS=flask gunicorn# Python dependencies to be installed with pip install
SHARED=../common# Folder of the vyg package shared by the layers, installed in editable mode
SHELL:=/bin/bash# Use bash to run complex commands
HOST=0.0.0.0# 0.0.0.0 allows external connections, localhost does not
PORT=8080# Port where the web app will listen for connections
THREADS=4# Number of threads to run the web application/service
PY=python3# Command to run python
LOGDIR=data# Folder for logs and runtime files of the server, ignored by git
PIDFILE=$(LOGDIR)/gunicorn.pid# Process id of the gunicorn master, used by stop
GUNICORN_FLAGS=# Extra gunicorn options, layers may append to it with +=

# Phony targets
.PHONY: clean debug deps install release server stop
default: all

debug: export FLASK_DEBUG=1
debug: run

# Run the web app for release testing.
# TODO(jhc): Use gUnicorn
release: install
	$(ACT) && python3 $(MAIN)

# Run the web app for debugging
run: export FLASK_APP=$(MAIN)
run: install
	$(ACT) && flask run -h $(HOST) -p $(PORT)

# Run the web app as a gunicorn daemon. Paths are relative to $(SRC) because gunicorn runs there
server: install | $(LOGDIR)
	$(ACT) && cd $(SRC) && gunicorn -w $(THREADS) --bind $(HOST):$(PORT) --daemon \
		--pid ../$(PIDFILE) --access-logfile ../$(LOGDIR)/access.log \
		--error-logfile ../$(LOGDIR)/error.log $(GUNICORN_FLAGS) main:app

# Stop the gunicorn daemon started by server, without affecting other gunicorn processes
stop:
	kill $$(cat $(PIDFILE))

$(LOGDIR):
	mkdir -p $(LOGDIR)

# Install dependencies
install: $(VENV)

# A Python virtual environment is required with Flask installed
$(VENV):
	$(PY) -m venv $(VENV)
	$(MAKE) deps

# The shared package is installed in editable mode, so changes to it apply without reinstalling
deps: $(VENV)
	$(ACT) && pip install $(DEPS) && pip install -e $(SHARED)

# Remove installation
clean:
	rm -rf $(VENV)
