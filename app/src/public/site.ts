// TODO: Remove redundancy with backend.ts, a backend.d.ts file?
interface Queue {
  queue: string;
  size: number;
  available: number;
  idle: number;
  working: number;
  paused: number;
  failed: number;
}

interface Status {
  status: string;
  workers?: Queue[];
}

/** Common behavior for all site pages */
class Site {
  // The SVG shown when the backend is offline or user disconnected
  backendOfflineElement: HTMLSpanElement;
  // The SVG shown when the backend is online and user connected
  backendOnlineElement: HTMLSpanElement;
  // True if show backend state instead of app version
  wantsBackendDetails: boolean = true;
  // A copy of the last status received
  status: Status = { status: 'offline' };

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
    }, 60000);
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
  updateBackendStatus(json: Status) {
    this.status = json;
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
    const element = document.getElementById('software_version') as HTMLSpanElement;
    element.innerText = this.buildBackendDetails();
  }

  buildBackendDetails() {
    let message = '';
    if (this.status.workers) {
      this.status.workers.forEach((queue: Queue) => {
        message += `${queue.queue} p${queue.size} f${queue.failed}`;
        message += ` a${queue.available} w${queue.working} p${queue.paused} i${queue.idle}`;
      });
    } else {
      message = this.status.status;
    }
    return message;
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
