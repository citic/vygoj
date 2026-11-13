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
    // The version of the backend software, e.g: '1.0.7'
    this.version = '0.0.0';
    // The number of submissions running in the backend in the last update
    this.jobs = 0;
    // workers?: Queue[];
  }
}

/** Common behavior for all site pages */
class Site {
  constructor() {
    // The SVG shown when the backend is offline or user disconnected
    this.backendOfflineElement = document.getElementById('backend_offline');
    // The SVG shown when the backend is online and user connected
    this.backendOnlineElement = document.getElementById('backend_online');
    // True if show backend state instead of app version
    this.wantsBackendDetails = true;
    // A copy of the last status received
    this.backendStatus = new BackendStatus();
    // True if the last check reached an online backend, null before the first check
    this.online = null; // boolean | null
    // The timer of the next status check
    this.statusTimer = 0; // number
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
    // Register event handlers for flash messages' close buttons
    this.setupFlashMessages();
    // No image of the page is shown broken
    document.querySelectorAll('img').forEach((image) => Site.showImageOrFallback(image));
  }

  // An image that does not load, e.g. by a wrong path in vygoj.json, shows its data-fallback image
  // instead, such as the gavel for courses, or hides if it has none or the fallback fails too
  static showImageOrFallback(image) {
    image.decode().catch(() => {
      const { fallback } = image.dataset;
      if (fallback && image.getAttribute('src') !== fallback) {
        image.src = fallback;
        Site.showImageOrFallback(image);
      } else {
        image.hidden = true;
      }
    });
  }

  // Ask the server for the backend status, then schedule the next check
  async checkBackendStatus() {
    // TODO: Replace by a WebSocket. Instead of pulling, server pushes changes
    window.clearTimeout(this.statusTimer);
    try {
      // The timeout ensures a hung connection is reported, instead of waiting forever
      const response = await fetch('/status', { signal: AbortSignal.timeout(STATUS_TIMEOUT) });
      this.updateBackendStatus(await response.json());
    } catch (error) {
      this.setOnline(false, _('Disconnected: %(error)s', { error: error.message }), true);
    }
    const interval = this.online ? STATUS_INTERVAL_ONLINE : STATUS_INTERVAL_OFFLINE;
    this.statusTimer = window.setTimeout(() => this.checkBackendStatus(), interval);
  }

  // Called when the backend status arrived to update the UI
  updateBackendStatus(json) {
    this.backendStatus = json;
    if (this.wantsBackendDetails) {
      this.showBackendDetails();
    }
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

  showBackendDetails() {
    const element = document.getElementById('backend_version');
    element.textContent = this.buildBackendDetails();
  }

  buildBackendDetails() {
    let message = '';
    message += this.backendStatus.version ? (` b${this.backendStatus.version}`) : '';
    message += this.backendStatus.jobs ? (` J=${this.backendStatus.jobs}`) : '';
    return message;
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

window.addEventListener('load', Site.main);
