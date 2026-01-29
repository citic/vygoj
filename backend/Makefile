include ../common/Makefile

DEPS+=docker# Python dependencies to be installed with pip install
PORT=9090# Port where the backend will listen for connections
THREADS=8# Number of threads to run the web application/service

.PHONY: all server

all: debug

server:
	. .venv/bin/activate && cd src && gunicorn -w 8 -b 0.0.0.0:9090 main:app --daemon --access-logfile ../backend.txt --error-logfile ../error.log --capture-output --log-level debug &
