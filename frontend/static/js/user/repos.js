// Repositories section of the home page: the student repo of the logged user. It shows the info,
// origin, and SSH key of the repo (GET /user/repo), starts its jobs in the background (POST
// /user/repo/<kind>), and asks for their state until they end, so a job that runs keeps its
// button disabled after a reload, or in other browsers. Done zips are downloaded from their links

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

// Texts of the message codes of the server (repo_jobs.py and repos.py)
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

class StudentRepoPanel {
  constructor(fieldset) {
    // The fieldset of the student repo, with the CSRF token of the session // HTMLFieldSetElement
    this.fieldset = fieldset;
    // Text with the versions of the repo // HTMLSpanElement
    this.info = fieldset.querySelector('#repo_info');
    // URL of the remote of the user // HTMLInputElement
    this.origin = fieldset.querySelector('#repo_origin');
    // Public SSH key of the user, read only // HTMLInputElement
    this.key = fieldset.querySelector('#repo_key');
    // Messages of the jobs and of the last action // HTMLUListElement
    this.messages = fieldset.querySelector('#repo_messages');
    // Button that saves the origin // HTMLButtonElement
    this.setOrigin = fieldset.querySelector('#set_origin');
    // Icon button that copies the public key to the clipboard // HTMLButtonElement
    this.copyKey = fieldset.querySelector('#copy_key');
    // Accessible name of the copy button when idle, in the language of the page // string
    this.copyLabel = this.copyKey.getAttribute('aria-label');
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
    // Messages of the last action of the user, shown until the next one // {text, category}[]
    this.notices = [];
    // Timer of the next check of the state while a job runs // number
    this.timer = null;
    // Messages of the jobs in the last state // {id, text, category}[]
    this.jobMessages = [];
    // Ids of the failures of jobs that the user closed // string[]
    this.dismissed = StudentRepoPanel.loadDismissed();
    // Text of the close buttons, in the language of the page // string
    this.closeLabel = this.messages.dataset.close;
    this.messages.addEventListener('click', (event) => this.dismiss(event));
    this.jobButtons.forEach((button) => button.addEventListener('click', () => this.clickJob(button)));
    this.setOrigin.addEventListener('click', () => this.saveOrigin());
    this.origin.addEventListener('input', () => this.updateSetOrigin());
    this.key.addEventListener('focus', () => this.key.select());
    this.copyKey.addEventListener('click', () => this.copyPublicKey());
  }

  // Ask for the state of the repo and show it. While a job runs, ask again after a while
  async load() {
    clearTimeout(this.timer);
    try {
      this.show(await this.request('/user/repo'));
    } catch (error) {
      this.notices = [{ text: error.message, category: 'error' }];
      this.showMessages();
      this.timer = setTimeout(() => this.load(), POLL_INTERVAL * 5);
    }
  }

  show(state) {
    this.originHosts = state.originHosts || [];
    this.info.textContent = StudentRepoPanel.describe(state.info);
    this.hasVersions = Boolean(state.info?.commits);
    this.savedOrigin = state.origin || '';
    if (document.activeElement !== this.origin) {
      this.origin.value = this.savedOrigin;
    }
    this.updateSetOrigin();
    this.key.value = state.publicKey || '';
    this.copyKey.disabled = !this.key.value;
    const jobs = state.jobs || {};
    this.jobButtons.forEach((button) => this.showJobButton(button, jobs[button.dataset.job]));
    this.jobMessages = StudentRepoPanel.jobMessages(jobs);
    this.showMessages();
    if (Object.values(jobs).some((job) => job.state === 'running')) {
      this.timer = setTimeout(() => this.load(), POLL_INTERVAL);
    }
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
      time: StudentRepoPanel.formatTime(info.lastCommit),
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
        messages.push({ text: _(READY[kind], { time: StudentRepoPanel.formatTime(job.expires) }), category: 'info' });
      } else if (job.state === 'done' && PUSHED[job.message]) {
        messages.push({ text: _(PUSHED[job.message], { time: StudentRepoPanel.formatTime(job.finished) }), category: 'success' });
      }
    });
    return messages;
  }

  // Show the notices and the messages of the jobs that were not closed, each one after the icon
  // of its category. Errors have a button at their right that closes them
  showMessages() {
    const notices = this.notices.map((notice, index) => ({ ...notice, notice: index }));
    const jobs = this.jobMessages.filter(({ id }) => !this.dismissed.includes(id));
    this.messages.replaceChildren(...[...notices, ...jobs].map((message) => {
      const item = document.createElement('li');
      item.dataset.category = message.category;
      item.append(StudentRepoPanel.categoryIcon(message.category));
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
      const others = this.dismissed.filter((other) => other !== id);
      this.dismissed = [...others, id].slice(-MAX_DISMISSED);
      StudentRepoPanel.saveDismissed(this.dismissed);
    }
    this.showMessages();
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

  async startJob(kind) {
    this.notices = [];
    const button = this.jobButtons.find((element) => element.dataset.job === kind);
    button.disabled = true;
    try {
      await this.request(`/user/repo/${kind}`, {});
    } catch (error) {
      this.notices = [{ text: _(FAILURES[kind], { reason: error.message }), category: 'error' }];
    }
    await this.load();
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

  async saveOrigin() {
    this.notices = [];
    this.setOrigin.disabled = true;
    try {
      const { origin } = await this.request('/user/repo/origin', { origin: this.origin.value });
      this.origin.value = origin;
      this.notices = [{ text: _('Origin saved.'), category: 'success' }];
    } catch (error) {
      this.notices = [{ text: error.message, category: 'error' }];
    }
    await this.load();
  }

  // Send a request to the server, a POST with the JSON of the body if given, and return the JSON
  // of the answer. Throw an Error with a text for the user if it fails
  async request(url, body = null) {
    const options = body === null ? {} : {
      method: 'POST',
      // The server rejects POST requests without the CSRF token of the session
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.fieldset.dataset.csrfToken },
      body: JSON.stringify(body),
    };
    let response;
    try {
      response = await fetch(url, { ...options, signal: AbortSignal.timeout(REQUEST_TIMEOUT) });
    } catch {
      throw new Error(_('could not connect to the server'));
    }
    const json = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(this.errorText(json.error, response.status));
    }
    return json;
  }

  errorText(code, status) {
    if (code === 'invalid_origin') {
      return _('The origin must be the SSH URL of a repo in %(hosts)s, e.g. git@github.com:user/repo.git', { hosts: this.originHosts.join(', ') });
    }
    return REASONS[code] || _('the server answered %(status)s', { status });
  }

  static formatTime(seconds) {
    return new Date(seconds * 1000).toLocaleString(document.documentElement.lang, { dateStyle: 'medium', timeStyle: 'short' });
  }
}

const fieldset = document.getElementById('student_repo');
if (fieldset) {
  new StudentRepoPanel(fieldset).load();
}
