// TODO: Remove redundancy with backend.ts, a backend.d.ts file?
interface Status {
  status: string;
  workers: {
    [key: string]: number;
  };
}

/** Common behavior for all site pages */
class Site {
  backendOfflineElement: HTMLSpanElement;

  backendOnlineElement: HTMLSpanElement;

  constructor() {
    this.backendOfflineElement = document.getElementById('backend_offline') as HTMLSpanElement;
    this.backendOnlineElement = document.getElementById('backend_online') as HTMLSpanElement;
    if (!this.backendOfflineElement || !this.backendOnlineElement) {
      throw new Error('Could not find backend status elements');
    }
  }

  static main() {
    const site = new Site();
    site.setup();
  }

  setup() {
    this.checkBackendStatus();
    window.setInterval(() => {
      this.checkBackendStatus();
    }, 10000);
  }

  // Called at some intervals to pull the backend status
  checkBackendStatus() {
    // TODO: Replace by a WebSocket. Instead of pulling server pushes changes
    fetch(`http://${window.location.host}/status`)
      .then((httpResponse) => httpResponse.json())
      .then((json) => this.updateBackendStatus(json))
      .catch((error) => this.showBackendOffline(error.message, true));
  }

  // Called when the backend status arrived to update the UI
  updateBackendStatus(json : Status) {
    let message = '';
    if (json.workers) {
      Object.keys(json.workers).forEach((key: string) => {
        message += `${key}: ${json.workers[key]}\n`;
      });
    }
    if (json.status === 'online') {
      this.showBackendOnline(message);
    } else {
      this.showBackendOffline(message, false);
    }
  }

  showBackendOffline(message: string, log: boolean) {
    Site.setStatusImage(this.backendOfflineElement, 'visible_inline', message, log);
    Site.setStatusImage(this.backendOnlineElement, 'hidden', message, log);
  }

  showBackendOnline(message: string) {
    Site.setStatusImage(this.backendOfflineElement, 'hidden', message, false);
    Site.setStatusImage(this.backendOnlineElement, 'visible_inline', message, false);
  }

  static setStatusImage(element: HTMLSpanElement, status: string, message: string, log: boolean) {
    if (log) {
      console.error(message);
    }
    element.className = status;
    element.title = message;
  }
}

window.addEventListener('load', Site.main);
