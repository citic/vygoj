# Inherit the official Debian image as the base
FROM debian:latest

# Install development packages
RUN apt update && \
    apt install -y \
    build-essential \
    checkstyle \
    clang \
    doxygen \
    linux-perf \
    python3 \
    valgrind

# Future packages
    # libgmp-dev \
    # mpich \

# Create a non-root user to run students' solutions
RUN useradd -m -s /bin/bash student -G dialout

# Switch to the student user
USER student
WORKDIR /home/student

# Set the default command to run a shell
CMD ["/bin/bash"]
