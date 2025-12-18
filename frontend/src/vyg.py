""" Common classes for VygOJ backend and frontend server """
import base64
import copy
import enum
import glob
import json
import os
import re
import subprocess
from abc import ABC as abstract
# TODO(jhc): markdown is only required by frontend, not backend
import markdown

# Maximum number of allowed execution threads to be created by a user solution
MAX_THREADS = 2**15

class Status(str, enum.Enum):
    """ Status of the execution of a programming solution.
    The str inheritance eases the translation to and from JSON """
    PENDING = 'pending'
    PASSED = 'passed'
    WRONG = 'wrong'
    TIMEOUT = 'timeout'
    COMPILER_ERROR = 'compilerError'
    RUNTIME_ERROR = 'runtimeError'
    INTERNAL_ERROR = 'internalError'

# Map file extensions to supported programming languages
LANGUAGE_EXTENSIONS = {
    'ale': 'Alecci',
    'c': 'C',
    'cpp': 'C++',
    'java': 'Java',
    'js': 'JavaScript',
    'kt': 'Kotlin',
    'py': 'Python',
}

# Create the inverse dictionary mapping languages to their extensions
EXTENSION_LANGUAGES = {value: key for key, value in LANGUAGE_EXTENSIONS.items()}

def get_app_path():
    """ Return the path where the docker app is located """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_path(subfolder:str):
    """ Return subfolder where programming problems are stored """
    return os.path.join(get_app_path(), subfolder)

def encode(value): # :str|dict
    """ Codifies the given text to base64 in order to transport it as a JSON value """
    if isinstance(value, dict):
        return encode_dict(value)
    return str(base64.b64encode(value.encode('utf-8')))[2:-1] if value else ''

def encode_dict(json_dict:dict):
    """ Codifies the values of dictionary to base64 in order to transport it as a JSON value """
    for key in json_dict.keys():
        json_dict[key] = encode(json_dict[key])
    return json_dict

def decode(value): # :str|dict
    """ De-codifies the given text in base64 to plain text """
    if isinstance(value, dict):
        return decode_dict(value)
    return base64.b64decode(value).decode('utf-8')

def decode_dict(json_dict:dict):
    """ De-codifies the values of the given dictionary in base64 to plain text """
    for key in json_dict.keys():
        json_dict[key] = decode(json_dict[key])
    return json_dict

def decode_if(value, cond):
    """ Decodes the given value only if the condition is true """
    return decode(value) if cond else value

def prepend(text, prefix, sep = ' '):
    """ Prepends the prefix to the text separated by sep if prefix is not empty """
    return f'{prefix}{sep}{text}' if prefix else text

def append(text, suffix, sep = ' '):
    """ Appends the suffix to the text separated by sep if suffix is not empty """
    return f'{text}{sep}{suffix}' if suffix else text

def to_dict(data_object):
    """ Returns a dictionary with data attributes of data_object. If the class for the data_object
    has a static attribute named encoded fields, the values for those fields are encoded to
    base64 strings. The data_object is not modified. """
    # By the default, return the direct dictionary representation of the object
    # Because it may be modified, we make a copy to preserve the original object intact
    result = copy.deepcopy(data_object.__dict__)
    # Do not export to JSON private non-serializable attributes (starts with _) or are empty
    # Traverse original dictionary because copy will be modified
    for field in data_object.__dict__:
        if field.startswith('_') or not result[field]:
            del result[field]
    # If class has a static attribute encoded_fields as a list of strings (attribute names)
    if hasattr(data_object.__class__, 'encoded_fields'):
        # For each field to be encoded
        for field in data_object.__class__.encoded_fields:
            # If the object has a value for the attribute
            if field in result:
                # Encode the value of the attribute to the temporary dictionary
                if isinstance(result[field], dict):
                    # The field contains a dictionary, but only its values must be encoded
                    for key in result[field].keys():
                        result[field][key] = encode(result[field][key])
                else:
                    result[field] = encode(result[field])
    # Return the dictionary that will be converted to JSON
    return result

