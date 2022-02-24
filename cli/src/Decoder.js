import fs from 'fs';

export default class Decoder {
  constructor() {
    this.inputFilename = '';
  }

  decode(filename) {
    this.inputFilename = filename;
    fs.readFileSync(filename);
    console.log(`Decoding ${this.inputFilename}`);
  }
}
