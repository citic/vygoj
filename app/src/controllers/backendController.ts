import { Request, Response } from 'express';
import config from '../util/config.js';
import { fetchJson } from '../common/common.js';

// TODO: Remove redundancy with site.ts, a backend.d.ts file?
interface Status {
  status: string;
  workers: {
    [key: string]: number;
  };
}

/**
 * Communicates with the Code Execution Service (Backend)
 * Currently the backend is Judge0
 */

class BackendController {
  status: Status;

  constructor() {
    this.status = { status: 'offline', workers: { } };
    this.checkBackendStatus();
    setInterval(() => {
      this.checkBackendStatus();
    }, config.getBackendStatusInterval());
  }

  // Called at some intervals to pull the backend status
  checkBackendStatus() {
    fetchJson(config.getBackend())
      .then((json) => { this.status.workers = json; })
      .catch((error) => console.error(error.message));
  }

  getStatus(req: Request, res: Response) {
    if (Math.random() < 0.75) {
      res.json(this.status);
    } else {
      res.json(this.status);
    }
  }
}

// Singleton
const backendController = new BackendController();
export default backendController;
