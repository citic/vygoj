export interface TestInterface {
  input: string;
  output: string;
  points: number;
  hidden: boolean = false; // TODO: clear it from server side
}

export interface ProblemInterface {
  name: string;
  title: string;
  statement: string;
  tests: TestInterface[];
  languages: string[]; // C, C++, Java, Python...
  initialCodeFor?: Object; // Map<string, string> but not supported by JSON
}