def to_json(data_object):
    """ Convert the given Python object to JSON string """
    # See https://docs.python.org/3/library/json.html#json.dump
    return json.dumps(data_object, default=to_dict, indent=2)

def run_cmd(cmd):
    ''' Run cmd as a separate process and waits for its completion. cmd is a list of parameters '''
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True) as process:
        # Wait until the sub-process finishes, capture stdin and stdout
        stdout, stderr = process.communicate()
        return_code = process.returncode
        return stdout, stderr, return_code


class Message:
    """ All messages exchanged between the JS client and Python server are generic.
        Send { } as json_dict to init Message to empty fields """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['code', 'error']

    def __init__(self, json_dict:dict):
        """ Construct this object getting values from the given dictionary """
        # Valid actions: fetch_problem | run
        self.action = json_dict.get('action', '')
        # Used when an error happens, and the rest of the message is invalid
        self.error = decode(json_dict.get('error', ''))
        # The programming language used in field code
        self.language = json_dict.get('language', '')
        # The source code
        self.code = decode(json_dict.get('code', ''))

# Attributes of these classes are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

class Material(abstract):
    """ A material is any educational resource created by professors to support the learning of
    students in a course. It can be a page, a question, a programming problem, even a course itself.
    """
    # Fields to be encoded using base64 when serializing to JSON when are send or received by
    # network. Fields loaded from vygoj.json files may be not encoded when created by hand.
    encoded_fields = ['title']

    def __init__(self, json_dict: dict, parent: 'Material', should_decode: bool):
        """ Construct the base part of a Material. json_dict is the dictionary where the values for
        attributes will be loaded from. If should_decode is false, means json_dict was read from a
        vygoj.json file created by humans, so the its values are not base64 encoded. If
        should_decode is true, means the json_dict was received by network. parent is the material
        that contains this material.
        """
        # Reference to the parent material that contains this material, or None if it is the course
        # It is a private attribute, not serialized to JSON, so it starts with _
        self._parent = parent
        # The type of material: 'course', 'section', 'page', 'question', 'problem'. This field is
        # no needed for the memory objects because the type is inferred from the class. It is kept
        # for the JSON representation of the object.
        self.type = json_dict.get('type', '')
        # The folder where this material is stored. Materials can be nested, and folders are
        # concatenated to form a path. For example, a problem in a section of a course may be
        # 'data/user@email.edu/repo/course/section/problem_name'.
        self.folder = json_dict.get('folder', '')
        # An identification name, such as 'CI0117', 'c_hello_world'. It must be unique within the
        # course. If no name is specified, use the folder as the identification name.
        self.name = json_dict.get('name', self.folder)
        # A human readable title, such as 'Programming I', 'Hello world'
        self.title = decode_if(json_dict.get('title', ''), should_decode)
        # Relative date when the material is enabled to students access it. Use relative dates in
        # repository, because they are recommendations. Absolute dates are override by course
        # offerings in the database. A real value means weeks. An empty value means "always enabled"
        self.start = json_dict.get('start', '')
        # Date when the material is overdue, empty means "never overdue". Same rules than start
        self.finish = json_dict.get('finish', '')
        # Action policy when a material is overdue: 'hidden', 'disabled', 'half'
        # 'hidden' means the material is not shown to students at all
        # 'disabled' means it is shown but read-only,
        # 'half' means students can solve the material but get half of the points
        self.overdue_policy = json_dict.get('overdue_policy', 'disabled')
        # Add this material to the course's symbols table, so it can be found by name
        if parent and parent.get_course():
            parent.get_course().add_symbol(self)
        # Materials can be nested, so a material can have a list of contents. Load them
        self.contents = []
        # Notice parent is not used for child materials, because self is the parent for them
        self.load(json_dict.get('contents', []), should_decode)

    def load(self, contents: list, should_decode: bool):
        """ Load the contents of this material that are also materials. """
        # For each entry in the JSON contents list, create a Material object
        for entry in contents:
            self.contents.append(Material.create(entry, self, should_decode))

    @staticmethod
    def create(json_dict: dict, parent: 'Material', should_decode: bool):
        """ Create a Material object from a JSON dictionary entry. """
        material_type = json_dict.get('type', '')
        if material_type == 'section':
            return Section(json_dict, parent, should_decode)
        if material_type == 'page':
            return Page(json_dict, parent, should_decode)
        if material_type == 'question':
            return Question(json_dict, parent, should_decode)
        if material_type == 'problem':
            return Problem(json_dict, parent, should_decode)
        raise TypeError(f'Unknown material type: {material_type}')

    def get_course(self) -> 'Course':
        """ Returns the course that contains this material """
        # The course has no parent (root material), otherwise, search the parent material
        if self._parent is None:
            return self if isinstance(self, Course) else None
        return self._parent.get_course()

    def get_path(self) -> str:
        """ Returns the path where this material is stored, e.g:
        data/u13/pexercises/1.1_io/hello/ """
        # My path is the concatenation of all parent materials and my folder
        return os.path.join(self._parent.get_path(), self.folder) if self._parent else self.folder

    def build_url(self) -> str:
        """ Returns the URL to access this material in the web application """
        # The URL is the concatenation of the course name and my folder
        course_name = f'{self.get_course().name}/' if self._parent else ''
        return f'/{self.type}/{course_name}{self.name}'



