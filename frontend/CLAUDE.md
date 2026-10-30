# VygOJ frontend (server side: Flask + Jinja2)

The frontend is the web application used by students, professors, and administrators. It serves
courses and problems, authenticates users, logs activity, and forwards code submissions to one of
the configured backends (`BACKENDS` in `config/config.py`). It never runs user code itself.

Client-side code lives in `static/` and has its own `static/CLAUDE.md`.

## Layout

- `src/main.py`: Flask app, security headers (Talisman CSP), config, database setup, routes.
- `src/courses.py`, `src/problems.py`, `src/users.py`: controllers for each area.
- `src/vyg.py`: model shared with the backend (see "Shared model" in the root `CLAUDE.md`).
- `src/vyg_log.py`: activity log (`vyg_log(action, ...)`) written as TSV.
- `src/db.py`: SQLAlchemy instance (PostgreSQL, URI in `SQLALCHEMY_DATABASE_URI` of
  `config/config.py`).
- `src/migrate_users.py`: loads the new users into the database from a git-ignored TSV file with
  plain passwords. `make` runs it with `data/users-passwords.tsv`, if that file exists.
- `templates/`: Jinja2 templates. `base.html` is the layout; pages extend it and fill blocks.
  Views pass data to templates in a single `it` object.
- `config/config.py`: local, git-ignored settings (copy from `config/config-example.py`).
- `vygdata/`, `data/`: runtime data (course repos, logs). Git-ignored.

## Commands

The common `make` rules (root `CLAUDE.md`) serve the frontend on `0.0.0.0:8080`. Extra rule:

```sh
make dev       # npm i (ESLint/Stylelint tooling for static/)
```

Verify changes by running `make` and exercising the affected pages in a browser. Pages that run
code also need the backend and the engine image (see the root `CLAUDE.md`).

## Rules

- Python style is in the root `CLAUDE.md`. Section banners in this layer look like
  `# Courses ------...` padded to 100 columns.
- Controllers are classes with `@staticmethod` handlers called from routes in `main.py`. Keep
  routes thin and put logic in the controllers.

## Security

The frontend is exposed to the Internet and handles untrusted input from students. In addition
to the general rules in the root `CLAUDE.md`:

- Validate and bound sizes of form fields, JSON bodies, query strings, and URL parameters (e.g.
  course/problem names) before using them.
- Never build file system paths from user input without normalizing them and checking they stay
  inside the intended folder (path traversal). Course and problem names map to files in
  `DATA_FOLDER`.
- Use SQLAlchemy queries with bound parameters; never format SQL strings.
- Jinja2 autoescaping must stay on. Use `|safe` only on content the server generated or sanitized
  (e.g. Markdown rendered from professor-authored course repos), never on raw user input.
- Forms use Flask-WTF so they carry CSRF tokens; new state-changing endpoints must be POST and
  CSRF-protected. Never change state on GET.
- Keep Talisman enabled. If a new CDN is needed, add only that host to the CSP in `main.py`.
- Keep `SESSION_COOKIE_SECURE` and `SESSION_COOKIE_HTTPONLY`. Store only minimal data in the
  session. Hash passwords; never log or display them.
- `requests` timeouts are in seconds. Handle `requests.exceptions.RequestException` so a down
  backend does not crash a page.

## Templates (HTML)

- Use semantic HTML5: `header`, `nav`, `main`, `article`, `section`, `aside`, `footer`,
  headings in order, `button` for actions and `a` for navigation, `label` linked to its control,
  and lists for lists. Do not use `div` when a semantic element fits.
- Every `img` needs a meaningful `alt` (empty `alt=""` only for decorative images), and icon-only
  buttons need `aria-label`.
- No inline `style` attributes or inline event handlers (`onclick`); styles go to `static/css/`
  and behavior to `static/js/`.
- Load page scripts as ES modules: `<script src="/js/..." type="module" async></script>`.
- CSS classes follow the existing BEM-like naming with underscores:
  `block`, `block__element`, `block--modifier` (e.g. `site_header__title`).
