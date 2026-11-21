# VygOJ frontend (server side: Flask + Jinja2)

The frontend is the web application used by students, professors, and administrators. It serves
courses and problems, authenticates users, logs activity, and forwards code submissions to one of
the configured backends (`BACKENDS` in `config/config.py`). It never runs user code itself.

Client-side code lives in `static/` and has its own `static/CLAUDE.md`.

## Layout

- `src/main.py`: Flask app, security headers (Talisman CSP), config, database setup, routes.
- `src/users.py`: users (`User`, their roles, `has_role()`), their progress (`Progress`), the
  limits of login attempts (`LoginAttempt`), and the language of the interface.
- `src/config_file.py`: `ConfigFile`, the base class of the configuration files of course repos:
  `load()` finds the first of `vygoj.json`, `vygoj.yaml`, `info.json`, and `info.yaml` in a
  folder, reads it bounded and inside the repo, parses it as JSON or as YAML without aliases
  (only JSON values), and gives the object to `interpret()`, which each subclass implements; the
  values it skips are kept in `warnings`. Questions will get their own subclass.
- `src/courses/`: package with the courses (imported as `courses.course_offer`...).
  - `course_controller.py`: `CourseController` lists the courses of the home page (prepared,
    enrolled, available), offers and enrolls them, lets only the professor, students, and
    administrators enter a course (`find_course()`), and caches each course by the commit of its
    offer.
  - `course_offer.py`: courses are in version control, and the database has their offers, which
    later will have groups (sections): `CourseOffer` (`course_offers` table: name, professor repo,
    commit, offered, hidden; prepared courses are offers not offered yet) and `Enrollment`
    (`enrollments`), and `parse_courses()`/`sync_offers()`, which turn the configuration file of a
    clone into offers after each clone or pull (see "Professor repositories and courses" in
    `readme.adoc`).
  - `course_config.py`: `CourseConfig(ConfigFile)`, the file of the root of a repo with its
    courses.
- `src/problems/`: package with the programming problems (imported as
  `problems.problem_loader`...).
  - `problem_controller.py`: `ProblemController`, the problem page: statement, runs of solutions
    in a backend, and the files of problem folders.
  - `problem_loader.py`: fills a `vyg.Problem` from its folder in a course repo (configuration
    file, statement rendered from HTML, Asciidoc with `asciidoctor`, or Markdown, initial code, and
    test cases).
  - `problem_config.py`: `ProblemConfig(ConfigFile)`, the file of a problem folder: checked fields
    of `vyg.Problem`, settings of the test cases of files, and languages, combined with the ones of
    the course by `ProblemLoader.choose_languages()`. The problem page shows the warnings
    (`Material.get_warnings()`) only to the professor who owns the repo.
- `src/sanitize.py`: `sanitize_html()` cleans HTML of course authors (statements, and content pages
  in the future) with `nh3` (allow lists of tags, attributes, CSS properties, and URL schemes;
  only videos of the content folder). It rewrites relative URLs to the files route of the content.
- `src/limits.py`: limits of the runs (time, output size). `config.py` sets an absolute range and
  a default per limit (per language if a dictionary), professors choose values in the problem,
  and `Limits` computes the effective values sent to the backend and the timeouts that follow.
- `src/sso.py`: single sign-on with OpenID Connect providers (Authlib). `SsoProvider` model
  (`sso_providers` table, configured by administrators in `/admin/users`; client secrets are in
  `SSO_CLIENT_SECRETS` of `config.py`, never in the database), `UserIdentity` (`user_identities`:
  issuer and subject of the ID tokens of each user), `SsoController` (login and callback, which
  finds, links, or creates the user), and `SsoAdminController` (provider forms).
- `src/admin.py`: `UserAdminController`, the users page of administrators (`/admin/users`): edit
  the student ID, full name, email, roles, and status of users, and suspend, activate, or delete
  them (never the logged administrator, who cannot remove their own administrator role nor change
  their status either), and import users from a CSV or TSV file (`import_users()`). Suspended
  users (`status` column of `users`) cannot log in, and
  `refresh_session()` in `users.py` logs out suspended and deleted users at their next request.
  Tables with data of users declare their foreign key with `ondelete='CASCADE'`, so deleting a
  user deletes it (`manage.py` updates the keys of older databases), and the folder of the user
  in `DATA_FOLDER` is deleted after the commit, with the clones of their professor repos.
