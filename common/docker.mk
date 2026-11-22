# Rules of a Docker image of VygOJ, included by the Makefile of its folder, which sets IMAGE (its
# name) and CONTEXT (the folder of its Dockerfile). Its Dockerfile has LABEL vygoj=..., so rebuild
# removes only the old images of VygOJ

.PHONY: image rebuild remove-image

# Build the image from its Dockerfile. Docker Desktop and the official packages have the buildx
# plugin. The docker.io package of Debian 12 (Docker 20.10) lacks it, but its docker build works;
# newer versions deprecate docker build without buildx
BUILD=if docker buildx version > /dev/null 2>&1; then docker buildx build $(1); \
	else docker build $(1); fi
image:
	$(call BUILD,-t $(IMAGE) $(CONTEXT))

# Build the image again with the updates of its base image (--pull) and of its packages
# (--no-cache), for their security fixes. The name moves to the new image when it is built, so
# running containers end with the old one and new ones use the new one, without a pause of the
# service. Then remove the old images of VygOJ that no container uses
rebuild:
	$(call BUILD,--pull --no-cache -t $(IMAGE) $(CONTEXT))
	docker image prune -f --filter label=vygoj

# Remove the image and its containers, running or stopped. xargs -r runs nothing without input
remove-image:
	docker ps -aq --filter ancestor=$(IMAGE) | xargs -r docker rm -f
	docker image ls -q $(IMAGE) | xargs -r docker rmi
