# VygOJ backend (Flask code execution web service)

The backend is a REST service that receives a problem and a student's solution from the frontend,
compiles and runs the solution inside a disposable Docker container (the engine, see
`engine/CLAUDE.md`), compares outputs against the test cases, and returns an `ExecutionResult` as
JSON. It must assume that every submitted program is malicious.

## Layout

- `src/main.py`: Flask app and endpoints: `GET /status` (health and job count) and `POST /run`
  (JSON body with `problem` and `solution`).
- `src/execution.py`: `Execution` class that drives one submission: static checks, container
  creation, file copy, compilation, test case runs, extra proofs (thread count, sanitizers,
  linting), and container removal. `languageDefaults` holds compiler and lint flags per language.
  `FailedSolution` stops the run as soon as a verdict is known.
- `src/vyg.py`: symlink to the shared model (see "Shared model" in the root `CLAUDE.md`).
- `tests/`: manual scripts. `tests001.sh` targets an old Judge0 API (port 2358) and is stale.

## Commands

The common `make` rules (root `CLAUDE.md`) serve the backend on `0.0.0.0:9090`. This `Makefile`
adds `docker` to `DEPS` and overrides `make server` (gunicorn daemon on port 9090, logs to
`backend.txt` and `error.log`).

The engine image must exist and Docker must be running before `/run` works
(`cd engine && make image`). Quick check:

```sh
curl http://localhost:9090/status
```

## Rules

- Python style is in the root `CLAUDE.md`. Add type hints on new method parameters
  (`index0:int`), as existing code does.
- Prefer the `logging` module over `print` for new diagnostics; do not add more debug `print`
  banners.

## Security

Running untrusted code is the core risk of the whole system. Every change must preserve or
improve isolation, and must never let a submission crash or exhaust the backend host.

- Untrusted code runs only inside an engine container, never on the host, and never as root.
- Container limits: keep `network_disabled=True` and `mem_limit`; prefer adding (not removing)
  limits such as `pids_limit`, `nano_cpus`, `ulimits`, `cap_drop=['ALL']`,
  `security_opt=['no-new-privileges']`, and read-only file systems with a small writable tmpfs.
  Known gap: `create_container()` currently passes `privileged=True`, which contradicts its own
  comment; do not rely on it and prefer removing it.
- Every command run in the container goes through `run_in_container(cmd, timeout)` with a
  timeout, and its output size must be capped before decoding or returning it.
- Never interpolate student-controlled data (code, test input, file names, language names) into
  shell commands. Write data to files copied with `put_archive`, use fixed file names, and accept
  only whitelisted values (e.g. languages in `languageDefaults`, tools `asan`/`tsan`/`ubsan`).
- Validate the `/run` request: correct `Content-Type`, required fields, types, and size limits for
  code and test cases. Reject anything else with a 4xx status, never a 500 with a traceback.
- Always remove containers in `finally`, even on errors, so they do not pile up.
- The backend should not be reachable from the Internet; only the frontend calls it. Do not add
  endpoints that execute arbitrary commands or expose Docker.
