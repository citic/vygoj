# Inherit the official Debian image as the base
FROM debian:latest

# Install development packages
RUN apt update && \
    apt install -y \
    build-essential \
    checkstyle \
    clang \
    doxygen \
    python3 \
    valgrind

# Future packages
    # libgmp-dev \
    # linux-perf \
    # mpich \

# Enable to run linux-perf without root in current session
# TODO(jhc): Fails because read-only file system
#RUN echo 1 > /proc/sys/kernel/perf_event_paranoid
# Makes the change permanent
#RUN echo kernel.perf_event_paranoid=1 > /etc/sysctl.d/local.conf

# Create a non-root user to run students' solutions
RUN useradd -m -s /bin/bash student

# Switch to the student user
USER student
WORKDIR /home/student

# Set the default command to run a shell
CMD ["/bin/bash"]
