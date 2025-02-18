import flask
import json
import os

MAX_THREADS = 2**16

# vyg.ProblemInterface {
#   name: string;
#   title: string;
#   statement: string;
#   tests: TestInterface[];
#   languages: string[]; // C, C++, Java, Python...
#   // Map<string, string> but not supported by JSON
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
#   hidden: boolean; // TODO: clear it from server side
#   minThreads?: number;
#   maxThreads?: number;
#   minDuration?: number;
#   maxDuration?: number;

# TODO(jhc): Move to common
def get_app_path():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_problem_path():
    return os.path.join(get_app_path(), 'problems')


class Problem:
    """ Represents a programming problem with statement, source code, and test cases """
    def __init__(self, relative_path, json_dict):
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
        self.initial_code_for = json_dict.get('initialCodeFor', { })
        # Minimum number of secondary threads to solve the problem. If this number
        # is one or more, additional runs will be conducted for each test case
        self.min_threads = json_dict.get('minThreads', 0)
        # There is no limit for the default number of secondary threads
        self.max_threads = json_dict.get('maxThreads', MAX_THREADS)
        # Considers valid an output that has different order than the expected
        # Supported values: 'lines'
        self.allow_indeterminism = json_dict.get('allowIndeterminism')
        # Considers invalid a solution if it does NOT contains words in this array
        self.must_contain = json_dict.get('mustContain')
        # Allowed time range in seconds specified by professor for all test cases
        self.min_duration = json_dict.get('minDuration')
        self.max_duration = json_dict.get('maxDuration')
        # Remove HTML escaping for all languages
        for lang, code in self.initial_code_for.items():
            code = code.replace('&amp;', '&')
            code = code.replace('&lt;', '<')
            code = code.replace('&gt;', '>')
            self.initial_code_for[lang] = code

    @staticmethod
    def load(problem_path):
        """ Creates a new Problem object from the given relative path problem eg: uint64_adder """
        # Problems are stored in data/path/vygoj.json
        abs_path = f'{get_problem_path()}/{problem_path}/vygoj.json'
        # Read the contents of the file
        with open(abs_path, encoding='utf8') as file:
            # Load the fields from the json file
            json_dic = json.load(file)
            return Problem(problem_path, json_dic)

    def calculate_total_points(self):
        """ Calculates the total amount of points from the test cases """
        total = 0
        for test in self.tests:
            # If test has no a points property, we use 0
            total += test.get('points', 0)
        return total

    def has_proofs(self):
        """ Returns true if this problem requires the solution to pass extra proofs """
        return self.min_threads >= 1


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
