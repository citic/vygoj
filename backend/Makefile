include ../common/Makefile

DEPS+=docker~=7.0# Python dependencies for pip install, each one with its major version
PORT=9090# Port where the backend will listen for connections
WORKERS=8# Number of gunicorn workers, it also bounds the number of concurrent executions
# Send the print() output of the backend to the error log
GUNICORN_FLAGS+=--capture-output

.PHONY: all docker-check engine-rebuild

all: debug

# Gunicorn would start without Docker and its workers would fail in the background, so check it
# first. Without Docker, execution.py prints a message and exits with status 4
server service: docker-check
docker-check: install
	$(ACT) && cd $(SRC) && python3 -c 'import execution'

# make update also rebuilds the image of the engine, for the security updates of its packages
post-pull: engine-rebuild
engine-rebuild:
	$(MAKE) -C engine rebuild
