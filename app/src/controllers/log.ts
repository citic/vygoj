import fs from 'fs';
import path from 'path';
import { Request } from 'express';

import common from '../common/common.js';

// TODO: separate between Log model class and LogController (singleton)
class Log {
  constructor(public filename = '') {
  }

  append(message: string, type = 'info', category = '') {
    const date = new Date().toLocaleString('es-CR').replace(' ', '\t');
    const line = `${date}\t${type}\t${category}\t${message}\n`;
    fs.appendFile(this.filename, line, (error) => {
      if (error) {
        console.error(`${common.appName} log error: `, error);
      }
    });
  }

  appendHttpRequest(req: Request) {
    console.log(`${req.method}\t${req.url}`);
    const user = req.session.user?.email ?? '';
    const body = req.body ? JSON.stringify(req.body) : '';
    const message = `${req.ip}\t${req.method}\t${req.url}\t${user}\t${body}`;
    this.append(message, 'info', 'req');
  }
}

// Singleton log instance
const log = new Log(path.join(process.cwd(), 'data', 'vygot.tsv'));
export default log;
