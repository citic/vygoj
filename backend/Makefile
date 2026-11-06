include ../common/Makefile

DEPS+=docker# Python dependencies to be installed with pip install
PORT=9090# Port where the backend will listen for connections
WORKERS=8# Number of gunicorn workers, it also bounds the number of concurrent executions
# Send the print() output of the backend to the error log
GUNICORN_FLAGS+=--capture-output

.PHONY: all

all: debug