class Resource(Material):
    """ A resource is a static material that is not evaluated to students during the course """
    # Fields to be encoded using base64 when serializing to JSON for network exchange.
    encoded_fields = ['description']

    def __init__(self, json_dict: dict, parent: Material, should_decode: bool):
        """ Construct this object getting values from the given dictionary """
        super().__init__(json_dict, parent, should_decode)
        # Resources may contain rich text in HTML format
        self.description = decode_if(json_dict.get('description', ''), should_decode)


class Course(Resource):
    """
    A course is an abstract structural concept. It is a collection of educative resources
    (materials) designed by professors to help students to learn about a specific subject.
    Do not confuse with a course offering/group, which is an instance of a course, that is an
    educative event, lasting -but not limited to- an academic term where professors and students
    share and build knowledge and skills. A course is compound of materials, a course offering
    is a course with dates and students enrolled in it.

    In a systems perspective, a course is compound of several resources:

    - Attributes: name, title, description, image, startDate, finishDate
    - Instructors (teachers, professors)
    - Students
    - Sections that can be nested
    - Pages that contain grading assignments, such as
      - Questions
      - Programming problems
    - Grades

    A course has four states:

    - Editing: When it is being modified by professors.
    - Future: When it is ready but its start date is coming.
    - Active: When it is being used by students.
    - Finalized: When its finish date passed or professors closed it.
    """
    def __init__(self, json_dict: dict, should_decode: bool, folder: str):
        """ Construct this object getting values from the given dictionary """
        # A table of symbols that maps the material names to their objects
        self._symbols = {}
        super().__init__(json_dict, None, should_decode)
        # Override the folder with the repository folder where courses are stored, e.g:
        # data/u13/pexercises
        self.folder = folder
        # Courses may have an allusive image for helping users to identify it
        self.image = json_dict.get('image', '')
        # Professors that created the course, they may be different than professors who teach it
        self.authors = json_dict.get('authors', [])
        # Status of the course: 'editing', 'available', 'enabled', 'disabled'
        # TODO(jhc): is status needed? snapshots make editing unnecessary, available is the default
        # self.status = json_dict.get('status', '')

    def add_symbol(self, material: 'Material'):
        """ Add this material to the course's symbols table, so it can be found by name """
        if material.name:
            if material.name in self._symbols:
                raise ValueError(f'Material {material.name} duplicated in course {self.name}')
            self._symbols[material.name] = material

    def find_symbol(self, name: str) -> 'Material':
        """ Find a material by its name """
        return self._symbols.get(name)

class Section(Resource):
    """ A section is a group of materials that are thematically related. They can be nested to
    represent parts, chapters, sections, subsections, and so on. Sections look similar to Pages,
    but sections are listed in the table of contents of the course, while Pages are not."""


class Page(Resource):
    """ A page is a material that contains text, images, and videos. It can be used to
    present concepts, or instructions. After its description, other materials can be nested.
    Pages are not listed in the table of contents of the course. """


