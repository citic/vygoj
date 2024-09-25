# Overloadable variables
VENV=.venv# Folder where the virtual environment is installed
ACT=. $(VENV)/bin/activate# Python command to activate the virtual environment
MAIN=src/main.py# Start point of the backend source code
DEPS=flask# Python dependecies to be installed with pip install
SHELL:=/bin/bash# Use bash to run complex commands
HOST=localhost# 0.0.0.0 to allow external connections
PORT=2358# Port where the backed will listen for connections

.PHONY: clean install run
default: run

# Run the backend for debugging
run: export FLASK_APP=$(MAIN)
run: export FLASK_DEBUG=1
run: $(VENV)
	$(ACT) && flask run -h $(HOST) -p $(PORT)

# Install dependencies
install: $(VENV)

# A Python virtual environment is required with Flask installed
$(VENV):
	python3 -m venv $(VENV)
	$(ACT) && pip install $(DEPS)

# Remove installation
clean:
	rm -rf $(VENV)
