""" Programming problems """
import glob
import json
import os
import re

# TODO(jhc): markdown is only required by frontend, not backend
import markdown

from vyg.activity import Activity
from vyg.constants import LANGUAGE_EXTENSIONS, MAX_THREADS
from vyg.material import Material
from vyg.testcase import TestCase
from vyg.utils import decode_if, run_cmd

# Attributes of this class are shared with JS client code and use the JS name convention
# pylint: disable=invalid-name

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
