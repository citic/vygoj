// interface Queue {
//   queue: string;
//   size: number;
//   available: number;
//   idle: number;
//   working: number;
//   paused: number;
//   failed: number;
// }

import _ from './i18n.js';

// Milliseconds between status checks while connected, and while disconnected. Disconnected pages
// check more often, so they notice soon that the connection is back
const STATUS_INTERVAL_ONLINE = 60000;
const STATUS_INTERVAL_OFFLINE = 10000;
// Milliseconds to wait for the status before considering the server unreachable
const STATUS_TIMEOUT = 10000;
// Event dispatched on window when the connection to the judge is lost or restored. Its detail is
// { online: boolean }. Pages dispatch CHECK_EVENT to ask for a check now, e.g. after a failed run
export const STATUS_EVENT = 'vyg:backendstatus';
export const CHECK_EVENT = 'vyg:checkbackend';

class BackendStatus {
  constructor() {
    // The status of the backend: 'online', 'offline', 'maintenance'
    this.status = 'offline';
    // The version of the backend software, e.g. '0.1.0', and its commit, e.g. 'ce271b1 2026-11-23'
    this.version = '';
    this.commit = '';
    // The number of submissions running in the backend in the last update
    this.jobs = 0;
    // workers?: Queue[];
  }
}

// Show the version and the commit of a process in its row of the versions table of the footer, and
// its state: the given text if it answered its status, or that it is offline. The texts come from
// other servers, so they are written as text, never as HTML
function showVersion(row, status, state = '') {
  const online = status?.status === 'online';
  row.querySelector('.version').textContent = online ? String(status.version ?? '') : '';
  row.querySelector('.commit').textContent = online ? String(status.commit ?? '') : '';
  row.querySelector('.state').textContent = online ? state : _('offline');
}

// Milliseconds after the last key before a search asks for its results, and to wait for them
const SEARCH_DELAY = 300;
const SEARCH_TIMEOUT = 10000;

// An image that does not load, e.g. by a wrong path in vygoj.json, shows its data-fallback image
// instead, such as the gavel for courses, or hides if it has none or the fallback fails too
function showImageOrFallback(image) {
  image.decode().catch(() => {
    const { fallback } = image.dataset;
    if (fallback && image.getAttribute('src') !== fallback) {
      image.src = fallback;
      showImageOrFallback(image);
    } else {
      image.hidden = true;
    }
  });
}

/**
 * Search of a table of data split in pages in the server while the user types (list_search of
 * macros.html, data_table.py). It asks the server for the page of the search, the same one that the
 * form opens without scripts, and puts the contents of the elements of the results (the ids of the
 * aria-controls of the form) of that page in the ones of this page, so the field keeps its focus
 * and what the user types. The URL of the page becomes the one of the search, so a reload keeps
 * it. If the session ended (a redirect), the browser opens the search, which goes to the login. If
 * the request fails or takes too long, the field says so, and the next key tries again: opening
 * the search would only ask a busy server for it again
 */
class ListSearch {
  constructor(form) {
    // The GET form of the search, with the ids of the results in its aria-controls
    this.form = form; // HTMLFormElement
    // The field of the search
    this.input = form.querySelector('input[type="search"]'); // HTMLInputElement
    // The X that clears the search, shown while the field has text
    this.clearLink = form.querySelector('.clear'); // HTMLAnchorElement
    // The timer of the next search, while the user types
    this.timer = 0; // number
    // Cancels the request of the last search when another one starts
    this.controller = null; // AbortController | null
  }

