// Repositories section of the home page: the SSH key of the logged user, their student repo, and
// the professor repos of professors. It asks for their state (GET /user/repo) and shows it, starts
// their jobs in the background (POST /user/repo/<kind> for the student repo, POST
// /user/repo/professor[/<id>] to clone or pull a professor repo), and asks for their state until
// they end, so a job that runs keeps its button disabled after a reload, or in other browsers.
// Done zips are downloaded from their links

import _ from '../i18n.js';

// Milliseconds between the checks of the state while a job runs, and to wait for an answer
const POLL_INTERVAL = 3000;
const REQUEST_TIMEOUT = 15000;
// Milliseconds that the copy button says that the key was copied
const COPIED_TIME = 2000;
// Key of localStorage with the ids of the failures of jobs that the user closed, so they stay
// hidden after a reload, and how many ids it keeps
const DISMISSED_KEY = 'vygoj.repo.dismissed';
const MAX_DISMISSED = 20;
// Icon of the Material Symbols font and name of each category of messages, in the language of
// the page
const CATEGORY_ICONS = {
  success: ['check_circle', _('Success')],
  info: ['info', _('Information')],
  warning: ['warning', _('Warning')],
  error: ['error', _('Error')],
};

// Texts of the message codes of the server (repo_jobs.py and repo_controller.py)
const REASONS = {
  empty: _('your student repo has no solutions yet: each run of a problem saves a version'),
  too_big: _('your student repo is too big'),
  no_origin: _('set the origin first'),
  timeout: _('it took too long'),
  interrupted: _('it was interrupted, try again'),
  failed: _('an error occurred, try again later'),
  host_key: _('the identity of the host of the origin changed'),
  denied: _('the origin did not accept the SSH key: add it to the repo with write access'),
  not_found: _('the origin repo does not exist, or the SSH key cannot access it'),
  rejected: _('the origin has commits that your student repo does not have: use an empty repo'),
  connect: _('could not connect to the host of the origin'),
  running: _('that job is running already'),
  busy: _('the server is running other jobs, try again in a few minutes'),
  too_soon: _('wait a minute after the last request, and try again'),
};
// Texts of the codes that mean something else for a professor repo, or only happen to them
const PROFESSOR_REASONS = {
  ...REASONS,
  too_big: _('the repository is bigger than the judge accepts'),
  host_key: _('the identity of the host of the repository changed'),
  denied: _('the repository did not accept the SSH key: add it to the repository with read access'),
  not_found: _('the repository does not exist, or the SSH key cannot access it'),
  connect: _('could not connect to the host of the repository'),
  no_main: _('the repository has no main branch'),
  no_catalog: _('the repository has no vygoj.json, vygoj.yaml, info.json, or info.yaml file in its root'),
  invalid_catalog: _('the configuration file of the repository is not a valid JSON or YAML object'),
  folder_exists: _('the judge has a folder with the name of the repository that is not a clone: ask the administrator'),
  invalid_name: _('the name of the repository may only have letters, digits, dots, hyphens, and underscores'),
  reserved_name: _('the name of the repository is reserved by the judge: rename the repository'),
  duplicate_name: _('you have another repository with the same name: rename one of them'),
  too_many: _('you cannot add more repositories'),
};
const FAILURES = {
  solutions: _('Could not make the zip of your last solutions: %(reason)s.'),
  history: _('Could not make the zip of your solution history: %(reason)s.'),
  push: _('Could not push to the origin: %(reason)s.'),
};
const READY = {
  solutions: _('The zip of your last solutions is ready until %(time)s, or until you save a new version. Then it is deleted, and you must generate it again.'),
  history: _('The zip of your solution history is ready until %(time)s, or until you save a new version. Then it is deleted, and you must generate it again.'),
};
const PUSHED = {
  pushed: _('Pushed to the origin on %(time)s.'),
  up_to_date: _('The origin was up to date on %(time)s.'),
};
// Results of the jobs of the professor repos, and their failures by whether the repo had a clone
const PULLED = {
  cloned: _('Cloned %(repo)s on %(time)s. Courses found: %(courses)s.'),
  pulled: _('Pulled %(repo)s on %(time)s. Courses found: %(courses)s.'),
};
const PULL_FAILURES = {
  clone: _('Could not clone %(repo)s: %(reason)s.'),
  pull: _('Could not pull %(repo)s: %(reason)s.'),
};

