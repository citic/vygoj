// import { ObjectId } from 'mongodb';
import fs from 'fs/promises';
import path from 'path';

interface ProblemInterface {
  name: string;
  title: string;
}

/**
 * A problem
 */
export default class Problem {
  // _id: ObjectId | undefined;
  // The relative path that identifies the problem
  relativePath: string;

  // An identifier name for the problem, eg "uint64_adder"
  name: string;

  // Title describing the problem, eg "Unsigned 64-bits adder"
  title: string;

  // Load the fields of this object from the given JSON file path
  constructor(relativePath: string, json: ProblemInterface) {
    this.relativePath = relativePath;
    this.name = json.name;
    this.title = json.title;
  }

  // Creates a new Problem object from the given relative path problem
  // eg: 'uint64_adder'
  static async load(problemPath: string) {
    // Problems are stored in data/path/vygoj.json
    const absPath = path.join(process.cwd(), 'data', problemPath, 'vygoj.json');
    // Read the contents of the file
    const content = await fs.readFile(absPath, 'utf-8');
    // Load the fields from the json file
    const json = JSON.parse(content);
    return new Problem(problemPath, json);
  }
}
