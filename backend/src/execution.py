""" Compile and run a student's solution against the test cases of a problem in a container """
import dataclasses
import io
import logging
import math
import re
import shlex
import tarfile
import threading
import time
import docker
import vyg

logger = logging.getLogger(__name__)

# Image built by the Makefile inside the engine/ subfolder (IMAGE=debian-dev). Change both together
IMAGE = 'debian-dev:latest'
# Unprivileged user of the engine image and its numeric id (useradd -u in engine/Dockerfile)
STUDENT_USER = 'student'
STUDENT_UID = 1000
# Working directory of the student inside the container, where solution and inputs are copied
WORKDIR = '/home/student'
# The frontend sends the effective time limits in the problem (maxDuration of each test case, and
# maxTotalDuration), chosen by its administrator and professors. The backend clamps them to these
# ranges, which must contain the ranges of the frontends (ABS_*_DURATION in their config.py)
# MIN_DURATION is the smallest maxDuration: a limit near 0 s, but never 0, because `timeout 0` does
# not limit the command. minDuration may be 0
MIN_DURATION = 1e-9 # seconds
MAX_DURATION = 30 # seconds
MAX_TOTAL_DURATION = 120 # seconds
# Limits used when the problem does not send them
DEFAULT_DURATION = 2 # seconds
DEFAULT_TOTAL_DURATION = 30 # seconds
# Time limits for compiling, linting, and reading statistics in the container
COMPILE_TIMEOUT = 2 # seconds
JAVA_COMPILE_TIMEOUT = 10 # seconds
# alecci starts Python and LLVM, and then links with clang
ALECCI_COMPILE_TIMEOUT = 5 # seconds
LINT_TIMEOUT = 2 # seconds
STATS_TIMEOUT = 2 # seconds
# Seconds that the gdb run that counts the threads may last beyond the limit of the test case
THREAD_PROOF_EXTRA = 2 # seconds
# Seconds between the SIGTERM and the SIGKILL sent by `timeout` to a command that does not end
KILL_GRACE = 1 # seconds
# Extra seconds a command may last after its timeout before the backend kills all student processes
# in the container. Background processes may keep the output pipe open after `timeout` ends
HANG_GRACE = 3 # seconds
# Test cases do not start after the maxTotalDuration of the submission, and the running one is cut
# at that time. The container is killed if the submission lasts this many seconds more, enough to
# stop the last commands. It must be shorter than BACKEND_GRACE in frontend/src/limits.py
DEADLINE_GRACE = 20 # seconds
# Read timeout for each call to the Docker API, longer than any command run in the container
DOCKER_TIMEOUT = MAX_DURATION + THREAD_PROOF_EXTRA + KILL_GRACE + HANG_GRACE + 10 # seconds

# Bounds for the data received from the frontend. Each value is untrusted
MAX_CODE_BYTES = 256 * 1024
MAX_TESTS = 100
MAX_TEST_INPUT_BYTES = 4 * 1024 * 1024
MAX_ARGS_LENGTH = 4096
# Bytes kept from the stdout and from the stderr of each command, the rest is discarded. It also
# bounds the maxOutputSize of the problem: the bytes of the stdout and stderr of each visible test
# case, and of the compiler output, sent to the frontend. Outputs are compared before truncating
MAX_OUTPUT_BYTES = 1024 * 1024
# Appended to a truncated output, so students know that their program wrote more
TRUNCATED_MARK = '\n(truncated)'

# Resource limits of the container. Threads count as processes in pids_limit
CONTAINER_MEMORY = '512m'
CONTAINER_PIDS = 512
CONTAINER_CPUS = 2
# Maximum size of any file written in the container (ulimit -f), and of open files (ulimit -n)
CONTAINER_FILE_BYTES = 64 * 1024 * 1024
CONTAINER_OPEN_FILES = 4096
# Size of the /tmp file system, kept in memory and counted in CONTAINER_MEMORY
CONTAINER_TMP_SIZE = '64m'
# Label that identifies the containers created by the backend, e.g. to remove leaked ones with
# docker rm -f $(docker ps -aq --filter label=vygoj=engine)
CONTAINER_LABELS = {'vygoj': 'engine'}
# Exit status of the backend when Docker is not available. gunicorn stops on 4 (its APP_LOAD_ERROR)
# instead of restarting the workers forever, and the Flask reloader would restart on 3
DOCKER_UNAVAILABLE_STATUS = 4

# Docker is a server, we need a client to use it. from_env() creates a client that connects to the
# server using the default socket or configuration in your environment variables. from_env() gives
# you access to the same client when you run the `docker` command in your shell. The timeout
# bounds each API call, so a stuck container cannot block a backend worker forever.
# Doc: https://docker-py.readthedocs.io/en/stable/client.html
try:
    docker_client = docker.from_env(timeout=DOCKER_TIMEOUT)
except docker.errors.DockerException as docker_error:
    # Without Docker no solution can run, so the backend stops with a message instead of a
    # traceback
    logger.critical('Docker server not available: %s', docker_error)
    raise SystemExit(DOCKER_UNAVAILABLE_STATUS) from None

