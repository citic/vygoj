import { Request, Response } from 'express';
import Execution from '../models/execution.js';
import errorController from './errorController.js';
import Problem from '../models/problem.js';
import * as vyg from '../common/vygoj.js';

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
    // setTimeout(() => { res.json(result); }, 3000);
    res.json(result);
  }

  // eslint-disable-next-line class-methods-use-this
  async runTestCases(problem: Problem, solution:vyg.Message) {
    try {
      // Create an array of results, one for each test case
      const results = [];
      // The user program is executed once for each test case
      for (let index = 0; index < problem.tests.length; ++index) {
        // Create an execution object, run it, and await its execution result
        const execution = new Execution(problem, solution);
        const result = await execution.run(index);
        // Store the result in the array to be retorned to the client
        results.push(result);
      }  
      // TODO: store executions in array of promises and run them in parallel Promise.all()
      // const executions: Promise<nodeFetch.Response>[] = [];
      // for (let index = 0; index < problem.tests.length; ++index) {
      //   executions.push(fetch(uri, options));
      //   executions.push( { uri, options } );
      // then
      // const results = await Promise.all(executions)
      //   .then(async (responses) => Promise.all(responses.map(async (body) => {
      //     await body.json();
      //   })));
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
