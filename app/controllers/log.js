import fs from 'fs';
import path from 'path';

import common from '../common/common.js';

// TODO: separate between Log model class and LogController (singleton)
class Log {
  constructor(filename = '') {
    this.filename = filename;
  }

  append(message, type = 'info', category = '') {
    const date = new Date();
    const line = `${date}\t${type}\t${category}\t${message}\n`;
    fs.appendFile(this.filename, line, (error) => {
      if (error) {
        console.error(`${common.appName} log error: `, error);
      }
    });
  }

  appendHttpRequest(req) {
    const message = `${req.method} ${req.url}`;
    console.log(message);
    this.append(message, 'info', 'req');
  }
}

// Singleton log instance
const log = new Log(path.join(process.cwd(), 'vygot.tsv'));
export default log;
