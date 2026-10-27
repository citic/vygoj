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
(shared `Makefile`), `docs/` (analysis and design, in Spanish), `cli/` (legacy Node.js tool).

## Language

- All source code, identifiers, comments, docstrings, log messages, UI text, and commit messages
  are written in English, even when the conversation with Claude is in Spanish or another
  language.
- Existing documents keep their language: `docs/*.es.adoc` are in Spanish.

## Shared model

- `frontend/src/vyg.py` holds the data model shared by frontend and backend (`Problem`,
  `TestCase`, `Status`, `ExecutionResult`...). `backend/src/vyg.py` is a symlink to it, so a change
  affects both layers. Keep it free of Flask-specific code.
- `frontend/static/js/vyg.js` mirrors that model on the client. Keep the three in sync, and keep
  `Status` values and `ExecutionResult` fields stable since they cross the HTTP boundary.

## Commands and testing

The Python layers include `common/Makefile`, so these rules work in `frontend/` and `backend/`
(ports and extra rules are in each layer's `CLAUDE.md`):

```sh
make install   # create .venv and pip install the dependencies listed in DEPS
make           # debug server (FLASK_DEBUG=1 flask run)
make release   # run src/main.py without debug
make server    # gunicorn daemon (production)
make deps      # reinstall Python dependencies into .venv
make clean     # remove .venv
```

- Add Python dependencies to `DEPS` in the layer's `Makefile` (there are no requirements files),
  then run `make deps`.
- There is no automated test suite. To test end to end: build the engine image
  (`cd backend/engine && make image`, Docker running), start the backend (`cd backend && make`),
  start the frontend (`cd frontend && make`), and run a problem from its page in the browser.
  Report which of these steps were actually run.

## Coding conventions

- Apply good programming practices: small cohesive functions and classes, meaningful names, no
  duplicated logic, clarity over cleverness. Do not add dependencies for what the standard library
  or the existing stack already does.
- Python: PEP 8 and the existing style: 4-space indentation, lines up to 100 characters,
  `""" Docstrings with surrounding spaces """` on every module, class, and function, and short
  comments explaining *why* before non-obvious statements.
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
