// interface Queue {
//   queue: string;
//   size: number;
//   available: number;
//   idle: number;
//   working: number;
//   paused: number;
//   failed: number;
// }

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
    // Update the backend status indicator each minute
    this.checkBackendStatus();
    window.setInterval(() => {
      this.checkBackendStatus();
    }, 60000);
    // Register event handlers for flash messages' close buttons
    this.setupFlashMessages();
  }

  // Called at some intervals to pull the backend status
  checkBackendStatus() {
    // TODO: Replace by a WebSocket. Instead of pulling, server pushes changes
    fetch(`${window.location.protocol}//${window.location.host}/status`)
      .then((httpResponse) => httpResponse.json())
      .then((json) => this.updateBackendStatus(json))
      .catch((error) => this.showBackendOffline(error.message, true));
  }

  // Called when the backend status arrived to update the UI
  updateBackendStatus(json) {
    this.backendStatus = json;
    if (this.wantsBackendDetails) {
      this.showBackendDetails();
    }
    if (json.status === 'online') {
      this.showBackendOnline('Connected');
    } else {
      this.showBackendOffline('Disconnected', false);
    }
  }

  showBackendDetails() {
    const element = document.getElementById('backend_version');
    element.innerText = this.buildBackendDetails();
  }

  buildBackendDetails() {
    let message = '';
    message += this.backendStatus.version ? (` b${this.backendStatus.version}`) : '';
    message += this.backendStatus.jobs ? (` J=${this.backendStatus.jobs}`) : '';
    return message;
  }

  showBackendOffline(message, log) {
    Site.setStatusImage(this.backendOfflineElement, 'visible_inline', message, log);
    Site.setStatusImage(this.backendOnlineElement, 'hidden', message, log);
  }

  showBackendOnline(message) {
    Site.setStatusImage(this.backendOfflineElement, 'hidden', message, false);
    Site.setStatusImage(this.backendOnlineElement, 'visible_inline', message, false);
  }

  static setStatusImage(element, status, message, log) {
    if (log) {
      console.error(message);
    }
    element.className = status;
    element.title = message;
  }

  // eslint-disable-next-line class-methods-use-this
  setupFlashMessages() {
    // Find all close buttons
    const closeButtons = document.querySelectorAll('.flash_message__close');
    // Add click event to each button
    closeButtons.forEach((button) => {
      button.addEventListener('click', (/* element */) => {
        const flashMessage = button.closest('.flash_message');
        if (flashMessage) {
          flashMessage.remove();
          // If no more flash messages, remove the container
          const flashContainer = document.querySelector('.flash_messages');
          if (flashContainer && flashContainer.children.length === 0) {
            flashContainer.remove();
          }
        }
      });
    });
  }
}

window.addEventListener('load', Site.main);
