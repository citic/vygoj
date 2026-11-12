IMAGE=debian-dev
CONTAINER=$(IMAGE)-interactive

.PHONY: image clean install official-install run stop remove-containers remove-image uninstall

# Run the Docker image
run:
	docker run -it --name $(CONTAINER) $(IMAGE):latest

# Create a Docker image from the Dockerfile. Docker Desktop and the official packages have the
# buildx plugin. The docker.io package of Debian 12 (Docker 20.10) lacks it, but its docker build
# works; newer versions deprecate docker build without buildx
image:
	if docker buildx version > /dev/null 2>&1; then docker buildx build -t $(IMAGE):latest .; \
	else docker build -t $(IMAGE):latest .; fi

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

# Containers created with the image, running or stopped. Docker fails if stop or rm get no
# container, so the rules below run them only when there are some
CONTAINERS=docker ps -aq --filter ancestor=$(IMAGE)

# Stop all containers created with the image
stop:
	ids=$$($(CONTAINERS)); if [ -n "$$ids" ]; then docker stop $$ids; fi

# Stop and remove all containers, but not the image
remove-containers: stop
	ids=$$($(CONTAINERS)); if [ -n "$$ids" ]; then docker rm $$ids; fi

# Remove the image, if it exists. All its containers must be stopped and removed first
remove-image: remove-containers
	if docker image inspect $(IMAGE):latest > /dev/null 2>&1; then docker rmi $(IMAGE):latest; fi
