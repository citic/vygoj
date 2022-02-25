import fs from 'fs';
import readline from 'readline';

// Index of fields in TSV
const fldDate = 0;
const fldTime = fldDate + 1;
const fldType = fldTime + 1;
const fldCategory = fldType + 1;
const fldIP = fldCategory + 1;
const fldMethod = fldIP + 1;
const fldURI = fldMethod + 1;
const fldUser = fldURI + 1;
const fldBody = fldUser + 1;
const fldCount = fldBody + 1;

function serverDecode(data) {
  // See https://stackoverflow.com/a/69992416
  return Buffer.from(data, 'base64').toString('utf8');
}

export default class Decoder {
  constructor() {
    this.inputFilename = '';
    // Stores unknown user events mapping IP
    this.ipEvents = new Map();
    // Known logged-in users and their advance percent and runs for each problem
    // 'user1' => { problem1: [100, 34], problem2: [95.8, 18] }
    this.users = new Map();
  }

  decode(filename) {
    this.inputFilename = filename;
    // Read one line at the time instead of loading entire file to memory
    const reader = readline.createInterface({
      input: fs.createReadStream(this.inputFilename),
      output: null, // do not send lines to process.stdout
      console: false,
    });
    this.lineNumber = 0;
    reader.on('line', (line) => {
      this.decodeLine(line);
    });
    reader.on('close', () => {
      console.log(`${this.lineNumber} lines decoded`);
      console.log(this.users);
    });
  }

  decodeLine(line) {
    this.lineNumber += 1;
    // Silently ignore blank lines
    if (line.length > 0) {
      const fields = line.split('\t');
      if (fields.length === fldCount) {
        this.decodeFields(fields);
      } else {
        console.error(`${this.lineNumber}: found ${fields.length} fields, expected ${fldCount}`);
      }
    }
  }

  decodeFields(fields) {
    const user = fields[fldUser];
    const ip = fields[fldIP];
    // If user is known
    if (user) {
      // If it is a new user
      if (!this.users.has(user)) {
        // Create a user folder
        this.createUser(user);
        // Associate pending events by IP
        this.associateEvents(user, fields[fldIP]);
      }
      // Store this event to user log and process run files
      this.decodeUserEvent(user, fields);
      // Add event to his/her log
    } else if (this.ipEvents.has(ip)) {
      // Store event to its IP
      // If there is an entry for this IP
      this.ipEvents.get(ip).push(fields);
    } else {
      this.ipEvents.set(ip, [fields]);
    }
  }

  createUser(user) {
    // Create a directory for this user
    const dir = `./${user}`;
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir);
    }
    // Add this user to the known list
    this.users.set(user, { });
  }

  associateEvents(user, ip) {
    // Process each event to the known user
    if (this.ipEvents.has(ip)) {
      const events = this.ipEvents.get(ip);
      for (let index = 0; index < events.length; index += 1) {
        this.decodeUserEvent(user, events[index]);
      }
      // Clear the events for this ip
      this.ipEvents.delete(ip);
    }
  }

  decodeUserEvent(user, fields) {
    // Append this event to the user's log
    const body = fields[fldBody];
    const event = `${fields[fldDate]}\t${fields[fldTime]}\t${fields[fldMethod]}\t${fields[fldURI]}\t${body}\n`;
    const log = `./${user}/log.tsv`;
    fs.appendFileSync(log, event, 'utf-8');

    // If this event is a solution Run
    if (body.startsWith('{"action":"run"')) {
      this.decodeRun(user, fields);
    }
  }

  decodeRun(user, fields) {
    const problem = fields[fldURI].substring('/problem/'.length);
    const dateTime = Decoder.extractDateTime(fields[fldDate], fields[fldTime]);
    const body = JSON.parse(fields[fldBody]);
    // TODO: Support multiple files
    // TODO: Map source code extension from body.language
    const extension = 'c';
    const source = serverDecode(body.code);

    // Create a directory for the problem if it does not exist
    const dir = `./${user}/${problem}`;
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir);
    }

    // Write source code to a file using the date
    const filename = `${dir}/${dateTime}.${extension}`;
    fs.writeFileSync(filename, source, 'utf-8');

    // Store statistics
    let stats = this.users.get(user)[problem];
    if (stats) {
      // Increase run count
      stats[1] += 1;
    } else {
      // First run of this problem
      stats = [0, 1];
    }
  }

  static extractDateTime(date, time) {
    const text = `${date}\t${time}`; // 18/2/2022 10:20:02
    const re = /(\d+)\/(\d+)\/(\d+)\t(\d+):(\d+):(\d+)/;
    const match = text.match(re);
    const dd = match[1].padStart(2, '0');
    const mm = match[2].padStart(2, '0');
    const yy = match[3].padStart(4, '0');
    const HH = match[4].padStart(2, '0');
    const MM = match[5].padStart(2, '0');
    const SS = match[6].padStart(2, '0');
    return `${yy}${mm}${dd}_${HH}${MM}${SS}`;
  }
}
