# Flask Makefile v1.5.0
VENV=.venv# Folder where the virtual environment is installed
ACT=. $(VENV)/bin/activate# Python command to activate the virtual environment
SRC=src#Folder where web application source code is
MAIN=$(SRC)/main.py# Start point of the backend source code
DEPS=flask~=3.0 gunicorn~=26.0# Python dependencies for pip install, each one with its major version
SHARED=../common# Folder of the vyg package shared by the layers, installed in editable mode
SHELL:=/bin/bash# Use bash to run complex commands
HOST=0.0.0.0# 0.0.0.0 allows external connections, localhost does not
PORT=8080# Port where the web app will listen for connections
WORKERS=4# Number of gunicorn worker processes
THREADS=1# Number of threads per worker, more than 1 lets a worker serve requests while others wait
PY=python3# Command to run python
LOGDIR=data# Folder for logs and runtime files of the server, ignored by git
PIDFILE=$(LOGDIR)/gunicorn.pid# Process id of the gunicorn master, used by stop
GUNICORN_FLAGS=# Extra gunicorn options, layers may append to it with +=
LINT_DEPS=pylint~=4.0# Development tools, installed only by lint, not needed to run the servers
PYLINT_SRC=$(SRC) $(SHARED)/vyg# Python code checked by lint: the layer and the shared package
PYLINTRC=$(SHARED)/pylintrc# Pylint configuration shared by the layers
# LAYER, the name of the layer in its release tags (e.g. frontend-v0.2.0), is set by its Makefile

# Version of the code that the server shows: the major.minor.patch of the VERSION file of the
# layer, and its commit, the short hash and the date (e.g. 0.2.0, and ce271b1 2026-11-23)
APP_VERSION=$(shell cat VERSION)
APP_COMMIT=$(shell git log -1 --format='%h %cs')

# Phony targets
.PHONY: clean debug deps install lint pylint post-pull release server service stop update version
default: all

# The servers read their version and commit from the environment (src/main.py of each layer)
run release server service: export VYGOJ_VERSION=$(APP_VERSION)
run release server service: export VYGOJ_COMMIT=$(APP_COMMIT)

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

# Run the web app as a gunicorn daemon. Paths are relative to $(SRC) because gunicorn runs there.
# Threaded workers (gthread) serve WORKERS*THREADS requests at the same time
server: install | $(LOGDIR)
	$(ACT) && cd $(SRC) && gunicorn -w $(WORKERS) \
		--worker-class gthread --threads $(THREADS) --bind $(HOST):$(PORT) --daemon \
		--pid ../$(PIDFILE) --access-logfile ../$(LOGDIR)/access.log \
		--error-logfile ../$(LOGDIR)/error.log $(GUNICORN_FLAGS) main:app

# Run the web app with gunicorn in the foreground, for systemd (the vygoj-*.service of the layer),
# which restarts it and keeps its logs: gunicorn writes requests and errors to its output (-)
service: install
	$(ACT) && cd $(SRC) && exec gunicorn -w $(WORKERS) \
		--worker-class gthread --threads $(THREADS) --bind $(HOST):$(PORT) \
		--access-logfile - --error-logfile - $(GUNICORN_FLAGS) main:app

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

# Update the copy of VygOJ of this user: pull the new code, refusing to merge local changes, then
# run post-pull. make runs again after the pull, so post-pull comes from the Makefiles of the new
# version. The server must be restarted to run the new code
update:
	git pull --ff-only
	$(MAKE) post-pull

# Steps after pulling new code: reinstall the dependencies. Layers with a Docker image add its
# rebuild as a prerequisite
post-pull: deps

# Check the Python code with Pylint. Layers may add more checks to lint, e.g. for client code
lint: pylint
pylint: $(VENV)/bin/pylint
	$(ACT) && pylint --rcfile=$(PYLINTRC) $(PYLINT_SRC)

# Pylint is installed the first time lint runs, so servers in production do not need it
$(VENV)/bin/pylint: | $(VENV)
	$(ACT) && pip install $(LINT_DEPS)

# Show the version of the layer, or release a new one with PART=major, minor, or patch: increment
# that part of VERSION (and reset the following ones), commit only that file, and tag the commit
# (e.g. frontend-v0.3.0). Branches never change VERSION, so their merges do not conflict on it:
# releases are made in main, after merging the changes that they publish
version:
ifeq ($(PART),)
	@echo '$(APP_VERSION) $(APP_COMMIT)'
else
	@case "$(PART)" in major|minor|patch) ;; \
		*) echo 'PART must be major, minor, or patch' >&2; exit 1 ;; esac
	@test "$$(git branch --show-current)" = main || { echo 'Releases are made in main' >&2; exit 1; }
	@git diff --quiet HEAD -- VERSION || { echo 'VERSION has uncommitted changes' >&2; exit 1; }
	@IFS=. read -r major minor patch < VERSION; \
	case "$(PART)" in \
		major) major=$$((major + 1)); minor=0; patch=0 ;; \
		minor) minor=$$((minor + 1)); patch=0 ;; \
		patch) patch=$$((patch + 1)) ;; \
	esac; \
	number="$$major.$$minor.$$patch"; \
	echo "$$number" > VERSION && \
	git commit -q -m "Release $(LAYER) $$number" -- VERSION && \
	git tag -a "$(LAYER)-v$$number" -m "$(LAYER) $$number" && \
	echo "Released $(LAYER)-v$$number. Publish it: git push origin main $(LAYER)-v$$number"
endif

# Remove installation
clean:
	rm -rf $(VENV)
