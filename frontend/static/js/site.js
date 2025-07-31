"use strict";
// TODO: Remove redundancy with backend.ts, a backend.d.ts file?
// interface Queue {
//   queue: string;
//   size: number;
//   available: number;
//   idle: number;
//   working: number;
//   paused: number;
//   failed: number;
// }
/** Common behavior for all site pages */
class Site {
  // The SVG shown when the backend is offline or user disconnected
  backendOfflineElement;
  // The SVG shown when the backend is online and user connected
  backendOnlineElement;
  // True if show backend state instead of app version
  wantsBackendDetails = true;
  // A copy of the last status received
  status = { status: 'offline' };
  constructor() {
    this.backendOfflineElement = document.getElementById('backend_offline');
    this.backendOnlineElement = document.getElementById('backend_online');
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
    fetch(`http://${window.location.host}/status`)
      .then((httpResponse) => httpResponse.json())
      .then((json) => this.updateBackendStatus(json))
      .catch((error) => this.showBackendOffline(error.message, true));
  }
  // Called when the backend status arrived to update the UI
  updateBackendStatus(json) {
    this.status = json;
    if (this.wantsBackendDetails) {
      this.showBackendDetails();
    }
    if (json.status === 'online') {
      this.showBackendOnline('Connected');
    }
    else {
      this.showBackendOffline('Disconnected', false);
    }
  }
  showBackendDetails() {
    const element = document.getElementById('software_version');
    element.innerText = this.buildBackendDetails();
  }
  buildBackendDetails() {
    let message = 'VygOJ';
    message += this.status.version ? (' v' + this.status.version) : '';
    message += this.status.jobs ? (' J=' + this.status.jobs) : '';
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
  setupFlashMessages() {
    // Find all close buttons
    const closeButtons = document.querySelectorAll('.flash_message__close');
    // Add click event to each button
    closeButtons.forEach(button => {
      button.addEventListener('click', function (element) {
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
