import { Request, Response } from 'express';
import config from '../util/config.js';
import { fetchJson } from '../common/common.js';

// TODO: Remove redundancy with site.ts, a backend.d.ts file?
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

/**
 * Communicates with the Code Execution Service (Backend)
 * Currently the backend is Judge0
 */

class BackendController {
  status: Status;

  constructor() {
    this.status = { status: 'offline' };
    this.checkBackendStatus();
    setInterval(() => {
      this.checkBackendStatus();
    }, config.getBackendStatusInterval());
  }

  // Called at some intervals to pull the backend status
  checkBackendStatus() {
    fetchJson(`${config.getBackend()}/workers`)
      .then((json) => {
        this.status.status = 'online';
        this.status.workers = json;
      })
      .catch((error) => console.error(error.message));
  }

  getStatus(req: Request, res: Response) {
    res.json(this.status);
  }
}

// Singleton
const backendController = new BackendController();
export default backendController;
