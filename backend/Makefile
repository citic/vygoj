include ../common/Makefile

DEPS+=docker~=7.0# Python dependencies for pip install, each one with its major version
PORT=9090# Port where the backend will listen for connections
WORKERS=8# Number of gunicorn workers, it also bounds the number of concurrent executions
# Send the print() output of the backend to the error log
GUNICORN_FLAGS+=--capture-output

.PHONY: all

all: debug
