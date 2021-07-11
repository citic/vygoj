import fs from 'fs';
import path from 'path';
import { Request } from 'express';

import common from '../common/common.js';

// TODO: separate between Log model class and LogController (singleton)
class Log {
  filename: string;

  constructor(filename = '') {
    this.filename = filename;
  }

  append(message: string, type = 'info', category = '') {
    const date = new Date();
    const line = `${date}\t${type}\t${category}\t${message}\n`;
    fs.appendFile(this.filename, line, (error) => {
      if (error) {
        console.error(`${common.appName} log error: `, error);
      }
    });
  }

  appendHttpRequest(req: Request) {
    const message = `${req.method} ${req.url}`;
    console.log(message);
    this.append(message, 'info', 'req');
  }
}

// Singleton log instance
const log = new Log(path.join(process.cwd(), 'data', 'vygot.tsv'));
export default log;