- `src/repos/`: package with the git repos of the users (imported as `repos.git_repo`...).
  - `git_repo.py`: `GitRepo`, the operations on git repos shared by student repos and professor
    repos (commit a file at the end of a branch, versions, read, archive, merge
    branches, copy with a working tree, push over SSH only), `check_ssh_url()` for the remotes of
    users, and `user_folder()`, the folder `DATA_FOLDER/user/<username>` with the repos of each
    user.
  - `student_repo.py`: `StudentRepo(GitRepo)`, the bare git repo with the solutions that each
    user submits as a student, in `DATA_FOLDER/user/<username>/student_repo`
    (`STUDENT_REPO_NAME`), created at login, with a branch per problem and a commit per run with
    new code (`ProblemController.save_solution()`), the versions of the slider of the editor, the
    last problem of a course (the course page scrolls to it), the `main` branch that merges the
    problems for copies and pushes, and the origin of the user. It
    runs git through `subprocess` with plumbing commands and a timeout, and validates names of
    courses, problems, files, and commits before they become refs or paths (see "Student repos"
    in `readme.adoc`).
  - `professor_repo.py`: `ProfessorRepo` (`professor_repos` table: URL and folder of each repo of
    a professor) and `CourseRepo(GitRepo)`, its clone in `DATA_FOLDER/user/<username>/<repo>`
    with `main` in its working tree, which the judge only reads: clone and pull over SSH only,
    without the git config of the server, symbolic links as plain files, and its
    configuration file bounded.
  - `repo_controller.py`: `RepoController`, the routes of the Repositories section of the home
    page (`/user/repo...`, script `static/js/user/repos.js`), the professor repos only for
    professors.
  - `repo_jobs.py`: `RepoJob`, the background jobs of a student repo (zip of the last solutions,
    zip of a copy with history, push) and of each professor repo (`pull_<id>`: clone or pull,
    and sync its courses): started as `manage.py repo-job` processes with `nice` 19 and a time
    limit, with their state in `DATA_FOLDER/user/<username>/jobs/` and a lock per job.
  - `ssh_key.py`: `UserKey`, the SSH key pair of each user, never shared between users (see
    "Repositories section" in `readme.adoc`).
- `src/data_table.py`: `DataTable`, a page of the rows of a SELECT searched, filtered
  (`column:value`), sorted (with pinned columns as the first sort keys), and split in pages in the
  server with the parameters of the URL (`q`, `sort`, `pin`, `page`, `size`), and `Column`, each
  searched or sorted column. Templates show it with the macros `list_search`, `column_header`, and
  `list_pages` of `macros.html`. The users page of administrators uses it (`USER_COLUMNS`).
- `src/runs.py`: `Run` model (`runs` table) that limits the code runs of each user: one at a
  time, 5 seconds between them, 120 per hour, and the same submission answered with the stored
  result of the last run.
- `src/activity_log.py`: activity log: `log_event(event, data, **cells)` appends a row to a
  monthly TSV in `DATA_FOLDER/log/` with fixed columns (`COLUMNS`) and the fields of each event as
  JSON in `data`, and `save_code()` saves the code of a run by its hash. Events are in `EVENTS`;
  document new events and data fields in `readme.adoc`. New kinds of materials add data fields,
  not columns. It also makes the zip archives of the log on demand: the log with tables for
  statistical software (`TABLES`), and the submissions in a folder per user, course, material,
  and time, with the statement, initial code, and test cases of the problem taken from the course
  repo in the commit of each run (`git archive`, `ProblemFiles`). `LogController` serves them to administrators (`/admin/log`, `/admin/submissions`).
- `src/db.py`: SQLAlchemy instance (PostgreSQL, URI in `SQLALCHEMY_DATABASE_URI` of
  `config/config.py`).
- `src/manage.py`: command line to manage the frontend in the server. `admin [username]` creates
  an administrator, or resets the password of a user and makes it administrator (`make admin`);
  the first administrator is created here, and then administrators give and take the role of
  others in the web (never their own). `import` creates the missing tables (`db.create_all()`) and
  updates the users table; `make`, `make release`, and `make server` run it before starting,
  because gunicorn workers creating tables at the same time fail. `main.py` never changes the
  schema. Administrators import users from CSV or TSV files in `/admin/users` (`admin.py`).
  `log output.zip` and `submissions output.zip` write the archives of the activity log.
  `repo-job kind username [repo_id]` runs a background job of `repo_jobs.py`. Their logic is in
  `users.py`, `activity_log.py`, and `repo_jobs.py`, so the web application can reuse it.
- `templates/`: Jinja2 templates. `base.html` is the layout; pages extend it and fill blocks.
  Views pass data to templates in a single `it` object.
- `config/defaults.py`: default value and explanation of every setting. `main.py` loads it, and
  then `config/config.py`: local, git-ignored settings that replace only the defaults that differ.
  Add new settings to `defaults.py` and read them with `app.config['NAME']`, without fallback
  values in the code.
- `langserv/`: the language server, a process of its own with its `Makefile` (port 7070),
  `config/`, and Docker image (`image/`). `src/main.py` accepts the WebSocket of each code editor
  with a key that `lang_server_key()` of `problem_controller.py` signs with `LANG_SERVER_SECRET`,
  and passes the LSP messages to a language server in a container without network (see
  `langserv/readme.adoc`).
- `vygdata/`, `data/`: runtime data (course repos, logs). Git-ignored.

## Commands

The common `make` rules (root `CLAUDE.md`) serve the frontend on `0.0.0.0:8080`. Extra rules:

```sh
make dev       # npm i (ESLint/Stylelint tooling for static/)
make lint      # Pylint (see root CLAUDE.md), then ESLint and Stylelint on static/ (make lint-static,
               # see static/CLAUDE.md). make -k lint runs the latter even if Pylint fails
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
