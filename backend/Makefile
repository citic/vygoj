include ../common/Makefile

DEPS+=docker# Python dependencies to be installed with pip install
PORT=9090# Port where the backend will listen for connections
THREADS=8# Number of threads to run the web application/service
# Send the print() output of the backend to the error log
GUNICORN_FLAGS+=--capture-output

.PHONY: all

all: debug