// A failed request, with the code of the error of the server (null if it did not answer) and the
// status of the answer (0 if none)
class RequestError extends Error {
  constructor(code, status) {
    super(code ?? 'no answer');
    // Code of the message of the server, e.g. busy // string|null
    this.code = typeof code === 'string' ? code : null;
    // HTTP status of the answer, 0 without answer // number
    this.status = status;
  }

  // Return the text of the error for the user, from the texts of the codes given
  text(reasons) {
    if (this.status === 0) {
      return _('could not connect to the server');
    }
    return reasons[this.code] || _('the server answered %(status)s', { status: this.status });
  }
}

// Send a request to the server, a POST with the JSON of the body and the CSRF token if a body is
// given, and return the JSON of the answer. Throw a RequestError if it fails
async function request(url, csrfToken, body = null) {
  const options = body === null ? {} : {
    method: 'POST',
    // The server rejects POST requests without the CSRF token of the session
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
    body: JSON.stringify(body),
  };
  let response;
  try {
    response = await fetch(url, { ...options, signal: AbortSignal.timeout(REQUEST_TIMEOUT) });
  } catch {
    throw new RequestError(null, 0);
  }
  const json = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new RequestError(json.error, response.status);
  }
  return json;
}

function formatTime(seconds) {
  return new Date(seconds * 1000).toLocaleString(document.documentElement.lang, { dateStyle: 'medium', timeStyle: 'short' });
}

// The messages of a repo, as a log: the notices of the last action of the user, shown until the
// next one, and the messages of the jobs in the last state. Errors have a button that closes
// them; the closed failures of jobs are kept in localStorage, so they stay closed after a reload
class MessageLog {
  constructor(list, closeLabel) {
    // The list of the messages // HTMLUListElement
    this.list = list;
    // Text of the close buttons, in the language of the page // string
    this.closeLabel = closeLabel;
    // Messages of the last action of the user // {text, category}[]
    this.notices = [];
    // Messages of the jobs in the last state, failures with an id // {id, text, category}[]
    this.jobMessages = [];
    this.list.addEventListener('click', (event) => this.dismiss(event));
  }

  // Replace the notices, and show them
  notify(...notices) {
    this.notices = notices;
    this.show();
  }

  // Replace the messages of the jobs, and show them if they changed: each check of the state sends
  // them again, and screen readers would read the same messages every time
  showJobs(messages) {
    if (JSON.stringify(messages) !== JSON.stringify(this.jobMessages)) {
      this.jobMessages = messages;
      this.show();
    }
  }

  // Show the notices and the messages of the jobs that were not closed, each one after the icon
  // of its category. Errors have a button at their right that closes them
  show() {
    const dismissed = MessageLog.loadDismissed();
    const notices = this.notices.map((notice, index) => ({ ...notice, notice: index }));
    const jobs = this.jobMessages.filter(({ id }) => !id || !dismissed.includes(id));
    this.list.replaceChildren(...[...notices, ...jobs].map((message) => {
      const item = document.createElement('li');
      item.dataset.category = message.category;
      item.append(MessageLog.categoryIcon(message.category));
      const text = document.createElement('p');
      text.textContent = message.text;
      item.append(text);
      if (message.category === 'error') {
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'close';
        close.textContent = '×';
        close.setAttribute('aria-label', this.closeLabel);
        close.title = this.closeLabel;
        close.dataset.id = message.id ?? `notice:${message.notice}`;
        item.append(close);
      }
      return item;
    }));
  }

  // Return the icon of a category of messages, an image for screen readers named by the category
  static categoryIcon(category) {
    const [name, label] = CATEGORY_ICONS[category] ?? CATEGORY_ICONS.info;
    const icon = document.createElement('span');
    icon.className = 'icon';
    icon.textContent = name;
    icon.setAttribute('role', 'img');
    icon.setAttribute('aria-label', label);
    icon.title = label;
    return icon;
  }

