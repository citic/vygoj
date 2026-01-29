IMAGE=debian-dev
CONTAINER=$(IMAGE)-interactive

.PHONY: image clean install official-install run stop remove-containers remove-image uninstall

# Run the Docker image
run:
	docker run -it --name $(CONTAINER) $(IMAGE):latest

# Create a Docker image from the Dockerfile
image:
	docker buildx build -t $(IMAGE):latest .

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
# Adapted from https://docs.docker.com/engine/install/debian/
official-install:
	sudo apt update
	sudo apt install ca-certificates curl
	sudo install -m 0755 -d /etc/apt/keyrings
	sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
	sudo chmod a+r /etc/apt/keyrings/docker.asc
	echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
	sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
	sudo apt update
	sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# TODO(jhc): official-uninstall rule

# Stop and remove the Docker image and all its containers
clean: remove-image

# Stop all containers created with the image
stop:
	docker stop $(shell docker ps -aq --filter ancestor=$(IMAGE))

# Stop and remove all containers, but not the image
remove-containers: stop
	docker rm $(shell docker ps -aq --filter ancestor=$(IMAGE))

# Remove the image. All its containers must be stopped and removed first
remove-image: remove-containers
	docker rmi $(IMAGE):latest
