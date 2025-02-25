.PHONY: build clean run

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
