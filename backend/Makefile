include ../common/Makefile

DEPS+=docker~=7.0# Python dependencies for pip install, each one with its major version
PORT=9090# Port where the backend will listen for connections
WORKERS=8# Number of gunicorn workers, it also bounds the number of concurrent executions
# Send the print() output of the backend to the error log
GUNICORN_FLAGS+=--capture-output

.PHONY: all docker-check

all: debug

# The gunicorn daemon would start without Docker and its workers would fail in the background, so
# check it first. Without Docker, execution.py prints a message and exits with status 4
server: docker-check
docker-check: install
	$(ACT) && cd $(SRC) && python3 -c 'import execution'