class Activity(Material):
    """ An activity is a material that requires an action from the student and it is graded by
    professors or teaching assistants """

    def __init__(self, json_dict: dict, parent: Material, should_decode: bool):
        """ Construct this object getting values from the given dictionary """
        super().__init__(json_dict, parent, should_decode)
        # Activities can have different weight over the final course grade
        self.weight = json_dict.get('weight', 1.0)


class Question(Activity):
    """ A question is a request for information from students. If student matches the right answer,
    s/he gains points. Questions have variables. Each variable has its own type, text, and answer.
    """
    # Fields to be encoded using base64 when serializing to JSON for network exchange.
    encoded_fields = ['text']

    def __init__(self, json_dict: dict, parent: Material, should_decode: bool):
        """ Construct this object getting values from the given dictionary """
        super().__init__(json_dict, parent, should_decode)
        # Sections may include a short description. For large text nest a Page object
        self.text = decode_if(json_dict.get('text', ''), should_decode)


class Problem(Activity):
    """ Represents a programming problem with statement, source code, and test cases """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = Material.encoded_fields + ['statement', 'mustContain', 'initialCodeFor']

    def __init__(self, json_dict: dict, parent: Material, should_decode: bool):
        """ Load the fields of this object from JSON dictionary """
        super().__init__(json_dict, parent, should_decode)
        # Problem statement in HTML code
        # TODO(jhc): use problem.{en|es|...}.{md|adoc|html} files instead
        self.statement = decode_if(json_dict.get('statement', ''), should_decode)
        # An array of test cases
        self.tests = Problem.load_tests(json_dict.get('tests', []), should_decode)
        # Allowed programming languages for this problem
        self.languages = json_dict.get('languages', [])
        # The given initial source code for the problem and programming language
        self.initialCodeFor = decode_if(json_dict.get('initialCodeFor', { }), should_decode)
        # Minimum number of secondary threads to solve the problem. If this number
        # is one or more, additional runs will be conducted for each test case
        self.minThreads = json_dict.get('minThreads', 0)
        # There is no limit for the default number of secondary threads
        self.maxThreads = json_dict.get('maxThreads', MAX_THREADS)
        # Considers valid an output that has different order than the expected
        # Supported values: 'none', 'lines'
        self.allowIndeterminism = json_dict.get('allowIndeterminism', 'none')
        # Considers invalid a solution if it does NOT contains words in this array
        self.mustContain = decode_if(json_dict.get('mustContain', ''), should_decode)
        # Allowed time range in seconds specified by professor for all test cases
        self.minDuration = json_dict.get('minDuration', '')
        # Maximum wall time duration that user solution must spent to consider it correct
        self.maxDuration = json_dict.get('maxDuration')
        # Extra tools, one of: asan tsan ubsan memcheck helgrind
        self.tools = json_dict.get('tools', '')
        # Remove HTML escaping for all languages
        # for lang, code in self.initialCodeFor.items():
        #     code = code.replace('&amp;', '&')
        #     code = code.replace('&lt;', '<')
        #     code = code.replace('&gt;', '>')
        #     self.initialCodeFor[lang] = code
        self.folder_loaded = False

    @staticmethod
    def load_tests(json_tests, should_decode=True):
        """ For each given test case, add it to the self.test[] array """
        tests = []
        for test in json_tests:
            tests.append(TestCase(test, should_decode))
        return tests

    def calculate_total_points(self):
        """ Calculates the total amount of points from the test cases """
        total = 0
        for test in self.tests:
            # If test has no a points property, we use 0
            total += test.points
        return total

    def has_proofs(self):
        """ Returns true if this problem requires the solution to pass extra proofs """
        return self.minThreads >= 1

    def load_folder(self):
        """ Load problem data from the folder where it is stored """
        if self.folder_loaded is False:
            path = self.get_path()
            self.load_json(path)
            self.load_problem_statement(path)
            self.folder_loaded = True
            self.load_initial_code(path)
            self.load_test_cases(path)

    def load_json(self, path):
        """ Load the JSON file, if any, with configuration for this problem """
        path = os.path.join(path, 'vygoj.json')
        if os.path.isfile(path):
            with open(path, encoding='utf8') as file:
                json_dict = json.load(file)
                # Load the fields of this object from JSON dictionary to a new object
                problem = Problem(json_dict, self._parent, False)
                # Copy the fields from the loaded problem to this problem. Dictionary update does
                # not work because some fields in problem are empty and would erase existing data
                #self.__dict__.update(problem.__dict__)
                # Merge non empty properties of problem into self. An object replacement
                # is problematic because self is already referenced by parent material
                for key, value in problem.__dict__.items():
                    if key[0] != '_' and value:
                        setattr(self, key, value)

    def load_problem_statement(self, path):
        """ Load the problem statement from Asciidoc, Markdown, or HTML file """
        if not self.statement:
            extensions = ['html', 'adoc', 'md']
            for extension in extensions:
                files = glob.glob(os.path.join(path, f'*.{extension}'))
                for filename in files:
                    if extension == 'html':
                        with open(filename, encoding='utf8') as file:
                            self.statement += file.read()
                    elif extension == 'adoc':
                        # Convert Asciidoc file to HTML
                        stdout, _, _ = run_cmd(['asciidoctor', filename, '-e', '-o', '-'])
                        self.statement += stdout
                    elif extension == 'md':
                        with open(filename, encoding='utf8') as file:
                            self.statement += markdown.markdown(file.read())

    def load_initial_code(self, path):
        """ Load the initial code from a file """
        enable_language = len(self.languages) == 0
        if len(self.initialCodeFor) == 0:
            files = (glob.glob(os.path.join(path, 'initial/*')) +
                    glob.glob(os.path.join(path, 'given/*')))
            for filename in files:
                with open(filename, encoding='utf8') as file:
                    # Extract file extension without dot
                    ext = os.path.splitext(filename)[1][1:]
                    # If extension is recognized as a programming language
                    if ext in LANGUAGE_EXTENSIONS:
                        language = LANGUAGE_EXTENSIONS.get(ext)
                        initial_code = file.read()
                        # TODO(jhc): support multi-file initial codes
                        if language in self.initialCodeFor:
                            self.initialCodeFor[language] += '\n' + initial_code
                        else:
                            self.initialCodeFor[language] = initial_code
                        if enable_language and language not in self.languages:
                            self.languages.append(language)
            # If initial code remains empty, enable at least one language
            if enable_language and len(self.languages) == 0:
                self.languages.append('C')

    def load_test_cases(self, path):
        """ Load the test cases from the problem folder """
        if len(self.tests) > 0:
            return  # Test cases are already loaded
        # TODO(jhc): implement test case generators
        # For each file tests/input<number>.txt read its entire contents to a variable input,
        # read the content of its correspondent tests/output<number>txt file to a variable
        # output, create a dictionary {'input': input, 'output': output} and append it to the
        # test_cases list
        input_files = sorted(glob.glob(os.path.join(path, 'tests/input*.txt')))
        for input_file in input_files:
            match = re.search(r'input(\d+)\.txt$', input_file)
            if not match:
                continue
            num = match.group(1)
            output_file = os.path.join(path, f'tests/output{num}.txt')
            if not os.path.exists(output_file):
                raise ValueError(f'Output file {output_file} not found for input {input_file}')
            with open(input_file, 'r', encoding='utf8') as file:
                input_content = file.read()
            with open(output_file, 'r', encoding='utf8') as file:
                output_content = file.read()
            # TODO(jhc): reuse code for files
            args_content = Problem.load_test(os.path.join(path, f'tests/args{num}.txt'))
            error_content = Problem.load_test(os.path.join(path, f'tests/error{num}.txt'))
            # TODO(jhc): if vygoj.json does not contain input/output, fetch from file
            json_dict = {
                'args': args_content,
                'input': input_content,
                'output': output_content,
                'error': error_content,
                'points': 1
            }
            self.tests.append(TestCase(json_dict, False))

    @staticmethod
    def load_test(file_path):
        """ Load the contents of a file, or return an empty string if the file does not exist """
        if os.path.isfile(file_path):
            with open(file_path, 'r', encoding='utf8') as file:
                return file.read()
        return ''