  // Close the message of the clicked button: a notice is forgotten, and the id of a failure of a
  // job is stored, so it stays closed after a reload
  dismiss({ target }) {
    const { id } = target.closest('button[data-id]')?.dataset ?? {};
    if (!id) {
      return;
    }
    if (id.startsWith('notice:')) {
      this.notices.splice(Number(id.slice('notice:'.length)), 1);
    } else {
      const others = MessageLog.loadDismissed().filter((other) => other !== id);
      MessageLog.saveDismissed([...others, id].slice(-MAX_DISMISSED));
    }
    this.show();
  }

  // Return the ids of the closed failures from localStorage, which anyone may edit or block, so
  // only an array of strings is accepted
  static loadDismissed() {
    try {
      const ids = JSON.parse(window.localStorage.getItem(DISMISSED_KEY) ?? '[]');
      return Array.isArray(ids) ? ids.filter((id) => typeof id === 'string').slice(-MAX_DISMISSED) : [];
    } catch {
      return [];
    }
  }

  static saveDismissed(ids) {
    try {
      window.localStorage.setItem(DISMISSED_KEY, JSON.stringify(ids));
    } catch {
      // Without storage, the closed failures show again after a reload
    }
  }
}

// The student repo: its info, the zips, the origin, and Push
class StudentRepoPanel {
  constructor(section, fieldset) {
    // The section of the repos, which loads their state and sends the requests // RepoSection
    this.section = section;
    // Text with the versions of the repo // HTMLSpanElement
    this.info = fieldset.querySelector('#repo_info');
    // URL of the remote of the user // HTMLInputElement
    this.origin = fieldset.querySelector('#repo_origin');
    // Button that saves the origin // HTMLButtonElement
    this.setOrigin = fieldset.querySelector('#set_origin');
    // Messages of the jobs and of the last action // MessageLog
    this.messages = new MessageLog(fieldset.querySelector('#repo_messages'), section.closeLabel);
    // Origin stored in the repo, to tell whether the field changed // string
    this.savedOrigin = '';
    // Whether the repo has versions, which the zips need // boolean
    this.hasVersions = false;
    // Buttons that start the jobs, by their data-job // HTMLButtonElement[]
    this.jobButtons = [...fieldset.querySelectorAll('[data-job]')];
    // The labels of the buttons when idle, written by the template in the language of the page
    this.jobButtons.forEach((button) => { button.dataset.idle = button.textContent; });
    // Hosts that the server accepts in the origin, for the error message // string[]
    this.originHosts = [];
    this.jobButtons.forEach((button) => button.addEventListener('click', () => this.clickJob(button)));
    this.setOrigin.addEventListener('click', () => this.saveOrigin());
    this.origin.addEventListener('input', () => this.updateSetOrigin());
  }

  // Show the state of the repo. Return whether a job runs
  show(state) {
    this.originHosts = state.originHosts || [];
    this.info.textContent = StudentRepoPanel.describe(state.info);
    this.hasVersions = Boolean(state.info?.commits);
    this.savedOrigin = state.origin || '';
    if (document.activeElement !== this.origin) {
      this.origin.value = this.savedOrigin;
    }
    this.updateSetOrigin();
    const jobs = state.jobs || {};
    this.jobButtons.forEach((button) => this.showJobButton(button, jobs[button.dataset.job]));
    this.messages.showJobs(StudentRepoPanel.jobMessages(jobs));
    return Object.values(jobs).some((job) => job.state === 'running');
  }

  // Show the state of the job in its button: generate (or push), running, or download for a done
  // zip. Its label comes from the template, in the language of the page
  showJobButton(button, job) {
    const running = job?.state === 'running';
    const download = !running && job?.state === 'done' && Boolean(button.dataset.url);
    const state = (running && 'running') || (download && 'download') || 'generate';
    const labels = { running: button.dataset.running, download: button.dataset.download };
    Object.assign(button.dataset, { state });
    button.textContent = labels[state] || button.dataset.idle;
    button.disabled = running || (!download && !this.canStart(button.dataset.job));
  }

