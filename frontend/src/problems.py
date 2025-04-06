import flask
import json
import requests
import vyg

MAX_THREADS = 2**16

# vyg.ProblemInterface {
#   name: string;
#   title: string;
#   statement: string;
#   tests: TestInterface[];
#   languages: string[]; # C, C++, Java, Python...
#   # Map<string, string> but not supported by JSON
#   initialCodeFor?: InitialCodeInterface;
#   minThreads?: number;
#   maxThreads?: number;
#   allowIndeterminism?: string;
#   mustContain?: Array<string>;
#   minDuration?: number;
#   maxDuration?: number;

# interface vyg.TestInterface {
#   input: string;
#   output: string;
#   points: number;
#   hidden: boolean; # TODO: clear it from server side
#   minThreads?: number;
#   maxThreads?: number;
#   minDuration?: number;
#   maxDuration?: number;

# Attributes of these classes are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

class ExecutionResult:
    """ Result of running student solution against all test cases """
    def __init__(self):
        # Count of passed test cases
        self.passedTestCount = 0
        # Points gained by this solution
        self.points = 0
        # Total points (sum of all test cases)
        self.totalPoints = 0
        # Wall time of the largest test case
        self.maxWallTime = float('-inf')
        # Results of each test case
        self.results = [] # TestCaseResult[]

class Problem:
    """ Represents a programming problem with statement, source code, and test cases """
    def __init__(self, relative_path:str, json_dict: dict):
        """Load the fields of this object from the given JSON file path"""
        # The relative path that identifies the problem
        self.relative_path = relative_path
        # An identifier name for the problem, eg "uint64_adder"
        self.name = json_dict.get('name')
        # Title describing the problem, eg "Unsigned 64-bits adder"
        self.title = json_dict.get('title')
        # Problem statement in HTML code
        # TODO(jhc): use problem.{en|es|...}.{md|adoc|html} files instead
        self.statement = json_dict.get('statement')
        # An array of test cases
        self.tests = json_dict.get('tests')
        # TODO(jhc): enabled programming languages, e.g: c,cpp,py,...
        # Allowed programming languages for this problem
        self.languages = json_dict.get('languages', [])
        # The given initial source code for the problem and programming language
        self.initialCodeFor = json_dict.get('initialCodeFor', { })
        # Minimum number of secondary threads to solve the problem. If this number
        # is one or more, additional runs will be conducted for each test case
        self.minThreads = json_dict.get('minThreads', 0)
        # There is no limit for the default number of secondary threads
        self.maxThreads = json_dict.get('maxThreads', MAX_THREADS)
        # Considers valid an output that has different order than the expected
        # Supported values: 'lines'
        self.allowIndeterminism = json_dict.get('allowIndeterminism')
        # Considers invalid a solution if it does NOT contains words in this array
        self.mustContain = json_dict.get('mustContain')
        # Allowed time range in seconds specified by professor for all test cases
        self.minDuration = json_dict.get('minDuration')
        self.maxDuration = json_dict.get('maxDuration')
        # Remove HTML escaping for all languages
        for lang, code in self.initialCodeFor.items():
            code = code.replace('&amp;', '&')
            code = code.replace('&lt;', '<')
            code = code.replace('&gt;', '>')
            self.initialCodeFor[lang] = code

    @staticmethod
    def load(problem_path:str):
        """ Creates a new Problem object from the given relative path problem eg: uint64_adder """
        # Problems are stored in data/path/vygoj.json
        abs_path = f'{vyg.get_problem_path()}/{problem_path}/vygoj.json'
        # Read the contents of the file
        with open(abs_path, encoding='utf8') as file:
            # Load the fields from the json file
            json_dict = json.load(file)
            return Problem(problem_path, json_dict)

    def calculate_total_points(self):
        """ Calculates the total amount of points from the test cases """
        total = 0
        for test in self.tests:
            # If test has no a points property, we use 0
            total += test.get('points', 0)
        return total

    def has_proofs(self):
        """ Returns true if this problem requires the solution to pass extra proofs """
        return self.minThreads >= 1

# pylint: enable=invalid-name