# Compiler options of the sanitizers that a problem may ask for in gcc, g++, and clang. Only these
# tools are accepted, any other word in problem.tools is ignored
COMPILE_TOOLS = {
    'asan': ['-fsanitize=address', '-fmessage-length=80'],
    'tsan': ['-fsanitize=thread', '-fmessage-length=80'],
    'ubsan': ['-fsanitize=undefined', '-fmessage-length=80'],
}
# The alecci compiler enables ThreadSanitizer unless it gets --no-tsan or --use-asan. TSan creates a
# thread of its own, which gdb would count, so it is enabled only when the problem asks for it
ALECCI_TOOLS = {
    'asan': ['--use-asan'],
    'tsan': [],
}
# Status lines that alecci writes on every compilation. Without them, a successful compilation has
# no output, as with the other compilers, and the frontend does not show an empty diagnostic
# TODO(jhc): remove when alecci has a quiet mode (citic/alecci#2)
ALECCI_STATUS = re.compile(r'^(?:Compiling with [\w ]+ support|'
        r'Compilation successful! Executable created: \S+)(?:\n|$)', re.MULTILINE)

@dataclasses.dataclass(frozen=True)
class LanguageDefault:
    """ How the backend compiles, runs, and lints the solutions in a programming language """
    # Fixed name of the source file in WORKDIR. A public Java class must be in a file of its name
    source_file: str
    # Compiler command and its options, before the source file. Interpreted languages only check
    # the syntax, so students get their syntax errors as compiler errors
    compiler: str
    # Arguments after the source file. The linker resolves symbols in order, so libraries must
    # follow the source files
    compiler_suffix: str
    # Seconds to compile. The Java compiler runs in a JVM, which starts slower than gcc
    compile_timeout: float
    # File that the compiler must create in WORKDIR, or '' if it creates none. alecci exits with
    # status 0 even when clang fails to link, so the missing file tells the failure
    compiled_file: str
    # Command that runs the compiled solution, before the arguments of the test case
    run_command: str
    # Filter of cpplint, or '' if the language has no linter
    linting_options: str
    # True if the solution is a native executable, where the sanitizers and valgrind work. They do
    # not apply to programs run by an interpreter or a virtual machine
    native: bool = True
    # True if gdb counts the threads created by the solution. The JVM creates threads of its own
    count_threads: bool = True
    # Compiler options of each sanitizer that the problem may ask for (COMPILE_TOOLS)
    compile_tools: dict = dataclasses.field(default_factory=lambda: COMPILE_TOOLS)
    # Compiler options when the problem asks for none of compile_tools, e.g. to disable a sanitizer
    # that the compiler enables by default
    no_tools_options: str = ''
    # Lines that the compiler writes even when it succeeds, removed from its output, or None
    status_lines: re.Pattern = None

COMMON_LINT = '-build/header_guard,-build/include_subdir,-runtime/int'
# TODO(jhc): override default compiler options with problem.compilerOptionsFor[lang]
# -fno-diagnostics-color
LANGUAGE_DEFAULTS = {
    'C': LanguageDefault('solution.c',
        'gcc -g -Wall -Wextra -std=gnu17 -pthread', '-o solution -lm', COMPILE_TIMEOUT,
        'solution', './solution', f'{COMMON_LINT},-readability/casting'),
    'C++': LanguageDefault('solution.cpp',
        'g++ -g -Wall -Wextra -std=gnu++20 -pthread', '-o solution -lm', COMPILE_TIMEOUT,
        'solution', './solution', f'{COMMON_LINT},-build/c++11,-runtime/references'),
    # The main class of the solution must be the public class Solution (the default code of the
    # frontend). -ea enables assertions, as they are in C without NDEBUG
    # TODO(jhc): lint Java solutions with checkstyle, and count their threads
    'Java': LanguageDefault('Solution.java',
        'javac -g -encoding UTF-8 -Xlint:all -d .', '', JAVA_COMPILE_TIMEOUT, 'Solution.class',
        'java -ea -cp . Solution', '', native=False, count_threads=False),
    # py_compile reports syntax errors before running the test cases. The threads of Python are
    # threads of the operating system, so gdb counts them on the interpreter
    # TODO(jhc): lint Python solutions, e.g. with pylint or pycodestyle
    'Python': LanguageDefault('solution.py',
        'python3 -m py_compile', '', COMPILE_TIMEOUT, '', 'python3 solution.py', '',
        native=False),
    # alecci translates the solution to LLVM IR and links it with clang into a native executable
    'Alecci': LanguageDefault('solution.ale',
        'alecci', '-o solution', ALECCI_COMPILE_TIMEOUT, 'solution', './solution', '',
        compile_tools=ALECCI_TOOLS, no_tools_options='--no-tsan', status_lines=ALECCI_STATUS),
}

# Run prefixes of the tools that a problem may ask for. Only these tools are accepted
RUN_TOOLS = {
    'memcheck': ['valgrind', '-q', '-s', '--sigill-diagnostics=yes', '--leak-check=full'],
    'helgrind': ['valgrind', '-q', '-s', '--sigill-diagnostics=yes', '--tool=helgrind'],
}