  // A button in the download state downloads its zip, which the server sends as an attachment,
  // so the page stays. Otherwise it starts its job
  clickJob(button) {
    if (button.dataset.state === 'download') {
      window.location.assign(button.dataset.url);
    } else {
      this.startJob(button.dataset.job);
    }
  }

  // True if the job of the kind can start: the zips need versions, and the push an origin too
  canStart(kind) {
    return this.hasVersions && (kind !== 'push' || Boolean(this.savedOrigin));
  }

  // Set origin is enabled when the field has a URL different from the stored origin
  updateSetOrigin() {
    const url = this.origin.value.trim();
    this.setOrigin.disabled = !url || url === this.savedOrigin;
  }

  // Return the text of the info of the repo: its versions, problems, and last version
  static describe(info) {
    if (!info) {
      return _('Could not read your student repo.');
    }
    if (!info.commits) {
      return _('No solutions yet: each run of a problem saves a version in this repository.');
    }
    return _('%(commits)s versions of %(problems)s problems, the last one on %(time)s.', {
      commits: info.commits,
      problems: info.problems,
      time: formatTime(info.lastCommit),
    });
  }

  // Return the messages of the jobs that ended: their zips ready to download, or their failures.
  // A failure is identified by its job and start, so a new failure shows again after closing one
  static jobMessages(jobs) {
    const messages = [];
    Object.entries(jobs).forEach(([kind, job]) => {
      if (job.state === 'failed') {
        const reason = REASONS[job.message] || REASONS.failed;
        // The texts are translated already: _() only fills their placeholders
        messages.push({ id: `${kind}:${job.started}`, text: _(FAILURES[kind], { reason }), category: 'error' });
      } else if (job.state === 'done' && READY[kind]) {
        messages.push({ text: _(READY[kind], { time: formatTime(job.expires) }), category: 'info' });
      } else if (job.state === 'done' && PUSHED[job.message]) {
        messages.push({ text: _(PUSHED[job.message], { time: formatTime(job.finished) }), category: 'success' });
      }
    });
    return messages;
  }

  async startJob(kind) {
    this.messages.notify();
    const button = this.jobButtons.find((element) => element.dataset.job === kind);
    button.disabled = true;
    try {
      await this.section.post(`/user/repo/${kind}`, {});
    } catch (error) {
      this.messages.notify({ text: _(FAILURES[kind], { reason: error.text(REASONS) }), category: 'error' });
    }
    await this.section.load();
  }

  async saveOrigin() {
    this.messages.notify();
    this.setOrigin.disabled = true;
    try {
      const { origin } = await this.section.post('/user/repo/origin', { origin: this.origin.value });
      this.origin.value = origin;
      this.messages.notify({ text: _('Origin saved.'), category: 'success' });
    } catch (error) {
      const text = error.code === 'invalid_origin'
        ? _('The origin must be the SSH URL of a repo in %(hosts)s, e.g. git@github.com:user/repo.git', { hosts: this.originHosts.join(', ') })
        : error.text(REASONS);
      this.messages.notify({ text, category: 'error' });
    }
    await this.section.load();
  }
}

// The professor repos: a line per repo with its URL and its Clone or Pull button, and new lines
// that Add repository makes, which become repos when their button is pressed
class ProfessorRepoPanel {
  constructor(section, fieldset) {
    // The section of the repos, which loads their state and sends the requests // RepoSection
    this.section = section;
    // The lines of the repos // HTMLUListElement
    this.list = fieldset.querySelector('#professor_repo_list');
    // Template of the line of a repo, with the texts in the language of the page
    this.template = fieldset.querySelector('#professor_repo_template'); // HTMLTemplateElement
    // Button that adds an empty line for a new repo // HTMLButtonElement
    this.addButton = fieldset.querySelector('#add_repo');
    // Messages of the jobs and of the last action // MessageLog
    this.messages = new MessageLog(fieldset.querySelector('#professor_messages'), section.closeLabel);
    // Lines of the repos that the server has, by id // Map<number, {item, input, button, repo}>
    this.lines = new Map();
    // Ids of the repos whose job was running in the last state // Set<number>
    this.running = new Set();
    // Number given to the next line, for the id of its field // number
    this.nextLine = 0;
    // Hosts that the server accepts in the URLs, for the error message // string[]
    this.hosts = [];
    this.addButton.addEventListener('click', () => this.addLine(null).input.focus());
  }

