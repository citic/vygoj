include ../common/Makefile

DEPS+=docker gunicorn# Python dependencies to be installed with pip install
HOST=localhost# 0.0.0.0 allows external connections, localhost does not
PORT=9090# Port where the backend will listen for connections
THREADS=8# Number of threads to run the web application/service

all: debug