  setup() {
    // The search, and the rows per page of a table
    this.form.addEventListener('input', () => {
      this.clearLink.hidden = this.input.value === '';
      window.clearTimeout(this.timer);
      this.timer = window.setTimeout(() => this.search(), SEARCH_DELAY);
    });
    this.form.addEventListener('submit', (event) => {
      event.preventDefault();
      this.search();
    });
    // The error of a failed search is cleared by any key, before Enter sends the form: an invalid
    // field would stop it
    this.input.addEventListener('keydown', () => this.input.setCustomValidity(''));
    // A number of rows out of its range, or with decimals, becomes the nearest valid one when the
    // user leaves the field, as the server takes it, and the rows follow it
    this.form.addEventListener('change', ({ target }) => {
      if (target.type === 'number' && target.value !== '' && !target.checkValidity()) {
        const rounded = Math.round(Number(target.value));
        target.value = Math.min(Math.max(rounded, Number(target.min)), Number(target.max));
        this.search();
      }
    });
    this.clearLink.addEventListener('click', (event) => {
      event.preventDefault();
      this.input.value = '';
      this.clearLink.hidden = true;
      this.input.focus();
      this.search();
    });
  }

  // The URL of the search: the fields of the form without the empty ones, as the links of the page
  url() {
    const params = new URLSearchParams(new FormData(this.form));
    const filled = new URLSearchParams([...params].filter(([, value]) => value));
    return filled.size ? `${this.form.action}?${filled}` : this.form.action;
  }

  // Ask for the page of the search and show its results
  async search() {
    window.clearTimeout(this.timer);
    this.input.setCustomValidity('');
    this.controller?.abort();
    this.controller = new AbortController();
    const url = this.url();
    try {
      const signal = AbortSignal.any([this.controller.signal, AbortSignal.timeout(SEARCH_TIMEOUT)]);
      const response = await fetch(url, { signal });
      if (response.redirected) {
        window.location.assign(url);
        return;
      }
      if (!response.ok) {
        throw new Error(response.statusText);
      }
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      this.form.getAttribute('aria-controls').split(' ').forEach((id) => {
        const element = document.getElementById(id);
        const fresh = page.getElementById(id);
        if (element && fresh) {
          element.hidden = fresh.hidden;
          element.replaceChildren(...fresh.childNodes);
          element.querySelectorAll('img').forEach(showImageOrFallback);
        }
      });
      window.history.replaceState(null, '', url);
    } catch (error) {
      // A newer search cancelled this one, which is not a failure (a timeout is a TimeoutError)
      if (error.name !== 'AbortError') {
        console.error(`search failed: ${error.message}`);
        this.input.setCustomValidity(_('The search failed. Try again later.'));
        this.input.reportValidity();
      }
    }
  }
}

/** Common behavior for all site pages */
class Site {
  constructor() {
    // The SVG shown when the backend is offline or user disconnected
    this.backendOfflineElement = document.getElementById('backend_offline');
    // The SVG shown when the backend is online and user connected
    this.backendOnlineElement = document.getElementById('backend_online');
    // A copy of the last status received
    this.backendStatus = new BackendStatus();
    // True if the last check reached an online backend, null before the first check
    this.online = null; // boolean | null
    // The timer of the next status check
    this.statusTimer = 0; // number
    // Number of the last status check, which is the only one that shows its answer
    this.statusCheck = 0; // number
    // Error checking
    if (!this.backendOfflineElement || !this.backendOnlineElement) {
      throw new Error('Could not find backend status elements');
    }
  }

  static main() {
    const site = new Site();
    site.setup();
  }

  setup() {
    // Update the backend status indicator now and then periodically
    this.checkBackendStatus();
    // The browser knows at once when the network goes down or up
    window.addEventListener('offline', () => this.setOnline(false, _('No network connection'), false));
    window.addEventListener('online', () => this.checkBackendStatus());
    window.addEventListener(CHECK_EVENT, () => this.checkBackendStatus());
    // The icon of the connection opens the versions of the processes
    this.setupVersions();
    // Register event handlers for flash messages' close buttons
    this.setupFlashMessages();
    // No image of the page is shown broken
    document.querySelectorAll('img').forEach(showImageOrFallback);
    // Tables of data split in pages are searched in the server while the user types. A search
    // without action filters the rows of the page instead (filter.js)
    document.querySelectorAll('.list_search[action]').forEach((form) => new ListSearch(form).setup());
  }

