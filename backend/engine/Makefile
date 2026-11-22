IMAGE=vygoj-engine# Docker image of the engines, IMAGE in ../src/execution.py
CONTEXT=.# Folder of the Dockerfile of the image
CONTAINER=$(IMAGE)-interactive

.PHONY: clean install official-install run uninstall

# Run a container of the image interactively, the default rule. It is removed when it exits
run:
	docker run -it --rm --name $(CONTAINER) $(IMAGE)

# Rules image, rebuild, and remove-image, after run, which stays the default rule
include ../../common/docker.mk

# Install Docker client and server using standard Debian packages
install:
ifeq (0, $(shell which brew > /dev/null 2>&1; echo $$?)) # macOS with Homebrew
	brew install docker-desktop
else
	sudo apt install docker.io
	sudo groupadd docker || true
	sudo usermod -aG docker $(USER) || true
	newgrp docker || true
endif

# TODO(jhc): remove Docker group
uninstall: clean
	sudo apt remove docker.io

# Uninstall potential installed versions with apt
# for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do sudo apt-get remove $pkg; done
# Adapted from https://docs.docker.com/engine/install/debian/. The shell gets $$ as $, so it
# writes the architecture and the codename of the release (bookworm, trixie) in the source
official-install:
	sudo apt update
	sudo apt install ca-certificates curl
	sudo install -m 0755 -d /etc/apt/keyrings
	sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
	sudo chmod a+r /etc/apt/keyrings/docker.asc
	echo "deb [arch=$$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $$(. /etc/os-release && echo "$$VERSION_CODENAME") stable" | \
	sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
	sudo apt update
	sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# TODO(jhc): official-uninstall rule

# Stop and remove the Docker image and all its containers
clean: remove-image
