export interface TestInterface {
  input: string;
  output: string;
  points: number;
}

export interface ProblemInterface {
  name: string;
  title: string;
  statement: string;
  tests: TestInterface[];
}
