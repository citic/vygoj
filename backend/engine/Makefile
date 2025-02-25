.PHONY: build clean install official-install run

# Run the Docker image
run:
	docker run -it --name debian-dev-container debian-dev:latest

# Create a Docker image from the Dockerfile
build:
	docker build -t debian-dev:latest .

# Remove the Docker image and container
clean:
	docker stop debian-dev-container
	docker rm debian-dev-container
	docker rmi debian-dev:latest

# Install Docker client and server using standard Debian packages
install:
	sudo apt install docker.io

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