class ProblemController:
    """Controls problems

    A problem page contains:
    - a problem statement
    - a text editor to provide a solution
    - a combo box for choosing between the enabled programming languages
    - a Submit/Run button
    - a test case list
    - a test case detail control

    Users read the problem statement, write a code solution in the selected
    programming language, and submit the solution. An AJAX code asks the
    backend to run the solution. The answers are sent to the client that shows
    them to the user.

    The answer contains compiler/interpreter diagnostics. If the code produced
    no errors a report of each passed/failed test case is provided. The AJAX
    code shows these results to the user who can modify the code and submit
    a new solution. This process repeat until user solves the problem or leaves
    the page.    
    """
    def __init__(self):
        pass

    @staticmethod
    def get_problem(path):
        """Get the contents page for a course"""
        problem = Problem.load(path)
        if not problem:
            flask.abort(404)
        return flask.render_template('problem.html', it={
            'stylesheet': 'problems',
            'title': problem.title,
            'user': {'name': 'You', 'role': 'admin'}, # TODO(I): flask.q.session.user,
            'breadcrumbs': [
                # TODO(I): course
                { 'href': '/course/stdthr', 'text': 'CI0117a' },
                { 'href': f'/problem/{problem.relative_path}', 'text': problem.name },
            ],
            'problem': problem,
            'scripts': [
                ('<script src="https://cdn.jsdelivr.net/npm/ace-builds@1.4.13/src-min/ace.js"'
                    ' crossorigin="anonymous" async="async"'
                    ' integrity="sha256-bS3VAQePcKYmsvI+8BdG2QJAVb9FbiZLgM5vK2/+TcM="></script>'),
                ('<script src="https://cdn.jsdelivr.net/npm/ace-diff@3.0.3/dist/ace-diff.min.js"'
                    'async="async"></script>'),
                '<script src="/js/problem/problem.js" type="module" async="async"></script>',
            ],
        })

    @staticmethod
    def post_problem(problem_path):
        """Client JavaScript asked for an action: fetch a problem, run user solution,
        save user code, ... All communication is made with JSON objects
        """
        # try:
        message = vyg.Message(json.loads(flask.request.get_data()))
        print(problem_path, ' --> ', message.__dict__)
        match message.action:
            case 'fetch_problem': return ProblemController.fetch_problem(problem_path)
            case 'run': return ProblemController.judge_solution(problem_path, message)
            case _: return flask.jsonify({ 'error': 'invalid action' })
        # except Exception:
        #     return flask.jsonify({ 'error': 'invalid action' })

    @staticmethod
    def fetch_problem(problem_path: str):
        """ Return a JSON version of the problem """
        problem = Problem.load(problem_path)
        json_result = vyg.to_json(problem)
        print(json_result)
        #return flask.jsonify(problem)
        return json_result

    @staticmethod
    def judge_solution(problem_path: str, message: vyg.Message):
        """ Called when user input a source code solution and press Run button """
        # Load the problem
        problem = Problem.load(problem_path)
        # Run the test cases and wait for the array of results
        results = ProblemController.run_test_cases(problem, message) # as vyg.TestCaseResult[]
        # Embed the results into a object with statistics
        result = ProblemController.create_result(problem, results)
        # Store progress
        # TODO(I): assert req.session.user
        #progress = 100.0 * result.points / result.totalPoints
        # TODO(I): req.session.user?.storeProgress(problem.name, progress);
        return vyg.to_json(result)

    @staticmethod
    def run_test_cases(problem: Problem, solution: vyg.Message):
        """ Compile solution and run it against all test cases. Return an array of verdicts """
        submission = { 'problem': problem.__dict__, 'solution': solution.__dict__ }
        # Create an array of results, one for each test case
        # TODO(jhc): get these args from config
        results = requests.post('http://localhost:9090/run', timeout=1000, json=submission).json()
        # The user program is executed once for each test case
        # TODO(jhc): Run in parallel
        return results

    @staticmethod
    def create_result(problem: Problem, results): # results:TestCaseResult[] -> ExecutionResult
        """ Generates a Execution result summary from the test cases results """
        # The result object has some statistics
        execution_result = ExecutionResult()
        # Calculate them
        #assert len(results) == len(problem.tests)
        for index, test in enumerate(results.get('outputs')):
            # If the test was passed
            if test.get('status') == vyg.ExecutionStatus.PASSED:
                # Increase the count of passed test cases and accumulate the points
                execution_result.passedTestCount += 1
                execution_result.points += problem.tests[index].points
                execution_result.totalPoints += problem.tests[index].points
            # If this test case lasted longer than the longest known
            #test_time = float(test.wallTime or test.cpuTime or '')
            #execution_result.maxWallTime = max(results.get('totalDuration'), test_time)
        # Build the result object
        return execution_result