  // Show the state of the repos. Return whether a job runs. A job that ends while the page shows
  // it reloads the page, so the lists of courses show what it found
  show(repos, hosts) {
    this.hosts = hosts;
    const ended = [...this.running].some((id) => {
      const job = repos.find((repo) => repo.id === id)?.job;
      return job?.state === 'done';
    });
    if (ended) {
      window.location.reload();
      return false;
    }
    repos.forEach((repo) => this.showRepo(repo));
    if (!repos.length && !this.list.children.length) {
      this.addLine(null);
    }
    this.running = new Set(repos.filter((repo) => repo.job.state === 'running').map((repo) => repo.id));
    this.messages.showJobs(repos.flatMap((repo) => ProfessorRepoPanel.jobMessages(repo)));
    return this.running.size > 0;
  }

  // Show a repo in its line, made the first time. The field keeps what the user writes in it
  showRepo(repo) {
    const line = this.lines.get(repo.id) ?? this.addLine(repo.id);
    const edited = line.repo && line.input.value.trim() !== line.repo.url;
    line.repo = repo;
    if (!edited && document.activeElement !== line.input) {
      line.input.value = repo.url;
    }
    const running = repo.job.state === 'running';
    const { dataset } = line.button;
    line.button.textContent = (running && (repo.cloned ? dataset.pulling : dataset.cloning))
      || (repo.cloned ? dataset.pull : dataset.clone);
    line.button.dataset.state = running ? 'running' : 'idle';
    ProfessorRepoPanel.updateButton(line);
  }

  // Add a line from the template, for the repo of the id, or for a new repo if null, and return it
  addLine(id) {
    const item = this.template.content.firstElementChild.cloneNode(true);
    const input = item.querySelector('input');
    const label = item.querySelector('label');
    const button = item.querySelector('button');
    input.id = `professor_repo_${this.nextLine}`;
    this.nextLine += 1;
    label.htmlFor = input.id;
    const line = {
      item, input, button, repo: null, id,
    };
    if (id !== null) {
      this.lines.set(id, line);
    }
    input.addEventListener('input', () => ProfessorRepoPanel.updateButton(line));
    button.addEventListener('click', () => this.pull(line));
    this.list.append(item);
    return line;
  }

  // The button is enabled when the field has a URL, and the job of the repo does not run
  static updateButton(line) {
    line.button.disabled = !line.input.value.trim() || line.button.dataset.state === 'running';
  }

  // Return the messages of the job of the repo: what a clone or pull found, or its failure
  static jobMessages(repo) {
    const { job, folder } = repo;
    if (job.state === 'failed') {
      const reason = PROFESSOR_REASONS[job.message] || PROFESSOR_REASONS.failed;
      const failure = repo.cloned ? PULL_FAILURES.pull : PULL_FAILURES.clone;
      const text = _(failure, { repo: folder, reason });
      return [{ id: `pull_${repo.id}:${job.started}`, text, category: 'error' }];
    }
    if (job.state !== 'done' || !PULLED[job.message]) {
      return [];
    }
    const messages = [{ text: _(PULLED[job.message], { repo: folder, time: formatTime(job.finished), courses: job.courses ?? 0 }), category: 'success' }];
    if (job.skipped?.length) {
      messages.push({ text: _('Skipped courses of %(repo)s, because other repositories have courses with the same names: %(names)s. Rename them in its configuration file.', { repo: folder, names: job.skipped.join(', ') }), category: 'warning' });
    }
    if (job.invalid) {
      messages.push({ text: _('Skipped courses of %(repo)s that are not valid in its configuration file: %(count)s.', { repo: folder, count: job.invalid }), category: 'warning' });
    }
    return messages;
  }

