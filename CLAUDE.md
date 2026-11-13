# VygOJ: Vygotsky Online Judge

An educational online programming judge with emphasis on concurrent programming. It is made of
independent processes that communicate through HTTP/JSON. Each layer has its own `CLAUDE.md`
with its specific layout, commands, and rules; this file holds what is common to all of them.

| Layer | Folder | Stack |
|---|---|---|
| Frontend (web application, server side) | `frontend/` | Python, Flask, Jinja2 |
| Frontend client | `frontend/static/` | Vanilla HTML, CSS, JavaScript |
| Backend (code execution web service) | `backend/` | Python, Flask, `docker` SDK |
| Engine (isolated execution environment) | `backend/engine/` | Docker image (Debian) |

Flow: the browser talks to the frontend; the frontend sends a problem and a solution to a backend
(`BACKENDS` in `frontend/config/config.py`, port 9090 by default); the backend runs the solution
inside a disposable engine container and returns an `ExecutionResult`. Other folders: `common/`
(shared `Makefile` and `vyg` Python package), `docs/` (analysis and design, in Spanish), `cli/`
(legacy Node.js tool).

## Development phase

VygOJ is in development (frontend and backend are in version 0.x.y), and no course uses it now.
The owner controls every frontend and backend in production and updates them together, so:

- Do not keep backward compatibility: change the HTTP/JSON protocol, the shared model, the
  database schema, stored data, and file formats as needed, and remove old formats and code paths
  instead of supporting both. Mention the changes that need a coordinated deploy or a database
  migration when reporting.
- This section stays until the owner announces that VygOJ is in production; then replace it with
  rules to keep compatibility.

## Language

- All source code, identifiers, comments, docstrings, log messages, UI text, and commit messages
  are written in English, even when the conversation with Claude is in Spanish or another
  language.
- Existing documents keep their language: `docs/*.es.adoc` are in Spanish.

## Shared model

- The `vyg` package in `common/vyg/` holds the data model shared by frontend and backend
  (`Problem`, `TestCase`, `Status`, `ExecutionResult`...), and `TsvLog`, the writer of their logs
  (the activity log of the frontend and the run log of the backend). `make deps` installs it in editable mode
  (`pip install -e ../common`) into the `.venv` of each layer, so a change affects both layers
  without reinstalling. Keep it free of Flask-specific code, file loading, and rendering (the
  frontend loads problems from disk in `frontend/src/problem_loader.py`), and declare its own
  dependencies in `common/pyproject.toml`.
- Each class lives in its own module named in `snake_case` (`execution_result.py` holds
  `ExecutionResult`). Test cases are the exception: `testcase.py` and `testcase_result.py` avoid
  the `test_*.py` pattern of pytest, and their classes set `__test__ = False`. Constants and
  enumerations (`Status`) are in `constants.py` and helper functions in `utils.py`.
  `vyg/__init__.py` re-exports the public names, so layers write `vyg.Problem`. Add new public
  names there and to `__all__`.
- `frontend/static/js/vyg.js` mirrors that model on the client. Keep the three in sync: `Status`
  values and the fields of the model cross the HTTP boundary, so change them in the three at once.
- Objects travel as compact JSON (`vyg.to_json()`), with the attribute names as keys and empty
  values omitted (readers use the same defaults). Texts travel as JSON strings, which carry any
  Unicode character; do not encode them again (e.g. base64).

## Commands and testing

The Python layers include `common/Makefile`, so these rules work in `frontend/` and `backend/`
(ports and extra rules are in each layer's `CLAUDE.md`):

```sh
make install   # create .venv and pip install the dependencies listed in DEPS
make           # debug server (FLASK_DEBUG=1 flask run)
make release   # run src/main.py without debug
make server    # gunicorn daemon (production), logs and pid file in data/
make stop      # stop the gunicorn daemon started by make server
make deps      # reinstall Python dependencies into .venv
make lint      # Pylint on src/ and common/vyg/ (installs pylint into .venv the first time)
make clean     # remove .venv
```

- `make lint` must pass with no messages. Its configuration is shared in `common/pylintrc`; fix the
  code rather than disabling a check, and when a disable is justified, put it on the line with a
  comment explaining why (e.g. `# pylint: disable=broad-exception-caught`).

- Add Python dependencies to `DEPS` in the layer's `Makefile` (there are no requirements files),
  then run `make deps`. Fix only their major version with `~=`, so they get the fixes of their
  authors, but a new major version, which may break the code, needs a manual update:
  `flask~=3.0` is `>=3.0,<4`. Packages in version 0.x may break in any minor version, so fix their
  minor version too: `nh3~=0.3.0` is `>=0.3.0,<0.4`. Do not use `<` or `>` in `DEPS`: the shell
  would read them as redirections.
- There is no automated test suite. To test end to end: build the engine image
  (`cd backend/engine && make image`, Docker running), start the backend (`cd backend && make`),
  start the frontend (`cd frontend && make`), and run a problem from its page in the browser.
  Report which of these steps were actually run.

## Workflow

- Ask the developer before applying important design decisions to the code: changes to the
  architecture, the HTTP/JSON protocol, the shared model, the database schema, file formats or
  the layout of stored data, and new dependencies. Propose the options with a recommendation, and
  wait for the answer.
- Leave changes in the working directory, without committing them, unless the prompt asks for a
  commit.

## Coding conventions

- Apply good programming practices: small cohesive functions and classes, meaningful names, no
  duplicated logic, clarity over cleverness. Do not add dependencies for what the standard library
  or the existing stack already does.
- Python: PEP 8 and the existing style: 4-space indentation, lines up to 100 characters,
  `""" Docstrings with surrounding spaces """` on every module, class, and function, and short
  comments explaining *why* before non-obvious statements.
- Command-line scripts have a single exit point: functions return or raise exceptions, never call
  `sys.exit()`; `main()` returns the exit status (0 on success) and only the entry point calls
  `sys.exit(main())`, so the shell and make know whether the script failed.
- Mark pending work with `TODO(<user>): ...`.
- Match the style of the surrounding code; review a few neighboring files before writing new code.

## Security

This system receives code and input from untrusted users. Security always comes first; avoid code
that enables attacks or system crashes.

- Treat all external data as untrusted: HTTP requests, submitted code, test cases, course repos,
  `localStorage`. Validate types and bound sizes before using it.
- Never build shell commands, SQL, file paths, or HTML by concatenating untrusted data.
- Every network call, subprocess, and container command must have a timeout. Avoid unbounded
  loops, recursion, memory, or output driven by user input (denial of service).
- Handle errors so one failing request cannot crash a server; log details, but never show stack
  traces, secrets, or host paths to users.
- Never commit secrets or local data: `config/config.py`, `config.json`, `data/`, `vygdata/`,
  `.venv/`, logs (see `.gitignore`).
- Prefer adding restrictions over removing them; when a change weakens a security control,
  say so explicitly and explain why.

## Documentation

- When a change alters documented behavior, update the affected documentation in the same change:
  docstrings and comments of the modified code, the layer's `readme.adoc`, and the root
  `readme.adoc` if commands, setup, or architecture change.
- Only update what the change makes inaccurate; do not rewrite unrelated sections.
- Keep each document in its existing language and AsciiDoc style.
- If a change contradicts `docs/analysis.es.adoc` or `docs/design.es.adoc`, point it out instead
  of silently editing them.
- Mention the documentation files that were updated when reporting the change.
