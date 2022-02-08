// import { ObjectId } from 'mongodb';
import fs from 'fs/promises';
import path from 'path';
import * as vyg from '../common/vygoj.js';

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

  // Problem statement in HTML code
  // TODO: use problem.{en|es|...}.{md|adoc|html} files instead
  statement: string;

  // A list of test cases
  tests: vyg.TestInterface[];

  // Minimum number of secondary threads to solve the problem. If this number
  // is one or more, additional runs will be conducted for each test case
  minThreads: number = 0;

  // There is no limit for the default number of secondary threads
  maxThreads: number = Number.MAX_SAFE_INTEGER;

  // TODO: enabled programming languages, e.g: c,cpp,py,...

  // Load the fields of this object from the given JSON file path
  constructor(relativePath: string, json: vyg.ProblemInterface) {
    this.relativePath = relativePath;
    this.name = json.name;
    this.title = json.title;
    this.statement = json.statement;
    this.tests = json.tests;
    this.minThreads = json.minThreads || 1;
    this.maxThreads = json.maxThreads || Number.MAX_SAFE_INTEGER;
  }

  // Creates a new Problem object from the given relative path problem
  // eg: 'uint64_adder'
  static async load(problemPath: string) {
    // Problems are stored in data/path/vygoj.json
    const absPath = path.join(process.cwd(), 'examples/problems', problemPath, 'vygoj.json');
    // Read the contents of the file
    const content = await fs.readFile(absPath, 'utf-8');
    // Load the fields from the json file
    const json = JSON.parse(content);
    return new Problem(problemPath, json);
  }

  // Calculates the total amount of points from the test cases
  calculateTotalPoints() {
    let total = 0;
    this.tests.forEach((test) => {
      // If test has no a points property, we use 0
      total += test.points ?? 0;
    });
    return total;
  }

  // Returns true if this problem requires the solution to pass extra proofs
  hasProofs() {
    return this.minThreads >= 1;
  }
}
