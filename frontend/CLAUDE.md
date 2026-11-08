# VygOJ frontend (server side: Flask + Jinja2)

The frontend is the web application used by students, professors, and administrators. It serves
courses and problems, authenticates users, logs activity, and forwards code submissions to one of
the configured backends (`BACKENDS` in `config/config.py`). It never runs user code itself.

Client-side code lives in `static/` and has its own `static/CLAUDE.md`.

## Layout

- `src/main.py`: Flask app, security headers (Talisman CSP), config, database setup, routes.
- `src/courses.py`, `src/problems.py`, `src/users.py`: controllers for each area.
- `src/problem_loader.py`: fills a `vyg.Problem` from its folder in a course repo (`vygoj.json`,
  statement rendered from HTML, Asciidoc with `asciidoctor`, or Markdown, initial code, and test
  cases).
- `src/sanitize.py`: `sanitize_html()` cleans HTML of course authors (statements, and content pages
  in the future) with `nh3` (allow lists of tags, attributes, CSS properties, and URL schemes;
  only videos of the content folder). It rewrites relative URLs to the files route of the content.
- `src/runs.py`: `Run` model (`runs` table) that limits the code runs of each user: one at a
  time, 5 seconds between them, 120 per hour, and the same submission answered with the stored
  result of the last run.
- `src/vyg_log.py`: activity log (`vyg_log(action, ...)`) written as TSV.
- `src/db.py`: SQLAlchemy instance (PostgreSQL, URI in `SQLALCHEMY_DATABASE_URI` of
  `config/config.py`).
- `src/manage_users.py`: command line to manage users in the server. `admin [username]` creates
  an administrator, or resets the password of a user and makes it administrator (`make admin`);
  the web never creates administrators. `import [users.tsv]` updates the users table and adds the
  users of a git-ignored TSV file with plain passwords, `USERS_FILE` in `DATA_FOLDER` (both in
  `config/config.py`); `make` runs it. Their logic is in `users.py` (e.g. `User.add_new()`), so
  the web application can reuse it.
- `templates/`: Jinja2 templates. `base.html` is the layout; pages extend it and fill blocks.
  Views pass data to templates in a single `it` object.
- `config/config.py`: local, git-ignored settings (copy from `config/config-example.py`).
- `vygdata/`, `data/`: runtime data (course repos, logs). Git-ignored.

## Commands

The common `make` rules (root `CLAUDE.md`) serve the frontend on `0.0.0.0:8080`. Extra rules:

```sh
make dev       # npm i (ESLint/Stylelint tooling for static/)
make lint      # make dev if needed, then ESLint and Stylelint on static/ (see static/CLAUDE.md)
make admin     # create an administrator or reset its password (make admin ADMIN=name)
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
  (e.g. statements, which `sanitize_html()` cleans), never on raw user input.
- `/problem/<course>/<problem>/files/` serves only images, videos, and subtitles (`FILE_TYPES`)
  inside the problem folder, with a strict CSP. Never widen it to other extensions: test cases and
  solutions live there.
- `CSRFProtect` checks every POST: forms carry the token with `form.hidden_tag()`, and `fetch()`
  calls send it in the `X-CSRFToken` header (see `data-csrf-token` in `problem.html`). New
  state-changing endpoints must be POST. Never change state on GET (e.g. `/logout` is POST).
- Keep Talisman enabled. If a new CDN is needed, add only that host to the CSP in `main.py`. The
  CSP forbids inline scripts, so templates have no `<script>` blocks.
- Course repos are untrusted: read problem files only through `ProblemLoader.read_file()`, which
  keeps them inside the course repo. Answer errors with generic messages and log the details.
- The "Security" section of `readme.adoc` explains these controls; update it when they change.
- Keep `SESSION_COOKIE_SECURE` and `SESSION_COOKIE_HTTPONLY`. Store only minimal data in the
  session. Hash passwords; never log or display them.
- Limits per client (e.g. `LoginAttempt` in `users.py`) are stored in the database, because
  gunicorn workers do not share memory. Get the client address from `flask.request.remote_addr`,
  which `ProxyFix` corrects behind a reverse proxy (`TRUSTED_PROXIES` in `config.py`); never read
  `X-Forwarded-For` directly, clients can fake it.
- `requests` timeouts are in seconds. Handle `requests.exceptions.RequestException` so a down
  backend does not crash a page.

## Templates (HTML)

- Use semantic HTML5: `header`, `nav`, `main`, `article`, `section`, `aside`, `footer`,
  headings in order, `button` for actions and `a` for navigation, `label` linked to its control,
  and lists for lists. Do not use `div` when a semantic element fits.
- Name the role of elements with a class, or an `id` when they are unique in the page, also when
  no CSS or JS uses it yet: developers read the role in the markup, whatever language its text is
  in. Name every element that repeats among its siblings (the `fieldset`s of a form, the cells of
  a row) and every element whose role the element itself does not tell (`nav class="breadcrumbs"`,
  `details class="solution"`). Every `div` and `span` has a class or an `id`, unless a more
  semantic element fits: `p` for a text, `ul` for a list (also
  of cards), `dl` for names and values, `figure` and `figcaption` for an output with its title,
  `output` for the result of an action. Keep the markup compact: drop a wrapper `div` when a grid
  can place the elements without it.
- Every `img` needs a meaningful `alt` (empty `alt=""` only for decorative images), and icon-only
  buttons need `aria-label`.
- No inline `style` attributes or inline event handlers (`onclick`); styles go to `static/css/`
  and behavior to `static/js/`.
- Load page scripts as ES modules: `<script src="/js/..." type="module" async></script>`.
- One CSS class per component, in snake_case (e.g. `site_header`, `flash_messages`). CSS selects
  its parts by element (`.site_header h1`); a part whose role the element does not tell uses a
  more specific element (`dl` for names and values) or a short role class (`progress`). States
  go in standard or `data-*`/`aria-*` attributes (`hidden`, `open`, `aria-expanded`,
  `data-status`). See the CSS rules in `static/CLAUDE.md`.
