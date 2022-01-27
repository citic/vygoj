import { Request, Response } from 'express';
import * as nodeFetch from 'node-fetch';
import fetch from 'node-fetch';
import errorController from './errorController.js';
import config from '../util/config.js';
import Problem from '../models/problem.js';
import * as vyg from '../common/vygoj.js';

const languageDefaults: vyg.LanguageDefaults = {
  C: {
    id: 50,
    compiler_options: '-g -Wall -Wextra -std=gnu17 -pthread',
  },
  'C++': {
    id: 54,
    compiler_options: '-g -Wall -Wextra -std=gnu++17 -pthread',
  },
};

/**
 * Controls problems
 *
 * A problem page contains:
 * - a problem statement
 * - a text editor to provide a solution
 * - a combo box for choosing between the enabled programming languages
 * - a Submit/Run button
 * - a test case list
 * - a test case detail control
 *
 * Users read the problem statement, write a code solution in the selected
 * programming language, and submit the solution. An AJAX code asks the
 * backend to run the solution. The answers are sent to the client that shows
 * them to the user.
 *
 * The answer contains compiler/interpreter diagnostics. If the code produced
 * no errors a report of each passed/failed test case is provided. The AJAX
 * code shows these results to the user who can modify the code and submit
 * a new solution. This process repeat until user solves the problem or leaves
 * the page.
 */
class ProblemController {
  // Get the contents page for a course
  // eslint-disable-next-line class-methods-use-this
  async getProblem(req: Request, res: Response) {
    try {
      const problemPath = req.params.path as string;
      const problem = await Problem.load(problemPath);
      res.render('problems/problem', {
        stylesheet: 'problems',
        title: `${problem.title} - Vygoj`,
        user: req.session.user,
        breadcumbs: [
          { href: `/problem/${problem.relativePath}`, text: problem.name },
        ],
        problem,
        scripts: [
          '<script src="https://pagecdn.io/lib/ace/1.4.13/ace.js" crossorigin="anonymous" integrity="sha256-bS3VAQePcKYmsvI+8BdG2QJAVb9FbiZLgM5vK2/+TcM=" async="async"></script>',
          '<script src="/js/problem/problem.js" type="module" async="async"></script>',
        ],
      });
    } catch (error) {
      console.error(error);
      errorController.getNotFound(req, res);
    }
  }

  // Client JavaScript asked for an action: fetch a problem, run user solution,
  // save user code, ... All communication is made with JSON objects
  async postProblem(req: Request, res: Response) {
    try {
      const problemPath = req.params.path as string;
      console.log(req.body);
      const message = req.body as vyg.Message;
      switch (message.action) {
        case 'fetch_problem': await this.fetchProblem(problemPath, res); break;
        case 'run': await this.runUserCode(problemPath, res, message); break;
        default: res.json({ error: 'invalid action' }); break;
      }
    } catch (error) {
      res.json({ error: 'invalid action' });
    }
  }

  // eslint-disable-next-line class-methods-use-this
  async fetchProblem(problemPath: string, res: Response) {
    const problem = await Problem.load(problemPath);
    res.json(problem);
  }

  // eslint-disable-next-line class-methods-use-this
  async runUserCode(problemPath: string, res: Response, message: vyg.Message) {
    const problem = await Problem.load(problemPath);
    const result = await this.runTestCases(problem, message);
    setTimeout(() => { res.json(result); }, 3000);
    // res.json(result);
  }

  // eslint-disable-next-line class-methods-use-this
  async runTestCases(problem: Problem, message:vyg. Message) {
    try {
      // The user program is executed once for each test case
      // Create an array of promises of results, one for each test case
      const language = (message.language || 'C') as keyof vyg.LanguageDefaults;
      // TODO: store executions in array of promises and run them in parallel Promise.all()
      //- const executions: Promise<nodeFetch.Response>[] = [];
      const results = [];
      for (let index = 0; index < problem.tests.length; ++index) {
        const test: vyg.TestInterface = problem.tests[index];
        // TODO: change wait to false, see https://ce.judge0.com/#submissions
        const uri = `${config.getBackend()}/submissions?base64_encoded=false&wait=true`;
        // The JSON object to be sent in the body of the POST message
        const submission: vyg.Judge0Submission = {
          source_code: message.code || '',
          language_id: languageDefaults[language].id,
          compiler_options: languageDefaults[language].compiler_options,
          stdin: test.input,
        };
        // The options of the fetch(uri, options) message
        const options: nodeFetch.RequestInit = {
          method: 'post',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(submission),
        };
        //- executions.push(fetch(uri, options));
        // executions.push( { uri, options } );
        // TODO: log the run in database
        console.log('uri::', uri, 'SUBMISSION::', submission);
        // Execute the code in the backend
        const response = await fetch(uri, options);
        const result = await response.json();
        // TODO: log the result in database
        console.log(result);
        results.push(result);
      }
      // const results = await Promise.all(executions)
      //   .then(async (responses) => Promise.all(responses.map(async (body) => {
      //     await body.json();
      //   })));
      /*
      const result: vyg.RunResultInterface = {
        totalDuration: 0.420019,
        threadCount: 1,
        outputs: [
          { passed: false, output: 'Hello\n' },
          { passed: true, output: '0' },
          { passed: false, output: 'world!\n' },
        ],
      };
      */
      return results;
    } catch (error) {
      console.error(error);
      return error;
    }
  }
} // class

// Export the singleton controller
const problemController = new ProblemController();
export default problemController;
