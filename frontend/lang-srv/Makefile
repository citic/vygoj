include ../../common/Makefile

SHARED=../../common# Folder of the vyg package and the configuration shared by the layers
DEPS+=flask-sock~=0.7.0# Python dependencies for pip install, each one with its major version
PORT=7070# Port where the language server will listen for connections
# One process counts the sessions of every user (src/main.py), and each WebSocket keeps one of its
# threads busy while its user edits code. More threads than MAX_SESSIONS (config/defaults.py) refuse
# the connections beyond it, instead of leaving them waiting for a thread
WORKERS=1# Number of gunicorn worker processes
THREADS=120# Number of threads of the worker
# Send the print() output of the language server to the error log
GUNICORN_FLAGS+=--capture-output
IMAGE=vygoj-lang-srv# Docker image of the language servers, IMAGE in config/defaults.py

.PHONY: all image

all: debug

# Build the image of the containers where the language servers run, from image/Dockerfile
image:
	docker build -t $(IMAGE) image
