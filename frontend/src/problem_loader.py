""" Loads programming problems from the folders of course repositories """
import glob
import json
import logging
import os
import re
import subprocess
import threading

import markdown

import vyg

# Maximum seconds that asciidoctor may spend converting a problem statement to HTML
ASCIIDOCTOR_TIMEOUT = 30

# Largest file of a problem folder that is loaded, in bytes. Statements, initial codes, and test
# cases are kept in memory and sent to clients and backends, so huge files are skipped
MAX_FILE_SIZE = 16 * 2**20

logger = logging.getLogger(__name__)

# Problems are shared by the threads of a gunicorn worker. The lock prevents two threads from
# loading the same problem at once, duplicating its statement or exposing it half loaded. A single
# lock is enough because each problem is loaded only once per worker process
_load_lock = threading.Lock()

class ProblemLoader:
    """ Fills a vyg.Problem with the files stored in its folder: the vygoj.json configuration,
    the statement in HTML, Asciidoc, or Markdown, the initial code, and the test cases """

    @staticmethod
    def load_folder(problem: vyg.Problem):
        """ Load problem data from the folder where it is stored """
        if problem.folder_loaded is False:
            with _load_lock:
                # Another thread may have loaded the problem while this one waited for the lock
                if problem.folder_loaded is False:
                    path = problem.get_path()
                    if ProblemLoader.is_inside_course(problem, path):
                        ProblemLoader.load_json(problem, path)
                        ProblemLoader.load_problem_statement(problem, path)
                        ProblemLoader.load_initial_code(problem, path)
                        ProblemLoader.load_test_cases(problem, path)
                    else:
                        logger.warning('problem %s: folder out of its course repo', problem.name)
                    # Mark it loaded at the end, so other threads never use a partial problem
                    problem.folder_loaded = True

    @staticmethod
    def is_inside_course(problem: vyg.Problem, path: str) -> bool:
        """ True if the path is inside the repository folder of the problem's course. Course repos
        are untrusted: a folder such as '../..' in vygoj.json, or a symbolic link committed to the
        repo, could make the statement or the test cases show any readable file of the server
        (e.g. config.py with the SECRET_KEY). Symbolic links are resolved before comparing """
        root = os.path.realpath(problem.get_course().folder)
        return os.path.commonpath([root, os.path.realpath(path)]) == root

    @staticmethod
    def is_loadable(problem: vyg.Problem, filename: str) -> bool:
        """ True if the file is a regular file inside the course repo, and it is not too large """
        if not os.path.isfile(filename) or not ProblemLoader.is_inside_course(problem, filename):
            logger.warning('problem %s: skipped %s, out of its course repo', problem.name,
                os.path.basename(filename))
            return False
        if os.path.getsize(filename) > MAX_FILE_SIZE:
            logger.warning('problem %s: skipped %s, larger than %d bytes', problem.name,
                os.path.basename(filename), MAX_FILE_SIZE)
            return False
        return True

    @staticmethod
    def read_file(problem: vyg.Problem, filename: str) -> str:
        """ Return the text of a file of the problem folder, or an empty string if it cannot be
        loaded safely """
        if not ProblemLoader.is_loadable(problem, filename):
            return ''
        with open(filename, encoding='utf8') as file:
            return file.read()

    @staticmethod
    def load_json(problem: vyg.Problem, path: str):
        """ Load the JSON file, if any, with configuration for this problem """
        path = os.path.join(path, 'vygoj.json')
        if os.path.isfile(path):
            text = ProblemLoader.read_file(problem, path)
            if text:
                # Files are written by hand, so their values are not base64 encoded
                problem.merge(json.loads(text), False)

    @staticmethod
    def load_problem_statement(problem: vyg.Problem, path: str):
        """ Load the problem statement from Asciidoc, Markdown, or HTML file """
        if not problem.statement:
            extensions = ['html', 'adoc', 'md']
            for extension in extensions:
                files = glob.glob(os.path.join(path, f'*.{extension}'))
                for filename in files:
                    if extension == 'html':
                        problem.statement += ProblemLoader.read_file(problem, filename)
                    elif extension == 'adoc':
                        if ProblemLoader.is_loadable(problem, filename):
                            problem.statement += ProblemLoader.convert_asciidoc(filename)
                    elif extension == 'md':
                        problem.statement += markdown.markdown(
                            ProblemLoader.read_file(problem, filename))

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
                # Extract file extension without dot
                ext = os.path.splitext(filename)[1][1:]
                # If extension is recognized as a programming language
                if ext in vyg.LANGUAGE_EXTENSIONS:
                    language = vyg.LANGUAGE_EXTENSIONS.get(ext)
                    initial_code = ProblemLoader.read_file(problem, filename)
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
            input_content = ProblemLoader.read_file(problem, input_file)
            output_content = ProblemLoader.read_file(problem, output_file)
            args_content = ProblemLoader.load_test(problem,
                os.path.join(path, f'tests/args{num}.txt'))
            error_content = ProblemLoader.load_test(problem,
                os.path.join(path, f'tests/error{num}.txt'))
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
    def load_test(problem: vyg.Problem, file_path: str) -> str:
        """ Load the contents of a file, or return an empty string if the file does not exist """
        return ProblemLoader.read_file(problem, file_path) if os.path.exists(file_path) else ''