class TestCase:
    """ A test case for black-box testing provides the input data to run a user solution code,
        and compare its output against the expected output. If they match, user gain points. """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['args', 'input', 'output', 'error']

    def __init__(self, json_dict:dict, should_decode=True):
        """ Construct this object getting values from the given dictionary """
        # Command line arguments to send to the user solution when running this test case
        self.commandLineArguments = decode_if(json_dict.get('args', ''), should_decode)
        # Text to send to user solution through stdin
        self.input = decode_if(json_dict.get('input', ''), should_decode)
        # Expected output
        self.output = decode_if(json_dict.get('output', ''), should_decode)
        # Expected error
        # TODO(jhc): If missing (None), allow using stderr for debug, because '' must match
        self.stderr = decode_if(json_dict.get('error', ''), should_decode)
        # Points that user earns if its solution matches the expected output
        self.points = json_dict.get('points', 0)
        # If true, the test case is hidden for users, so they cannot see what is in it
        self.hidden = json_dict.get('hidden', False)
        # Minimum number of threads that user solution must create in order to consider it right
        self.minThreads = json_dict.get('minThreads', 1)
        # Maximum number of threads that user solution may create to consider it correct
        self.maxThreads = json_dict.get('maxThreads', MAX_THREADS)
        # Minimum wall time duration that user solution must spent to consider it correct
        self.minDuration = json_dict.get('minDuration')
        # Maximum wall time duration that user solution must spent to consider it correct
        self.maxDuration = json_dict.get('maxDuration')