  // Clone or pull the repo of the line, after saving its URL, or add the repo of a new line
  async pull(line) {
    this.messages.notify();
    line.button.disabled = true;
    const url = line.input.value;
    try {
      if (line.id === null) {
        const { error } = await this.section.post('/user/repo/professor', { url });
        // The repo was added, and the next state makes its line, so this one is removed. Its
        // clone may not have started (e.g. the server is busy), and its button tries it again
        line.item.remove();
        if (error) {
          throw new RequestError(error, 503);
        }
      } else {
        await this.section.post(`/user/repo/professor/${line.id}`, { url });
      }
    } catch (error) {
      const text = error.code === 'invalid_url'
        ? _('The repository must be the SSH URL of a repo in %(hosts)s, e.g. git@github.com:user/courses.git', { hosts: this.hosts.join(', ') })
        : error.text(PROFESSOR_REASONS);
      const failure = line.repo?.cloned ? PULL_FAILURES.pull : PULL_FAILURES.clone;
      const repo = line.repo?.folder ?? url.trim();
      this.messages.notify({ text: _(failure, { repo, reason: text }), category: 'error' });
    }
    await this.section.load();
  }
}

// The Repositories section: the SSH key of the user, and the panels of their repos, which it
// shows from the state of the server, asked again while a job runs
class RepoSection {
  constructor(details) {
    // CSRF token of the session, for the POST requests // string
    this.csrfToken = details.dataset.csrfToken;
    // Text of the close buttons of the messages, in the language of the page // string
    this.closeLabel = details.dataset.close;
    // Public SSH key of the user, read only // HTMLInputElement
    this.key = details.querySelector('#repo_key');
    // Icon button that copies the public key to the clipboard // HTMLButtonElement
    this.copyKey = details.querySelector('#copy_key');
    // Accessible name of the copy button when idle, in the language of the page // string
    this.copyLabel = this.copyKey.getAttribute('aria-label');
    // The student repo of the user // StudentRepoPanel
    this.student = new StudentRepoPanel(this, details.querySelector('#student_repo'));
    // The professor repos, only for professors // ProfessorRepoPanel|null
    const professorRepos = details.querySelector('#professor_repos');
    this.professor = professorRepos ? new ProfessorRepoPanel(this, professorRepos) : null;
    // Timer of the next check of the state while a job runs // number
    this.timer = null;
    this.key.addEventListener('focus', () => this.key.select());
    this.copyKey.addEventListener('click', () => this.copyPublicKey());
  }

  // Ask for the state of the repos and show it. While a job runs, ask again after a while
  async load() {
    clearTimeout(this.timer);
    let state;
    try {
      state = await request('/user/repo', this.csrfToken);
    } catch (error) {
      this.student.messages.notify({ text: error.text(REASONS), category: 'error' });
      this.timer = setTimeout(() => this.load(), POLL_INTERVAL * 5);
      return;
    }
    this.key.value = state.publicKey || '';
    this.copyKey.disabled = !this.key.value;
    const studentRunning = this.student.show(state);
    const hosts = state.originHosts || [];
    const professorRunning = Boolean(this.professor?.show(state.professorRepos || [], hosts));
    if (studentRunning || professorRunning) {
      this.timer = setTimeout(() => this.load(), POLL_INTERVAL);
    }
  }

  // Send a POST with the JSON of the body, and return the JSON of the answer
  post(url, body) {
    return request(url, this.csrfToken, body);
  }

  // Copy the public key to the clipboard, and say so in the button for a moment. If the browser
  // refuses (e.g. an http:// address), the key is selected for the user to copy it
  async copyPublicKey() {
    try {
      await navigator.clipboard.writeText(this.key.value);
      this.showCopied(true);
      setTimeout(() => this.showCopied(false), COPIED_TIME);
    } catch {
      this.key.focus();
      this.key.select();
    }
  }

  // Show the check icon and the Copied name in the copy button, or its normal icon and name
  showCopied(copied) {
    const label = copied ? this.copyKey.dataset.done : this.copyLabel;
    this.copyKey.textContent = copied ? 'check' : 'content_copy';
    this.copyKey.setAttribute('aria-label', label);
    this.copyKey.title = label;
  }
}

const details = document.getElementById('repositories');
if (details) {
  new RepoSection(details).load();
}
