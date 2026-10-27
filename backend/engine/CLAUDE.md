# VygOJ code execution engine (Docker image)

The engine is the Docker image in which the backend compiles and runs students' solutions. The
backend (`../src/execution.py`, Python with the `docker` SDK) creates one container per
submission from this image, runs every command through `docker exec`, and destroys the container
afterwards. The parent `backend/CLAUDE.md` also applies here.

## Layout

- `Dockerfile`: Debian base with compilers and analysis tools (`build-essential`, `clang`,
  `cpplint`, `checkstyle`, `valgrind`, `linux-perf`, `time`, `python3`...), and an unprivileged
  `student` user whose home `/home/student` is the working directory.
- `Makefile`: Docker install, image build, and cleanup rules.

The image name `debian-dev:latest` is a contract between this `Makefile` (`IMAGE=debian-dev`) and
`create_container()` in `../src/execution.py`. Change both together.

## Commands

```sh
sudo make install           # install Docker (Debian packages); on macOS: make install (Homebrew)
sudo make official-install  # Debian: install Docker from Docker's official repositories
make image                  # build debian-dev:latest from the Dockerfile
make run                    # open an interactive container to try tools manually (default rule)
make stop                   # stop all containers created from the image
make remove-containers      # stop and remove them
make clean                  # remove containers and the image
```

After changing the `Dockerfile`, rebuild with `make image`, then try the tool in `make run` and
run a real submission from the frontend through the backend.

## Rules

- Keep the `Dockerfile` readable: one package per line in alphabetical order, a comment above each
  instruction explaining its purpose, and `apt` cleanup in the same `RUN` layer when adding
  packages (`rm -rf /var/lib/apt/lists/*`).
- Use the Python `docker` SDK from the backend; do not shell out to the `docker` CLI from Python.

## Security

The image runs code written by untrusted users. Every change must keep the container useless as
an attack platform and harmless to the host:

- The final `USER` must stay `student` (non-root). Do not add `sudo`, setuid binaries, or the
  student user to privileged groups. Question any extra group membership (e.g. `dialout`).
- Install only the tools that the judge needs; every extra package adds attack surface.
- No credentials, SSH keys, or network configuration in the image.
- Assume no network at run time (the backend disables it); the image must work offline.
- Prefer pinning the base image (e.g. `debian:<release>-slim`) over `debian:latest` so builds are
  reproducible, and rebuild regularly to receive security updates.
- Resource limits (memory, CPU, processes, time) are applied by the backend when creating the
  container; do not weaken them, and document in `../src/execution.py` any tool that needs
  extra permissions (e.g. `linux-perf` with `kernel.perf_event_paranoid`).