class ExecutionResult:
    """ Result of running student solution against all test cases """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['message', 'compileOutput']

    def __init__(self, json_dict:dict):
        """ Construct this object getting values from the given dictionary """
        # We suppose student's code solves the problem, until a test fails
        self.status = Status(json_dict.get('status', Status.PASSED))
        # A human-readable verdict emitted by the judge
        self.message = decode(json_dict.get('message', ''))
        # Compiler output or null if no output was generated
        self.compileOutput = decode(json_dict.get('compileOutput', ''))
        # Count of passed test cases
        self.passedTestCount = json_dict.get('passedTestCount', 0)
        # Points gained by this solution
        # TODO(jhc): used?
        self.points = json_dict.get('points', 0)
        # Total points (sum of all test cases)
        self.totalPoints = json_dict.get('totalPoints', 0)
        # Wall time of the largest test case
        self.maxWallTime = json_dict.get('maxWallTime', -1.0)
        # Results of each test case
        self.results:TestCaseResult = []
        for test_result_json in json_dict.get('results', []):
            self.results.append(TestCaseResult(test_result_json))

class TestCaseResult:
    """ Result of running a test case """
    # Fields to be encoded using base64 when serializing to JSON
    encoded_fields = ['message', 'stderr', 'stdout']

    def __init__(self, json_dict:dict):
        """ Construct this object getting values from the given dictionary """
        # An enumeration value code of the verdict, see vyg.Status
        self.status = Status(json_dict.get('status', Status.PASSED))
        # A human-readable verdict emitted by the judge
        self.message = decode(json_dict.get('message', ''))
        # CPU time, i.e all threads added up
        self.cpuTime = json_dict.get('cpuTime', 0.0)
        # Exit code reported by the program to the operating system after running this test case
        self.exitCode = json_dict.get('exitCode', 0)
        # Memory used by the process (bytes)
        self.memory = json_dict.get('memory', 0)
        # Text produced by the user solution in the standard error
        self.stderr = decode(json_dict.get('stderr', ''))
        # Text produced by the user solution in the standard output
        self.stdout = decode(json_dict.get('stdout', ''))
        # Number of threads created by solution for this test case
        self.threadCount = json_dict.get('threadCount', 0)
        # Elapsed wall time running this test case in seconds
        self.wallTime = json_dict.get('wallTime', 0.0)
        # TODO(jhc): number_of_runs?

# pylint: enable=invalid-name
