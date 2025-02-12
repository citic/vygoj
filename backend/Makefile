# Flask Makefile v1.0.1
VENV=.venv# Folder where the virtual environment is installed
ACT=. $(VENV)/bin/activate# Python command to activate the virtual environment
SRC=src#Folder where web application source code is
MAIN=$(SRC)/main.py# Start point of the backend source code
DEPS=flask# Python dependecies to be installed with pip install
SHELL:=/bin/bash# Use bash to run complex commands
HOST=localhost# 0.0.0.0 allows external connections, localhost does not
PORT=2358# Port where the backed will listen for connections
PY=python3# Command to run python

# Phony targets
.PHONY: clean debug install release
default: debug
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

# Install dependencies
install: $(VENV)

# A Python virtual environment is required with Flask installed
$(VENV):
	$(PY) -m venv $(VENV)
	$(ACT) && pip install $(DEPS)

# Remove installation
clean:
	rm -rf $(VENV)
