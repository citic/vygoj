interface Status {
  status: string;
  workers: {
    [key: string]: number;
  };
}

/** Common behavior for all site pages */
class Site {
  backendStatusElement: HTMLImageElement;

  constructor() {
    this.backendStatusElement = document.getElementById('backend_status') as HTMLImageElement;
    if (!this.backendStatusElement) {
      throw new Error('Could not find backend_status element');
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

  showBackendOnline(message: string) {
    this.backendStatusElement.src = '/icon/cloud_online.svg';
    this.backendStatusElement.alt = message;
  }

  showBackendOffline(error: string, log: boolean) {
    if (log) {
      console.error(error);
    }
    this.backendStatusElement.src = '/icon/cloud_offline.svg';
    this.backendStatusElement.alt = error;
  }
}

window.addEventListener('load', Site.main);
