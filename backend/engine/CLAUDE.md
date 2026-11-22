# VygOJ code execution engine (Docker image)

The engine is the Docker image in which the backend compiles and runs students' solutions. The
backend (`../src/execution.py`, Python with the `docker` SDK) creates one container per
submission from this image, runs every command through `docker exec`, and destroys the container
afterwards. The parent `backend/CLAUDE.md` also applies here.

## Layout

- `Dockerfile`: Debian base with compilers and analysis tools (`build-essential`, `clang`,
  `cpplint`, `checkstyle`, `default-jdk-headless`, `valgrind`, `linux-perf`, `time`,
  `python3`...), the Alecci compiler from PyPI in a venv (`/opt/alecci`, linked as
  `/usr/local/bin/alecci`), and an unprivileged `student` user whose home `/home/student` is the
  working directory.
- `Makefile`: the image rules of `common/docker.mk`, and `run` to try the image. It never installs
  packages of the host: Docker is installed with the package manager of the distribution (see
  "Dependencies" in the root `readme.adoc`), so the rules never need `sudo`.

The image name `vygoj-engine` is a contract between this `Makefile` (`IMAGE=vygoj-engine`) and
`IMAGE` in `../src/execution.py`. Change both together. The `LABEL vygoj=engine` of the
`Dockerfile` lets `make rebuild` remove only the old images of VygOJ.

## Commands

```sh
make image                  # build vygoj-engine from the Dockerfile
make rebuild                # build it again with the updates of Debian, remove the old image
make run                    # open an interactive container to try tools manually (default rule)
make remove-image           # remove the containers of the image and the image (also make clean)
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
