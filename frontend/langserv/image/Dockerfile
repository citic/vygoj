# Image of the containers where the language servers run, one container for each code editor.
# The release is pinned for reproducible builds; rebuild the image regularly (make rebuild) to
# receive security updates

# Download the language server of Java from Eclipse, which Debian does not package, in a stage of
# its own, so the image does not keep the archive. Its version is fixed and its download checked
# against its SHA-256, so a changed file stops the build. Update both from
# https://download.eclipse.org/jdtls/milestones/ when a new version comes out
FROM debian:trixie AS jdtls
ARG JDTLS=1.63.0/jdt-language-server-1.63.0-202610191322.tar.gz
ARG JDTLS_SHA256=b1f2abe0b3cccb462cf64fb4a5587c7d09df60cf8be7748b152cbd89d018bdc4
ADD --checksum=sha256:$JDTLS_SHA256 https://download.eclipse.org/jdtls/milestones/$JDTLS /tmp/jdtls.tar.gz
RUN mkdir /opt/jdtls && tar -xzf /tmp/jdtls.tar.gz -C /opt/jdtls

FROM debian:trixie
# make rebuild removes the old images with this label (common/docker.mk)
LABEL vygoj=langserv

# Install the language servers, the headers of the libraries that solutions include, and the Java
# that jdtls needs, and remove the package lists to reduce the image size
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    clangd \
    libc6-dev \
    libstdc++-14-dev \
    openjdk-25-jre-headless \
    python3-pylsp \
    && rm -rf /var/lib/apt/lists/*

COPY --from=jdtls /opt/jdtls /opt/jdtls
RUN ln -s /opt/jdtls/plugins/org.eclipse.equinox.launcher_*.jar /opt/jdtls/launcher.jar
COPY jdtls /usr/local/bin/jdtls
COPY pylsp-files /usr/local/bin/pylsp-files

# Folder of the solution files, as in the engine of the backend. Editors send the code in their
# messages, but clangd needs the folder to exist. Its options apply to the files in the folder.
# Each container mounts a small folder in memory on it, where pylsp-files writes the files of
# Python solutions
RUN mkdir /home/student
COPY clangd.yaml /home/.clangd
