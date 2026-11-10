# VygOJ backend (Flask code execution web service)

The backend is a REST service that receives a problem and a student's solution from the frontend,
compiles and runs the solution inside a disposable Docker container (the engine, see
`engine/CLAUDE.md`), compares outputs against the test cases, and returns an `ExecutionResult` as
JSON. It must assume that every submitted program is malicious.

## Layout

- `src/main.py`: Flask app and endpoints: `GET /status` (health and job count) and `POST /run`
  (JSON body with `problem`, `solution`, and an optional `context` that is only logged). The
  problem carries the effective limits chosen by the frontend (`maxDuration`, `maxTotalDuration`,
  `maxOutputSize`); the backend clamps them to its own ranges in `execution.py`.
- `src/execution.py`: `Execution` class that drives one submission: static checks, container
  creation, file copy, compilation, test case runs, extra proofs (thread count, sanitizers,
  linting), and container removal. `LANGUAGE_DEFAULTS` holds compiler and lint flags per language.
  `FailedSolution` stops the run as soon as a verdict is known.
- `src/run_log.py`: log of every submission received and its verdict (`data/log/runs-*.tsv`, a
  `vyg.TsvLog`), with the context the frontend sends (user, course, material, id of its run).
  Document new columns and data fields in the "Run log" section of `readme.adoc`.
- `tests/`: manual scripts. `tests001.sh` targets an old Judge0 API (port 2358) and is stale.

## Commands

The common `make` rules (root `CLAUDE.md`) serve the backend on `0.0.0.0:9090`. This `Makefile`
adds `docker` to `DEPS`, uses 8 single-threaded workers (which bound concurrent executions), and
appends `--capture-output` to `GUNICORN_FLAGS` so `print` output goes to `data/error.log`.

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
  Never pass `privileged=True`. `put_archive` cannot write into a tmpfs, so `/home/student` stays
  on the container's writable layer (bounded by the `fsize` ulimit).
- Every command run in the container goes through `_run_in_container(argv, timeout)`: `argv` is a
  list (never a shell string), it always gets a timeout, and its output is capped at
  `MAX_OUTPUT_BYTES` before decoding.
- Never interpolate student-controlled data (code, test input, file names, language names) into
  shell commands. Write data to files copied with `put_archive`, use fixed file names, and accept
  only whitelisted values (e.g. languages in `LANGUAGE_DEFAULTS`, tools `asan`/`tsan`/`ubsan`).
- Validate the `/run` request: correct `Content-Type`, required fields, types, and size limits for
  code and test cases. Reject anything else with a 4xx status, never a 500 with a traceback.
- Always remove containers in `finally`, even on errors, so they do not pile up.
- The backend should not be reachable from the Internet; only the frontend calls it. Do not add
  endpoints that execute arbitrary commands or expose Docker.
