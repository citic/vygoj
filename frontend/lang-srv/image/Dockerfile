# Image of the containers where the language servers run, one container for each code editor.
# The release is pinned for reproducible builds; rebuild the image regularly (make image) to receive
# security updates
FROM debian:trixie

# Install the language servers and the headers of the libraries that solutions include, and remove
# the package lists to reduce the image size
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    clangd \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Folder of the solution files, as in the engine of the backend. Editors send the code in their
# messages, but clangd needs the folder to exist. Its options apply to the files in the folder
RUN mkdir /home/student
COPY clangd.yaml /home/.clangd