  // Ask the server for the backend status, then schedule the next check
  async checkBackendStatus() {
    // TODO: Replace by a WebSocket. Instead of pulling, server pushes changes
    window.clearTimeout(this.statusTimer);
    this.statusCheck += 1;
    const check = this.statusCheck;
    let json = null;
    let failure = null;
    try {
      // The timeout ensures a hung connection is reported, instead of waiting forever
      const response = await fetch('/status', { signal: AbortSignal.timeout(STATUS_TIMEOUT) });
      json = await response.json();
    } catch (error) {
      failure = error;
    }
    // Checks may overlap, e.g. a failed run asks for one while another waits. Only the last one
    // shows its answer and schedules the next check, so an older answer cannot replace it
    if (check !== this.statusCheck) {
      return;
    }
    if (failure) {
      this.backendStatus = new BackendStatus();
      this.showBackendVersion();
      this.setOnline(false, _('Disconnected: %(error)s', { error: failure.message }), true);
    } else {
      this.updateBackendStatus(json);
    }
    const interval = this.online ? STATUS_INTERVAL_ONLINE : STATUS_INTERVAL_OFFLINE;
    this.statusTimer = window.setTimeout(() => this.checkBackendStatus(), interval);
  }

  // Called when the backend status arrived to update the UI
  updateBackendStatus(json) {
    this.backendStatus = json;
    this.showBackendVersion();
    if (json?.status === 'online') {
      this.setOnline(true, _('Connected'), false);
    } else {
      this.setOnline(false, _('Disconnected'), false);
    }
  }

  // Show the connection state, keep it in the data-status attribute of #backend_status for pages
  // that load later, and tell the pages when it changes
  setOnline(online, message, log) {
    if (online) {
      this.showBackendOnline(message);
    } else {
      this.showBackendOffline(message, log);
    }
    if (online !== this.online) {
      this.online = online;
      const statusElement = document.getElementById('backend_status');
      if (statusElement) {
        statusElement.dataset.status = online ? 'online' : 'offline';
      }
      window.dispatchEvent(new CustomEvent(STATUS_EVENT, { detail: { online } }));
    }
  }

  // The versions table of the footer has the rows of the frontend, written by the server, of the
  // backend, from its last status, and of the language server of the user, if any, which is asked
  // for its status each time that the table opens
  setupVersions() {
    const versions = document.getElementById('versions');
    versions.addEventListener('toggle', (event) => {
      if (event.newState === 'open' && versions.dataset.langServer) {
        this.checkLangServerStatus(versions.dataset.langServer);
      }
    });
  }

  // Show the version of the backend of the last status, and the submissions running in it
  showBackendVersion() {
    const { jobs } = this.backendStatus;
    const state = Number.isInteger(jobs) && jobs > 0 ? _('%(jobs)s running', { jobs }) : '';
    showVersion(document.getElementById('backend_version'), this.backendStatus, state);
  }

  // eslint-disable-next-line class-methods-use-this
  async checkLangServerStatus(url) {
    const row = document.getElementById('langserv_version');
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(STATUS_TIMEOUT) });
      showVersion(row, await response.json());
    } catch {
      showVersion(row, null);
    }
  }

  showBackendOffline(message, log) {
    Site.setStatusImage(this.backendOfflineElement, true, message, log);
    Site.setStatusImage(this.backendOnlineElement, false, message, log);
  }

  showBackendOnline(message) {
    Site.setStatusImage(this.backendOfflineElement, false, message, false);
    Site.setStatusImage(this.backendOnlineElement, true, message, false);
  }

  static setStatusImage(element, visible, message, log) {
    if (log) {
      console.error(message);
    }
    element.hidden = !visible;
    element.title = message;
  }

  // eslint-disable-next-line class-methods-use-this
  setupFlashMessages() {
    // The close button of each message removes it, and the list after its last message
    document.querySelectorAll('.flash_messages button').forEach((button) => {
      button.addEventListener('click', () => {
        const list = button.closest('.flash_messages');
        button.closest('li').remove();
        if (list.children.length === 0) {
          list.remove();
        }
      });
    });
  }
}

// Not on the load event: the page may load while i18n.js waits for the translations, and then this
// listener would never run. base.html puts this module at the end of the body, after the elements
Site.main();
