# Development rules of VygOJ: they run the rules of the same name of the frontend, the backend,
# and the language server, in one computer. In production each one runs on its own with its own
# user, as a systemd service (vygoj-*.service of each layer, see the production section of
# readme.adoc)

# Folders of the layers with a Python web server, and of the Docker images
LAYERS=frontend backend frontend/langserv
IMAGES=backend/engine frontend/langserv

.PHONY: all debug install config deps image rebuild remove-images update lint clean $(LAYERS)

all: debug

# Run the three debug servers at the same time: frontend on port 8080, backend on 9090, and
# language server on 7070. Ctrl+C stops them all. Their outputs are mixed in the console
debug: install
	$(MAKE) -j3 $(LAYERS)
$(LAYERS):
	$(MAKE) -C $@

# Create the virtual environment of each layer, with its Python dependencies, after the secrets of
# the configuration files, so the frontend and the language server share the same one
install: config
	for layer in $(LAYERS); do $(MAKE) -C $$layer install || exit 1; done

# Add the missing secrets to config/config.py of the frontend and the language server, without
# changing the settings that they have
config:
	python3 common/make_config.py frontend langserv

# Install the Python dependencies again, e.g. after a git pull
deps:
	for layer in $(LAYERS); do $(MAKE) -C $$layer deps || exit 1; done

# Build the Docker images of the engine and the language server
image:
	for folder in $(IMAGES); do $(MAKE) -C $$folder image || exit 1; done

# Build the images again with the security updates of Debian and its packages. Running servers
# keep working: new containers use the new images
rebuild:
	for folder in $(IMAGES); do $(MAKE) -C $$folder rebuild || exit 1; done

# Remove the images and their containers. The backend and the language server stop working until
# make image builds them again
remove-images:
	for folder in $(IMAGES); do $(MAKE) -C $$folder remove-image || exit 1; done

# Update the source code, refusing to merge local changes, then its dependencies and the images.
# make runs again after the pull, so it reads the Makefiles of the new version. Servers must be
# restarted to run the new code
update:
	git pull --ff-only
	$(MAKE) deps rebuild
	@echo 'Restart the servers, e.g. sudo systemctl restart vygoj-frontend vygoj-backend vygoj-langserv'

# Check the code of every layer, and report the problems of all of them even if one fails
lint:
	status=0; for layer in $(LAYERS); do $(MAKE) -C $$layer lint || status=1; done; exit $$status

# Remove the virtual environments
clean:
	for layer in $(LAYERS); do $(MAKE) -C $$layer clean || exit 1; done
