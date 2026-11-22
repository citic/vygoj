IMAGE=vygoj-engine# Docker image of the engines, IMAGE in ../src/execution.py
CONTEXT=.# Folder of the Dockerfile of the image
CONTAINER=$(IMAGE)-interactive

.PHONY: clean run

# Run a container of the image interactively, the default rule. It is removed when it exits
run:
	docker run -it --rm --name $(CONTAINER) $(IMAGE)

# Rules image, rebuild, and remove-image, after run, which stays the default rule
include ../../common/docker.mk

# Stop and remove the Docker image and all its containers
clean: remove-image