# Runs "${@:2}" with its stdin read from the file "$1". Arguments are passed as positional
# parameters, never pasted into the script, so their content cannot inject shell commands
STDIN_SCRIPT = 'exec "${@:2}" < "$1"'
# Exit status of `timeout` when the command lasted longer than the limit, and when it also had to
# kill the command with SIGKILL because it ignored SIGTERM (128 + 9)
TIMEOUT_EXIT_CODE = 124
KILLED_EXIT_CODE = 137
# File where /usr/bin/time writes the statistics of a test case run
TIME_FILE = 'vyg_time.txt'
# Lines of `/usr/bin/time -v` with the statistics sent to the frontend. The elapsed time is written
# as h:mm:ss or m:ss with decimals, e.g: 0:01.25
WALL_TIME_PATTERN = re.compile(
        r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (?:(\d+):)?(\d+):(\d+(?:\.\d+)?)')
USER_TIME_PATTERN = re.compile(r'User time \(seconds\): (\d+(?:\.\d+)?)')
SYSTEM_TIME_PATTERN = re.compile(r'System time \(seconds\): (\d+(?:\.\d+)?)')
MEMORY_PATTERN = re.compile(r'Maximum resident set size \(kbytes\): (\d+)')

class InvalidSubmission(ValueError):
    """ The problem or solution received from the frontend is malformed or exceeds a limit. The
        message is safe to be returned to the frontend """

class FailedSolution(Exception):
    """ An object of this class is launched immediately we know student code failed in order
        to stop the execution of the test case. The message is used internally, not reported to
        user. The Execution.report object carries the status and its message """
    def __init__(self, result:vyg.ExecutionResult, status:vyg.Status, message:str):
        """ Constructor. result: reference to the result object that will be modified.
            status: the status to be assigned in the result object. The message to be
            assigned to the result object. No other exceptions should be launched after this
            one, otherwise the result object will reflect the last one """
        super().__init__(message)
        self.message = message # needed?
        result.status = status
        result.message = vyg.append(result.message, message, '\n')

def bounded_number(value, default:float, low:float, high:float) -> float:
    """ Return value clamped to [low, high], or default if value is not a finite number """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return default
    return min(max(value, low), high)

def append_bounded(buffer:bytearray, chunk:bytes):
    """ Append chunk to buffer without exceeding MAX_OUTPUT_BYTES """
    if chunk and len(buffer) < MAX_OUTPUT_BYTES:
        buffer += chunk[:MAX_OUTPUT_BYTES - len(buffer)]

def truncate_output(text:str, limit:int) -> str:
    """ Return the text cut to limit bytes of UTF-8 followed by TRUNCATED_MARK, or the text if it
        is not longer """
    data = text.encode('utf-8')
    if len(data) <= limit:
        return text
    # A character cut in the middle of its bytes is dropped
    return data[:limit].decode('utf-8', errors='ignore') + TRUNCATED_MARK

def decode_output(buffer:bytearray) -> str:
    """ Decode the output of a program. Student programs may print invalid UTF-8 """
    return buffer.decode('utf-8', errors='replace').strip()

class Execution:
    """Controls an execution of the user solution against only one or several test cases. Input:

    - The problem object containing test cases, compiler options
    - The index of the test case to be evaluated from the problem, or None for all tests
    - User solution
    - Extra proofs (indicated in problem object), eg: minimum number of threads

    Output is an ExecutionResult object that contains:

    - The standard output generated by user solution
    - A verdict of the test case: passed, wrong answer, timeout...
    - The standard error output
    - Results of static and dynamic code proofs if asked in problem object
    """
    def __init__(self, problem_json:dict, solution_json:dict):
        """ Constructor. The problem carries the limits of the run. Raises InvalidSubmission if the
            problem or the solution is malformed """
        try:
            # The problem to be solved, sent by VygOJ frontend
            self.problem = vyg.Problem(problem_json, None)
            # The solution submitted by user, sent by VygOJ frontend as a message
            self.solution = vyg.Message(solution_json)
        except (ValueError, TypeError, AttributeError) as error:
            # Invalid JSON types in the fields, e.g. a language that is not a text
            raise InvalidSubmission('Malformed problem or solution') from error
        # The programming language used by user to write the code solution
        # Language is sent by client, but if omitted, we suppose 'C'
        self.language = self.solution.language or 'C'
        # Extra tools asked by the problem, e.g: ['asan', 'lint']
        self.tools = self.problem.tools.split() if isinstance(self.problem.tools, str) else []
        self._validate()
        # How to compile, run, and lint the solution
        self.flags = LANGUAGE_DEFAULTS[self.language]
        # The filename of the student's solution, e.: 'solution.c'
        self.source_file = self.flags.source_file
        # Sanitizers and valgrind only work on native executables
        if not self.flags.native:
            self.tools = [tool for tool in self.tools
                    if tool not in COMPILE_TOOLS and tool not in RUN_TOOLS]
        # Docker container to compiler and run test cases
        self.container:docker.models.containers.Container = None
        # Kills the container when the submission lasts DEADLINE_GRACE seconds after its deadline
        self.watchdog:threading.Timer = None
        # True if the watchdog killed the container
        self.deadline_expired = False
        # The execution result of each test case and a brief to be returned to frontend
        self.result = vyg.ExecutionResult({})
        # Bytes of the outputs sent back for each visible test case. The frontend omits 0
        self.output_limit = int(bounded_number(self.problem.maxOutputSize, 0, 0,
                MAX_OUTPUT_BYTES))
        # The time.monotonic() when the time of the whole submission expires
        self.deadline = math.inf

    def _validate(self):
        """ Check types and sizes of the untrusted data used to run the solution """
        if self.language not in LANGUAGE_DEFAULTS:
            raise InvalidSubmission(f'Not supported language by backend: {self.language}')
        if not isinstance(self.solution.code, str) or not self.solution.code:
            raise InvalidSubmission('Missing source code')
        if len(self.solution.code.encode('utf-8')) > MAX_CODE_BYTES:
            raise InvalidSubmission(f'Source code exceeds {MAX_CODE_BYTES} bytes')
        if not isinstance(self.problem.languages, list):
            raise InvalidSubmission('Invalid problem languages')
        if not Execution._is_list_of_texts(self.problem.mustContain):
            raise InvalidSubmission('Invalid problem mustContain')
        if not isinstance(self.problem.tools, str):
            raise InvalidSubmission('Invalid problem tools')
        if len(self.problem.tests) > MAX_TESTS:
            raise InvalidSubmission(f'Problem has more than {MAX_TESTS} test cases')
        for test in self.problem.tests:
            self._validate_test_case(test)

    @staticmethod
    def _is_list_of_texts(value) -> bool:
        """ True if value is a text, or a list of texts. Texts arrive as they are in JSON, so their
            types must be checked """
        return isinstance(value, str) or (isinstance(value, list)
                and all(isinstance(item, str) for item in value))

    @staticmethod
    def _validate_test_case(test:vyg.TestCase):
        """ Check types and sizes of the fields of a test case """
        for text in (test.stdin, test.stdout, test.stderr, test.args):
            if not isinstance(text, str):
                raise InvalidSubmission('Invalid test case')
        if len(test.stdin.encode('utf-8')) > MAX_TEST_INPUT_BYTES:
            raise InvalidSubmission(f'Test case input exceeds {MAX_TEST_INPUT_BYTES} bytes')
        if len(test.args) > MAX_ARGS_LENGTH:
            raise InvalidSubmission('Test case arguments are too long')
        # Raises InvalidSubmission if the arguments cannot be split, e.g: unbalanced quotes
        Execution._build_args(test)
        if bounded_number(test.points, None, -math.inf, math.inf) is None:
            raise InvalidSubmission('Test case points must be a number')
        if not isinstance(test.custom, bool):
            raise InvalidSubmission('Invalid test case')

    def execute(self) -> str:
        """ Execute the solution against all test cases. Return the result as a JSON string """
        self.deadline = time.monotonic() + self._total_limit()
        try:
            # TODO(jhc): log the run in database
            # Run static analysis checks before compiling and run the test cases
            self._check_static_analysis()
            # Do not create a container for a language that the problem does not allow
            self._check_language()
            # Do not run code directly on the OS, isolate student code into a Docker container
            self._create_container()
            # Copy the student solution and test cases to the container
            self._copy_files()
            # If the solution is in a language that should be compiled, compile it
            self._compile()
            # Run all test cases. TODO(jhc): test in parallel to finish sooner
            for index0, test_case in enumerate(self.problem.tests):
                self._check_deadline(len(self.problem.tests) - index0)
                self._run_test_case(index0, test_case)
            # Run after test case proofs, e.g: linting
            self._check_deadline(0)
            self._after_run_proofs()
            # TODO(jhc): self.build_message() for the entire execution result
        except FailedSolution:
            # Student's code does not solve the problem, report to frontend
            pass
        except Exception: # pylint: disable=broad-exception-caught
            # Errors are logged with details, but users receive only a generic message, because
            # details may reveal host paths or configuration
            # TODO(jhc): Communicate errors to admins, professors, or students
            if self.deadline_expired:
                self.result.status = vyg.Status.TIMEOUT
                self.result.message = vyg.append(self.result.message,
                        'Submission exceeded the total time limit', '\n')
            else:
                logger.exception('Error running a submission')
                self.result.status = vyg.Status.INTERNAL_ERROR
                self.result.message = vyg.append(self.result.message,
                        'Internal error while running the solution', '\n')
        finally:
            # Kill and remove the container even on errors, so they do not pile up on the host
            self._remove_container()
        # Execution finished, encode the result to JSON and send it to frontend
        return vyg.to_json(self.result)

    def _total_limit(self) -> float:
        """ Return the seconds for the whole submission """
        return bounded_number(self.problem.maxTotalDuration, DEFAULT_TOTAL_DURATION,
                MIN_DURATION, MAX_TOTAL_DURATION)

    def _time_left(self, limit:float) -> float:
        """ Return the limit in seconds for a command, cut to the time left until the deadline """
        # timeout needs a positive limit. A command started at the deadline ends at once
        return max(min(limit, self.deadline - time.monotonic()), MIN_DURATION)

    def _check_deadline(self, pending:int):
        """ Stop the submission if its total time is over. pending: test cases not run yet """
        if time.monotonic() < self.deadline:
            return
        message = f'Total time limit exceeded ({self._total_limit():g} s)'
        if pending:
            message += f': {pending} test case{"s" if pending > 1 else ""} not run'
        raise FailedSolution(self.result, vyg.Status.TIMEOUT, message)

    def _check_static_analysis(self):
        """ If professor asked to do static analysis, eg: check some words are in code"""
        if not self.problem.mustContain:
            return
        code = self.solution.code or ''
        # A single text is one token, not a list of characters
        tokens = self.problem.mustContain
        for token in [tokens] if isinstance(tokens, str) else tokens:
            if not token in code:
                # The token is missing, launch an exception to stop the execution
                raise FailedSolution(self.result, vyg.Status.WRONG, f'Missing {token} in solution')

    def _check_language(self):
        """ Stop if the language of the solution is not allowed by the problem """
        if self.language not in self.problem.languages:
            message = f'Not allowed language for problem: {self.language}'
            raise FailedSolution(self.result, vyg.Status.COMPILER_ERROR, message)

    def _create_container(self):
        """ Create a Docker container and set it to self.container reference """
        # Create a container and run it but do not wait until it finishes to run the command, the
        # detach=True argument returns immediately. We run 'sleep infinity' to be sure the
        # command will last forever and keep the container running, but not consuming resources.
        # We will use the container to compile the student solution and run against all the test
        # cases defined in the Problem. Therefore, we need to run several other commands in the
        # container. This may be not the best approach, but it provides a good balance between
        # security and efficiency. After the student solution is run against all test cases, the
        # container is removed by the _remove_container() method. Many of provided arguments are
        # used to constraint the container in order to run unsafe code coming from users. The
        # sanitizers, gdb, and valgrind work with these restrictions and the default seccomp
        # profile.
        # Doc: https://docker-py.readthedocs.io/en/stable/containers.html
        # TODO(jhc): Run for the amount of seconds indicated by the problem or default for language
        # TODO(jhc): Limit memory from the Problem configuration
        # TODO(jhc): Make the root file system read-only. put_archive() cannot write to a tmpfs, so
        # the files would need another way in, e.g. a size-limited volume
        self.container = docker_client.containers.run(
            image=IMAGE,
            # Do not wait until the command finishes, just return the reference to the container
            detach=True,
            # A dummy command to keep the container alive. As PID 1 it ignores signals sent from
            # inside the container, so `kill -9 -1` removes student processes but not the container
            command=['sleep', 'infinity'],
            # Student solutions do not have root privileges. Never run with privileged=True, it
            # gives the container full access to the devices and kernel of the host
            user=STUDENT_USER,
            working_dir=WORKDIR,
            # Drop all Linux capabilities, and forbid regaining them through setuid binaries
            cap_drop=['ALL'],
            security_opt=['no-new-privileges:true'],
            # TODO(jhc): Support the distributed programming paradigm
            network_disabled=True,
            network_mode='none',
            # Bound memory (without swap), processes and threads (fork bombs), and CPU usage
            mem_limit=CONTAINER_MEMORY,
            memswap_limit=CONTAINER_MEMORY,
            pids_limit=CONTAINER_PIDS,
            nano_cpus=int(CONTAINER_CPUS * 1e9),
            # Bound file sizes and open files. Do not write core dumps
            ulimits=[
                docker.types.Ulimit(name='fsize', soft=CONTAINER_FILE_BYTES,
                        hard=CONTAINER_FILE_BYTES),
                docker.types.Ulimit(name='nofile', soft=CONTAINER_OPEN_FILES,
                        hard=CONTAINER_OPEN_FILES),
                docker.types.Ulimit(name='core', soft=0, hard=0),
            ],
            # /tmp lives in memory and is bounded, instead of growing in the host disk
            tmpfs={'/tmp': f'size={CONTAINER_TMP_SIZE}'},
            # Enable to run linux-perf without root privileges in current session
            #sysctls={'kernel.perf_event_paranoid': 1},
            labels=CONTAINER_LABELS)
        # Bound the total time of the submission, whatever the student code does
        self.watchdog = threading.Timer(self.deadline - time.monotonic() + DEADLINE_GRACE,
                self._expire_deadline)
        self.watchdog.daemon = True
        self.watchdog.start()

    def _expire_deadline(self):
        """ Called by the watchdog when the submission lasts too long: kill the container """
        self.deadline_expired = True
        logger.warning('Submission exceeded %s seconds, killing its container',
                self._total_limit() + DEADLINE_GRACE)
        try:
            self.container.kill()
        except docker.errors.DockerException:
            logger.exception('Could not kill the container')

    def _remove_container(self):
        """ Kill the container if it is running and destroy it """
        if self.watchdog:
            self.watchdog.cancel()
        if self.container:
            try:
                # Force kills the container immediately, instead of waiting the stop timeout
                self.container.remove(force=True)
            except docker.errors.DockerException:
                logger.exception('Could not remove container %s', self.container.id)
            self.container = None

    def _copy_files(self):
        """ Copy the student solution and test cases to the container """
        # Docker copies files to a container from a tar file. It is built in memory with fixed file
        # names, owned by the student, so no chown is needed in the container
        mem_tar = io.BytesIO()
        with tarfile.open(fileobj=mem_tar, mode='w') as tar_file:
            Execution._add_to_tar(tar_file, self.source_file, self.solution.code)
            # Copy input files of all test cases
            for index0, test in enumerate(self.problem.tests):
                Execution._add_to_tar(tar_file, Execution._input_file(index0), test.stdin)
        # Extract the tar file in the container
        self.container.put_archive(path=WORKDIR, data=mem_tar.getvalue())

    @staticmethod
    def _add_to_tar(tar_file:tarfile.TarFile, name:str, text:str):
        """ Add a regular file with the given name and text to the tar file """
        data = text.encode('utf-8')
        info = tarfile.TarInfo(name)
        info.size = len(data)
        info.mode = 0o644
        info.uid = info.gid = STUDENT_UID
        tar_file.addfile(info, io.BytesIO(data))

    @staticmethod
    def _input_file(index0:int) -> str:
        """ Name of the file with the stdin of the test case at index0 """
        return f'input{index0 + 1:03}.txt'

    def _run_in_container(self, argv:list, timeout:float, stdin_file:str = None,
            prefix:list = None):
        """
        Executes a command in the Docker container as the student. Args:
        - argv: command and its arguments as a list. It is never interpreted by a shell
        - timeout: maximum allowed duration in seconds (can contain decimals)
        - stdin_file: optional file in the container to be used as stdin
        - prefix: optional command that wraps the timed command, e.g: /usr/bin/time
        Returns a tuple: (stdout, stderr, exit_code). Only the first MAX_OUTPUT_BYTES of stdout and
        stderr are kept. exit_code is None if Docker could not report it
        """
        assert isinstance(argv, list) and timeout > 0
        # timeout sends SIGTERM when time is over, and SIGKILL later if the program ignores it. Nine
        # decimals (its resolution, nanoseconds) keep MIN_DURATION above 0, which means no limit
        command = (prefix or []) + ['timeout', '-k', str(KILL_GRACE), f'{timeout:.9f}'] + argv
        if stdin_file:
            command = ['bash', '-c', STDIN_SCRIPT, 'bash', stdin_file] + command
        logger.debug('Running in container: %s', command)
        # If background processes keep the output open after `timeout` ends, kill them
        hang_guard = threading.Timer(timeout + KILL_GRACE + HANG_GRACE,
                self._kill_student_processes)
        hang_guard.daemon = True
        # The low-level API streams the output, so it can be bounded, and still reports the exit
        # code. demux separates stdout and stderr chunks
        api = docker_client.api
        exec_id = api.exec_create(self.container.id, command, user=STUDENT_USER,
                workdir=WORKDIR)['Id']
        stdout, stderr = bytearray(), bytearray()
        hang_guard.start()
        try:
            for out_chunk, err_chunk in api.exec_start(exec_id, stream=True, demux=True):
                # Output beyond the limit is read and discarded, so the program is not blocked
                # writing and ends by itself or by its timeout
                append_bounded(stdout, out_chunk)
                append_bounded(stderr, err_chunk)
        finally:
            hang_guard.cancel()
        exit_code = api.exec_inspect(exec_id).get('ExitCode')
        return decode_output(stdout), decode_output(stderr), exit_code

    def _kill_student_processes(self):
        """ Kill every student process in the container but PID 1, e.g. background processes left
            by a test case, which could interfere with the following ones """
        try:
            # kill -1 signals all processes of the user, except PID 1 and the caller
            self.container.exec_run(['bash', '-c', 'kill -9 -1'], user=STUDENT_USER)
        except docker.errors.DockerException:
            logger.exception('Could not kill student processes')

    def _compile(self):
        """ Compile the solution if its language is compiled, e.g: C, C++, Java, or check its
            syntax if it is interpreted, e.g: Python """
        # Prepare compilation command. Options are defined by the backend, never by users
        cmd = (self._build_compiler_options() + [self.source_file]
                + self.flags.compiler_suffix.split())
        # Run the compilation command, if it fails, report to frontend
        stdout, stderr, exit_code = self._run_in_container(cmd, self.flags.compile_timeout)
        output = stdout + stderr
        if self.flags.status_lines:
            output = self.flags.status_lines.sub('', output)
        self.result.compileOutput = truncate_output(output, self.output_limit)
        if exit_code != 0 or not self._compiled_file_exists():
            # Student code produced compiling errors. They are in compileOutput, the client shows
            # it after the message
            raise FailedSolution(self.result, vyg.Status.COMPILER_ERROR, 'Compilation failed')
        # TODO(jhc): Create a snapshot (commit/image) of the container in order to restore it
        # after running the student solution against each test case. Disabled until efficiency
        # could be measured
        # self.container.commit(repository='vyg', tag='after_compile', message='')

    def _compiled_file_exists(self) -> bool:
        """ True if the compiler created the file of the language, or if it creates none """
        if not self.flags.compiled_file:
            return True
        # The file name is fixed by the backend, not by users
        _, _, exit_code = self._run_in_container(['test', '-f', self.flags.compiled_file],
                STATS_TIMEOUT)
        return exit_code == 0

    def _build_compiler_options(self) -> list:
        """ Build the compiler command and its options for the language used by student """
        compiler_options = self.flags.compiler.split()
        # Get the compiler options from the problem object, if not defined, use the default ones
        # compiler_options = self.problem.compilerOptionsFor.get(self.language,
        #         flags.compiler_options)
        # If professor asked to use some extra tools, add them to the compiler options. Tools that
        # the compiler does not support are ignored, e.g. ubsan in alecci
        tools = [tool for tool in self.tools if tool in self.flags.compile_tools]
        for tool in tools:
            compiler_options += self.flags.compile_tools[tool]
        if not tools:
            compiler_options += self.flags.no_tools_options.split()
        return compiler_options

    def _run_test_case(self, index0:int, test_case:vyg.TestCase):
        """ Runs a test case of the problem given in the constructor """
        # Get the test case to run
        assert 0 <= index0 < len(self.problem.tests)
        input_file = Execution._input_file(index0)
        expected_output = test_case.stdout
        expected_error = test_case.stderr
        wall_time_limit = self._wall_time_limit(test_case)
        # The last test case before the deadline may have less time than its limit
        run_limit = self._time_left(wall_time_limit)
        # Prepare run command: /usr/bin/time -v -o vyg_time.txt timeout 2 ./solution < input.txt
        cmd = (self._build_run_prefix() + self.flags.run_command.split()
                + self._build_args(test_case))
        time_prefix = ['/usr/bin/time', '-v', '-o', TIME_FILE]
        test_result = vyg.TestCaseResult({})
        test_result.stdout, test_result.stderr, test_result.exitCode = (
                self._run_in_container(cmd, run_limit, input_file, time_prefix))
        # Background processes must not interfere with the statistics or the next test cases
        self._kill_student_processes()
        # Fetch the statistics generated by the /usr/bin/time command
        self._fetch_stats(test_result)
        # Compare standard output and error against expected ones in test case. The outputs of a
        # test case written by the user are not compared, they are only shown
        if not test_case.custom:
            self._compare_output('stdout', expected_output, test_result)
            self._compare_output('stderr', expected_error, test_result)
        if Execution._timed_out(test_result, run_limit):
            # The solution was killed by timeout
            test_result.status = vyg.Status.TIMEOUT
            self.result.status = vyg.Status.TIMEOUT
            test_result.message = ('Time limit exceeded' if run_limit >= wall_time_limit
                    else 'Total time limit exceeded')
        elif (test_result.exitCode != 0 or not test_case.custom and not expected_error.strip()
                and test_result.stderr and 'ERROR SUMMARY: 0 errors' not in test_result.stderr):
            # If the exit code is not 0, or the solution wrote to stderr when the test case did not
            # expect it (e.g. a sanitizer report), mark the test case as failed. An expected
            # stderr was already compared by _compare_output(), and the stderr of a test case
            # written by the user is only shown
            test_result.status = vyg.Status.RUNTIME_ERROR
            self.result.status = vyg.Status.RUNTIME_ERROR
            test_result.message = (f'Exit code {test_result.exitCode}' if test_result.exitCode
                    else 'Unexpected standard error output')
            #self.result.message = vyg.append(self.result.message, test_result.message)
        # Check solution is in time range
        self._check_time_range(test_case, test_result)
        # If there further proofs, execute them. Each test case is checked on its own, so later
        # test cases also report their threads after a failed one
        # TODO(jhc): count the threads of Java solutions, e.g. with jstack
        if (test_result.status == vyg.Status.PASSED and self.problem.has_proofs()
                and self.flags.count_threads):
            self._run_thread_count_proof(index0, input_file, test_result)
        # Store the result in the array to be returned to the client, without outputs that are too
        # large or hidden
        self._bound_outputs(test_case, test_result)
        self.result.results.append(test_result)
        self.result.totalPoints += test_case.points
        # If the test was passed
        if test_result.status == vyg.Status.PASSED:
            # Increase the count of passed test cases and accumulate the points
            self.result.passedTestCount += 1
            self.result.points += test_case.points
        logger.debug('Test case %d: %s', index0 + 1, test_result.status)

    def _wall_time_limit(self, test_case:vyg.TestCase) -> float:
        """ Return the seconds that the solution may run the test case """
        return bounded_number(test_case.maxDuration or self.problem.maxDuration,
                DEFAULT_DURATION, MIN_DURATION, MAX_DURATION)

    def _bound_outputs(self, test_case:vyg.TestCase, test_result:vyg.TestCaseResult):
        """ Remove the outputs of a hidden test case, students must not see what its input made
            their program write. Truncate the outputs of a visible test case to output_limit """
        if test_case.hidden:
            test_result.stdout = test_result.stderr = ''
        else:
            test_result.stdout = truncate_output(test_result.stdout, self.output_limit)
            test_result.stderr = truncate_output(test_result.stderr, self.output_limit)

    @staticmethod
    def _timed_out(test_result:vyg.TestCaseResult, wall_time_limit:float) -> bool:
        """ True if `timeout` stopped the solution. A SIGKILL before the limit is a crash, e.g:
            out of memory """
        return (test_result.exitCode == TIMEOUT_EXIT_CODE or
                test_result.exitCode == KILLED_EXIT_CODE and
                test_result.wallTime >= wall_time_limit)

    @staticmethod
    def _build_args(test_case:vyg.TestCase) -> list:
        """ Split the command line arguments of the test case as a shell would, but without
            expanding variables, globs, or running commands """
        try:
            return shlex.split(test_case.args)
        except ValueError as error:
            # E.g: unbalanced quotes
            raise InvalidSubmission('Invalid test case arguments') from error

    def _build_run_prefix(self) -> list:
        """ Build the prefix to run the solution with extra tools, e.g: memcheck, helgrind """
        for tool in self.tools:
            if tool in RUN_TOOLS:
                return list(RUN_TOOLS[tool])
        return []

    def _fetch_stats(self, test_result:vyg.TestCaseResult):
        """ Fetch /usr/bin/time output, parse it to extract the wall time, the CPU time (all
            threads added up), and the maximum memory of the test case for the frontend """
        # TODO(jhc): The student can write this file, so a solution could forge its statistics.
        # Measure them outside the student's reach
        time_output, _, _ = self._run_in_container(['cat', TIME_FILE], STATS_TIMEOUT)
        match = WALL_TIME_PATTERN.search(time_output)
        if match:
            hours, minutes, seconds = match.groups()
            test_result.wallTime = (int(hours or 0) * 3600 + int(minutes) * 60
                    + float(seconds))
        else:
            test_result.wallTime = 0.0
        test_result.cpuTime = round(Execution._parse_stat(USER_TIME_PATTERN, time_output)
                + Execution._parse_stat(SYSTEM_TIME_PATTERN, time_output), 3)
        # /usr/bin/time reports kibibytes, the frontend expects bytes
        test_result.memory = int(Execution._parse_stat(MEMORY_PATTERN, time_output)) * 1024
        # If this test case lasted longer than the longest known, even if it failed
        self.result.maxWallTime = max(self.result.maxWallTime, test_result.wallTime)

    @staticmethod
    def _parse_stat(pattern:re.Pattern, time_output:str) -> float:
        """ Return the number captured by pattern in the output of /usr/bin/time, or 0 """
        match = pattern.search(time_output)
        return float(match.group(1)) if match else 0.0

    def _compare_output(self, output_type:str, expected_output:str,
                test_result:vyg.TestCaseResult):
        """ Compare student stdout or stderr considering if indeterminism is allowed """
        assert hasattr(test_result, output_type)
        expected_output = expected_output.strip()
        student_output = getattr(test_result, output_type).strip()
        # Do not consider stderr mismatch if expected stderr is empty (it can be used for debug)
        must_match = output_type == 'stdout' or expected_output != ''
        if self.problem.allowIndeterminism == 'lines':
            # sorted() returns a new list, list.sort() returns None and any output would match
            student_output = sorted(student_output.split('\n'))
            expected_output = sorted(expected_output.split('\n'))
        if must_match and student_output != expected_output:
            test_result.status = vyg.Status.WRONG
            self.result.status = vyg.Status.WRONG
            test_result.message = f'Wrong {output_type}'
            #self.result.message = vyg.append(self.result.message, test_result.message)

    def _check_time_range(self, test_case:vyg.TestCase, test_result:vyg.TestCaseResult):
        """ Check if the test case run within the time range allowed by the problem """
        if test_result.status != vyg.Status.PASSED:
            return
        # Each test case is judged by its own duration, not by the longest one of the run
        duration = test_result.wallTime # or test_result.cpuTime
        assert duration >= 0.0
        min_duration = bounded_number(test_case.minDuration or self.problem.minDuration,
                0.0, 0.0, MAX_DURATION)
        max_duration = self._wall_time_limit(test_case)
        if min_duration and duration < min_duration:
            self.result.status = test_result.status = vyg.Status.TIMEOUT
            test_result.message = vyg.append(test_result.message,
                    'Execution faster than expected')
        if max_duration and duration > max_duration:
            self.result.status = test_result.status = vyg.Status.TIMEOUT
            test_result.message = vyg.append(test_result.message,
                    'Execution slower than expected')

    def _run_thread_count_proof(self, index:int, stdin:str, test_result:vyg.TestCaseResult):
        """ Checks that user solution created the required count of threads in the test case at
            index, and stores the count in its result """
        # Get the test case
        assert 0 <= index < len(self.problem.tests)
        test = self.problem.tests[index]
        # To get the number of created threads, we use GDB: -q quiet, -batch exits after running
        # the -ex commands. We count output lines that report New Thread events. The solution
        # inherits the stdin of gdb, a fixed file name, not user data. `run < file` would replace
        # the arguments given with --args, e.g. the script of Python and those of the test case
        cmd = (['gdb', '-q', '-batch', '-ex=run', '--args'] + self.flags.run_command.split()
                + self._build_args(test))
        # gdb runs the solution slower than the test case
        proof_limit = self._time_left(self._wall_time_limit(test) + THREAD_PROOF_EXTRA)
        stdout, _, _ = self._run_in_container(cmd, proof_limit, stdin)
        self._kill_student_processes()
        test_result.threadCount = sum('New Thread' in line for line in stdout.splitlines())
        # Get the accepted range, min may be the first number in stdin
        min_threads = test.minThreads or self.problem.minThreads
        if min_threads == 'stdin':
            words = test.stdin.split(maxsplit=1)
            min_threads = int(words[0]) if words and words[0].isdecimal() else None
        min_threads = bounded_number(min_threads, 1, 0, vyg.MAX_THREADS)
        max_threads = bounded_number(test.maxThreads or self.problem.maxThreads,
                vyg.MAX_THREADS, 0, vyg.MAX_THREADS)
        # Check it is in range
        in_range = min_threads <= test_result.threadCount <= max_threads
        # If user did not create the asked amount of threads
        if not in_range:
            # Mark the test case failed, and the whole run
            test_result.status = self.result.status = vyg.Status.RUNTIME_ERROR
            # Provide a descriptive message. The proof runs only on passed test cases, which
            # have no message yet
            test_result.message = (
                    f'Invalid amount of secondary threads ({test_result.threadCount})')

    def _after_run_proofs(self):
        """ Run after test case proofs, e.g: linting """
        # Languages without a linting filter have no linter yet
        if 'lint' in self.tools and self.flags.linting_options:
            # Run the linter, e.g: cpplint.py
            cmd = ['cpplint', f'--filter={self.flags.linting_options}', self.source_file]
            stdout, stderr, exit_code = self._run_in_container(cmd, LINT_TIMEOUT)
            if exit_code != 0:
                # Linter found errors, report them
                self.result.compileOutput = truncate_output(vyg.append(self.result.compileOutput,
                        vyg.append(stdout, stderr, '\n'), '\n'), self.output_limit)
                self.result.status = vyg.Status.COMPILER_ERROR
                self.result.message = vyg.append(self.result.message,
                        'Linter found errors in the code')
