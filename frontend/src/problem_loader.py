""" Loads programming problems from the folders of course repositories """
import glob
import json
import os
import re
import subprocess

import markdown

import vyg

# Maximum seconds that asciidoctor may spend converting a problem statement to HTML
ASCIIDOCTOR_TIMEOUT = 30

class ProblemLoader:
    """ Fills a vyg.Problem with the files stored in its folder: the vygoj.json configuration,
    the statement in HTML, Asciidoc, or Markdown, the initial code, and the test cases """

    @staticmethod
    def load_folder(problem: vyg.Problem):
        """ Load problem data from the folder where it is stored """
        if problem.folder_loaded is False:
            path = problem.get_path()
            ProblemLoader.load_json(problem, path)
            ProblemLoader.load_problem_statement(problem, path)
            problem.folder_loaded = True
            ProblemLoader.load_initial_code(problem, path)
            ProblemLoader.load_test_cases(problem, path)

    @staticmethod
    def load_json(problem: vyg.Problem, path: str):
        """ Load the JSON file, if any, with configuration for this problem """
        path = os.path.join(path, 'vygoj.json')
        if os.path.isfile(path):
            with open(path, encoding='utf8') as file:
                # Files are written by hand, so their values are not base64 encoded
                problem.merge(json.load(file), False)

    @staticmethod
    def load_problem_statement(problem: vyg.Problem, path: str):
        """ Load the problem statement from Asciidoc, Markdown, or HTML file """
        if not problem.statement:
            extensions = ['html', 'adoc', 'md']
            for extension in extensions:
                files = glob.glob(os.path.join(path, f'*.{extension}'))
                for filename in files:
                    if extension == 'html':
                        with open(filename, encoding='utf8') as file:
                            problem.statement += file.read()
                    elif extension == 'adoc':
                        problem.statement += ProblemLoader.convert_asciidoc(filename)
                    elif extension == 'md':
                        with open(filename, encoding='utf8') as file:
                            problem.statement += markdown.markdown(file.read())

    @staticmethod
    def convert_asciidoc(filename: str) -> str:
        """ Convert the given Asciidoc file to embeddable HTML """
        # Course repos are untrusted, so the safe mode restricts include:: to the folder of the
        # statement, otherwise a statement could include any readable file of the server. A
        # timeout prevents a malformed statement from blocking the request forever
        process = subprocess.run(['asciidoctor', '-S', 'safe', filename, '-e', '-o', '-'],
            capture_output=True, text=True, timeout=ASCIIDOCTOR_TIMEOUT, check=False)
        return process.stdout

    @staticmethod
    def load_initial_code(problem: vyg.Problem, path: str):
        """ Load the initial code from a file """
        enable_language = len(problem.languages) == 0
        if len(problem.initialCodeFor) == 0:
            files = (glob.glob(os.path.join(path, 'initial/*')) +
                    glob.glob(os.path.join(path, 'given/*')))
            for filename in files:
                with open(filename, encoding='utf8') as file:
                    # Extract file extension without dot
                    ext = os.path.splitext(filename)[1][1:]
                    # If extension is recognized as a programming language
                    if ext in vyg.LANGUAGE_EXTENSIONS:
                        language = vyg.LANGUAGE_EXTENSIONS.get(ext)
                        initial_code = file.read()
                        # TODO(jhc): support multi-file initial codes
                        if language in problem.initialCodeFor:
                            problem.initialCodeFor[language] += '\n' + initial_code
                        else:
                            problem.initialCodeFor[language] = initial_code
                        if enable_language and language not in problem.languages:
                            problem.languages.append(language)
            # If initial code remains empty, enable at least one language
            if enable_language and len(problem.languages) == 0:
                problem.languages.append('C')

    @staticmethod
    def load_test_cases(problem: vyg.Problem, path: str):
        """ Load the test cases from the problem folder """
        if len(problem.tests) > 0:
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
            args_content = ProblemLoader.load_test(os.path.join(path, f'tests/args{num}.txt'))
            error_content = ProblemLoader.load_test(os.path.join(path, f'tests/error{num}.txt'))
            # TODO(jhc): if vygoj.json does not contain input/output, fetch from file
            json_dict = {
                'args': args_content,
                'input': input_content,
                'output': output_content,
                'error': error_content,
                'points': 1
            }
            problem.tests.append(vyg.TestCase(json_dict, False))

    @staticmethod
    def load_test(file_path: str) -> str:
        """ Load the contents of a file, or return an empty string if the file does not exist """
        if os.path.isfile(file_path):
            with open(file_path, 'r', encoding='utf8') as file:
                return file.read()
        return ''
