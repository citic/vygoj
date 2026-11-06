# Inherit the official Debian image as the base. The release is pinned for reproducible builds;
# rebuild the image regularly to receive security updates, also in execution.py
FROM debian:trixie

# Install development packages, and remove the package lists to reduce the image size
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    checkstyle \
    clang \
    cpplint \
    doxygen \
    gdb \
    linux-perf \
    python3 \
    time \
    valgrind \
    && rm -rf /var/lib/apt/lists/*

# Future packages
    # libgmp-dev \
    # mpich \

# Create a non-root user to run students' solutions, without extra groups. The uid is fixed
# because the backend gives it the ownership of the copied files (STUDENT_UID in execution.py)
RUN useradd -m -u 1000 -s /bin/bash student

# Switch to the student user
USER student
WORKDIR /home/student

# Set the default command to run a shell
CMD ["/bin/bash"]
