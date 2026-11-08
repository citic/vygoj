""" Compile and run a student's solution against the test cases of a problem in a container """
import dataclasses
import io
import logging
import math
import re
import shlex
import tarfile
import threading
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
# Maximum time allowed to a user solution to run in seconds
MAX_DURATION = 10 # seconds
# Wall time limit for a test case when neither the test case nor the problem set one
DEFAULT_DURATION = 2 # seconds
# Time limits for compiling, linting, and reading statistics in the container
COMPILE_TIMEOUT = 2 # seconds
LINT_TIMEOUT = 2 # seconds
STATS_TIMEOUT = 2 # seconds
# Time limit for the gdb run that counts the threads created by the solution
THREAD_PROOF_TIMEOUT = 3 # seconds
# Seconds between the SIGTERM and the SIGKILL sent by `timeout` to a command that does not end
KILL_GRACE = 1 # seconds
# Extra seconds a command may last after its timeout before the backend kills all student processes
# in the container. Background processes may keep the output pipe open after `timeout` ends
HANG_GRACE = 3 # seconds
# Total time for a submission. The container is killed when it expires. It must be shorter than
# BACKEND_RUN_TIMEOUT in frontend/src/problems.py
SUBMISSION_DEADLINE = 100 # seconds
# Read timeout for each call to the Docker API, longer than any command run in the container
DOCKER_TIMEOUT = MAX_DURATION + KILL_GRACE + HANG_GRACE + 10 # seconds

# Bounds for the data received from the frontend. Each value is untrusted
MAX_CODE_BYTES = 256 * 1024
MAX_TESTS = 100
MAX_TEST_INPUT_BYTES = 4 * 1024 * 1024
MAX_ARGS_LENGTH = 4096
# Bytes kept from the stdout and from the stderr of each command, the rest is discarded
MAX_OUTPUT_BYTES = 1024 * 1024

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

# Docker is a server, we need a client to use it. from_env() creates a client that connects to the
# server using the default socket or configuration in your environment variables. from_env() gives
# you access to the same client when you run the `docker` command in your shell. The timeout
# bounds each API call, so a stuck container cannot block a backend worker forever.
# Doc: https://docker-py.readthedocs.io/en/stable/client.html
docker_client = docker.from_env(timeout=DOCKER_TIMEOUT)

@dataclasses.dataclass(frozen=True)
class LanguageDefault:
    """ Default language options """
    id: int
    file_extension: str
    compiler: str
    compiler_options: str
    # The linker resolves symbols in order, so libraries must follow the source files
    libraries: str
    linting_options: str

COMMON_LINT = '-build/header_guard,-build/include_subdir,-runtime/int'
# TODO(jhc): override default compiler options with problem.compilerOptionsFor[lang]
# -fno-diagnostics-color
LANGUAGE_DEFAULTS = {
    'C': LanguageDefault(50, 'c', 'gcc',
        '-g -Wall -Wextra -std=gnu17 -pthread', '-lm',
        f'{COMMON_LINT},-readability/casting'),
    'C++': LanguageDefault(54, 'cpp', 'g++',
        '-g -Wall -Wextra -std=gnu++20 -pthread', '-lm',
        f'{COMMON_LINT},-build/c++11,-runtime/references'),
}

# Compiler options and run prefixes of the tools that a problem may ask for. Only these tools are
# accepted, any other word in problem.tools is ignored
COMPILE_TOOLS = {
    'asan': ['-fsanitize=address', '-fmessage-length=80'],
    'tsan': ['-fsanitize=thread', '-fmessage-length=80'],
    'ubsan': ['-fsanitize=undefined', '-fmessage-length=80'],
}
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
        """ Constructor. Raises InvalidSubmission if the problem or the solution is malformed """
        try:
            # The problem to be solved, sent by VygOJ frontend
            self.problem = vyg.Problem(problem_json, None, True)
            # The solution submitted by user, sent by VygOJ frontend as a message
            self.solution = vyg.Message(solution_json)
        except (ValueError, TypeError, AttributeError) as error:
            # Invalid base64, UTF-8, or JSON types in the fields
            raise InvalidSubmission('Malformed problem or solution') from error
        # The programming language used by user to write the code solution
        # Language is sent by client, but if omitted, we suppose 'C'
        self.language = self.solution.language or 'C'
        # Extra tools asked by the problem, e.g: ['asan', 'lint']
        self.tools = self.problem.tools.split() if isinstance(self.problem.tools, str) else []
        self._validate()
        # The filename of the student's solution, e.: 'solution.c'
        self.source_file = f'solution.{LANGUAGE_DEFAULTS[self.language].file_extension}'
        # Executable file name, relative to WORKDIR
        self.executable = 'solution'
        # Docker container to compiler and run test cases
        self.container:docker.models.containers.Container = None
        # Kills the container when the submission lasts longer than SUBMISSION_DEADLINE
        self.watchdog:threading.Timer = None
        # True if the watchdog killed the container
        self.deadline_expired = False
        # The execution result of each test case and a brief to be returned to frontend
        self.result = vyg.ExecutionResult({})

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
        if len(self.problem.tests) > MAX_TESTS:
            raise InvalidSubmission(f'Problem has more than {MAX_TESTS} test cases')
        for test in self.problem.tests:
            self._validate_test_case(test)

    @staticmethod
    def _validate_test_case(test:vyg.TestCase):
        """ Check types and sizes of the fields of a test case """
        for text in (test.input, test.output, test.stderr, test.commandLineArguments):
            if not isinstance(text, str):
                raise InvalidSubmission('Invalid test case')
        if len(test.input.encode('utf-8')) > MAX_TEST_INPUT_BYTES:
            raise InvalidSubmission(f'Test case input exceeds {MAX_TEST_INPUT_BYTES} bytes')
        if len(test.commandLineArguments) > MAX_ARGS_LENGTH:
            raise InvalidSubmission('Test case arguments are too long')
        # Raises InvalidSubmission if the arguments cannot be split, e.g: unbalanced quotes
        Execution._build_args(test)
        if bounded_number(test.points, None, -math.inf, math.inf) is None:
            raise InvalidSubmission('Test case points must be a number')

    def execute(self) -> str:
        """ Execute the solution against all test cases. Return the result as a JSON string """
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
            # Run all test cases. TODO(jhc): test in parallel? needed?
            for index0, test_case in enumerate(self.problem.tests):
                # Create an execution object, run it, and wait its execution result
                self._run_test_case(index0, test_case)
            # Run after test case proofs, e.g: linting
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

    def _check_static_analysis(self):
        """ If professor asked to do static analysis, eg: check some words are in code"""
        if not self.problem.mustContain:
            return
        code = self.solution.code or ''
        for token in self.problem.mustContain:
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
        self.watchdog = threading.Timer(SUBMISSION_DEADLINE, self._expire_deadline)
        self.watchdog.daemon = True
        self.watchdog.start()

    def _expire_deadline(self):
        """ Called by the watchdog when the submission lasts too long: kill the container """
        self.deadline_expired = True
        logger.warning('Submission exceeded %s seconds, killing its container',
                SUBMISSION_DEADLINE)
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
                Execution._add_to_tar(tar_file, Execution._input_file(index0), test.input)
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
        # timeout sends SIGTERM when time is over, and SIGKILL later if the program ignores it
        command = (prefix or []) + ['timeout', '-k', str(KILL_GRACE), f'{timeout:.3f}'] + argv
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
        """ Compile the solution if its language is compiled, e.g: C, C++, Java... """
        flags = LANGUAGE_DEFAULTS[self.language]
        # Prepare compilation command. Options are defined by the backend, never by users
        cmd = ([flags.compiler] + self._build_compiler_options(flags)
                + [self.source_file, '-o', self.executable] + flags.libraries.split())
        # Run the compilation command, if it fails, report to frontend
        stdout, stderr, exit_code = self._run_in_container(cmd, COMPILE_TIMEOUT)
        self.result.compileOutput = stdout + stderr
        if exit_code != 0:
            # Student code produced compiling errors
            raise FailedSolution(self.result, vyg.Status.COMPILER_ERROR,
                    vyg.append(stdout, stderr, '\n'))
        # TODO(jhc): Check if the executable is created
        # TODO(jhc): Create a snapshot (commit/image) of the container in order to restore it
        # after running the student solution against each test case. Disabled until efficiency
        # could be measured
        # self.container.commit(repository='vyg', tag='after_compile', message='')

    def _build_compiler_options(self, flags:LanguageDefault) -> list:
        """ Build the compiler options for the language used by student """
        compiler_options = flags.compiler_options.split()
        # Get the compiler options from the problem object, if not defined, use the default ones
        # compiler_options = self.problem.compilerOptionsFor.get(self.language,
        #         flags.compiler_options)
        # If professor asked to use some extra tools, add them to the compiler options
        for tool in self.tools:
            compiler_options += COMPILE_TOOLS.get(tool, [])
        return compiler_options

    def _run_test_case(self, index0:int, test_case:vyg.TestCase):
        """ Runs a test case of the problem given in the constructor """
        # Get the test case to run
        assert 0 <= index0 < len(self.problem.tests)
        input_file = Execution._input_file(index0)
        expected_output = test_case.output
        expected_error = test_case.stderr
        # TODO(jhc): get wall time limit from min(problem, max_for_language)
        wall_time_limit = bounded_number(test_case.maxDuration or self.problem.maxDuration,
                DEFAULT_DURATION, 0.1, MAX_DURATION)
        # Prepare run command: /usr/bin/time -v -o vyg_time.txt timeout 2 ./solution < input.txt
        cmd = self._build_run_prefix() + [f'./{self.executable}'] + self._build_args(test_case)
        time_prefix = ['/usr/bin/time', '-v', '-o', TIME_FILE]
        test_result = vyg.TestCaseResult({})
        test_result.stdout, test_result.stderr, test_result.exitCode = (
                self._run_in_container(cmd, wall_time_limit, input_file, time_prefix))
        # Background processes must not interfere with the statistics or the next test cases
        self._kill_student_processes()
        # Fetch the statistics generated by the /usr/bin/time command
        self._fetch_stats(test_result)
        # Compare standard output and error against expected ones in test case
        self._compare_output('stdout', expected_output, test_result)
        self._compare_output('stderr', expected_error, test_result)
        if Execution._timed_out(test_result, wall_time_limit):
            # The solution was killed by timeout
            test_result.status = vyg.Status.TIMEOUT
            self.result.status = vyg.Status.TIMEOUT
            test_result.message = 'Time limit exceeded'
        elif (test_result.exitCode != 0 or test_result.stderr and
            'ERROR SUMMARY: 0 errors' not in test_result.stderr):
            # If the exit code is not 0, mark the test case as failed
            test_result.status = vyg.Status.RUNTIME_ERROR
            self.result.status = vyg.Status.RUNTIME_ERROR
            test_result.message = f'Exit code {test_result.exitCode}'
            #self.result.message = vyg.append(self.result.message, test_result.message)
        # Check solution is in time range
        self._check_time_range(test_case, test_result)
        # If there further proofs, execute them
        if self.result.status == vyg.Status.PASSED and self.problem.has_proofs():
            self._run_thread_count_proof(index0, input_file)
        # Store the result in the array to be returned to the client
        # TODO(jhc): Each step should save into the self.result dictionary
        self.result.results.append(test_result)
        # If the test was passed
        if test_result.status == vyg.Status.PASSED:
            # Increase the count of passed test cases and accumulate the points
            self.result.passedTestCount += 1
            self.result.points += test_case.points
            self.result.totalPoints += test_case.points
        logger.debug('Test case %d: %s', index0 + 1, test_result.status)

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
            return shlex.split(test_case.commandLineArguments)
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
        """ Fetch /usr/bin/time output, parse it to extract some statistics for the frontend """
        # TODO(jhc): Fetch CPU time, used RAM
        # TODO(jhc): The student can write this file, so a solution could forge its duration.
        # Measure the time outside the student's reach
        time_output, _, _ = self._run_in_container(['cat', TIME_FILE], STATS_TIMEOUT)
        match = re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): 0:(\d+\.\d+)',
                time_output)
        if match:
            test_result.wallTime = float(match.group(1))
        else:
            test_result.wallTime = 0.0
        # If this test case lasted longer than the longest known, even if it failed
        self.result.maxWallTime = max(self.result.maxWallTime, test_result.wallTime)

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
        """ Check if the solution run within the time range allowed by the problem """
        if self.result.status != vyg.Status.PASSED:
            return
        duration = self.result.maxWallTime # or self.result.maxCpuTime
        assert duration >= 0.0
        min_duration = bounded_number(test_case.minDuration or self.problem.minDuration,
                0.0, 0.0, MAX_DURATION)
        max_duration = bounded_number(test_case.maxDuration or self.problem.maxDuration,
                MAX_DURATION, 0.0, MAX_DURATION)
        if min_duration and duration < min_duration:
            self.result.status = test_result.status = vyg.Status.TIMEOUT
            test_result.message = vyg.append(test_result.message,
                    'Execution faster than expected')
        if max_duration and duration > max_duration:
            self.result.status = test_result.status = vyg.Status.TIMEOUT
            test_result.message = vyg.append(test_result.message,
                    'Execution slower than expected')

    def _run_thread_count_proof(self, index:int, stdin:str):
        """ Checks that user solution created the required count of threads """
        # Get the test case
        assert 0 <= index < len(self.problem.tests)
        test = self.problem.tests[index]
        # To get the number of created threads, we use GDB: -q quiet, -batch exits after running
        # the -ex commands. stdin is a fixed file name, not user data. We count output lines that
        # report New Thread events
        cmd = (['gdb', '-q', '-batch', f'-ex=run < {stdin}', '--args', f'./{self.executable}']
                + self._build_args(test))
        stdout, _, _ = self._run_in_container(cmd, THREAD_PROOF_TIMEOUT)
        self._kill_student_processes()
        self.result.threadCount = sum('New Thread' in line for line in stdout.splitlines())
        # Get the accepted range, min may be the first number in stdin
        min_threads = test.minThreads or self.problem.minThreads
        if min_threads == 'stdin':
            words = test.input.split(maxsplit=1)
            min_threads = int(words[0]) if words and words[0].isdecimal() else None
        min_threads = bounded_number(min_threads, 1, 0, vyg.MAX_THREADS)
        max_threads = bounded_number(test.maxThreads or self.problem.maxThreads,
                vyg.MAX_THREADS, 0, vyg.MAX_THREADS)
        # Check it is in range
        in_range = min_threads <= self.result.threadCount <= max_threads
        # If user did not create the asked amount of threads
        if not in_range:
            # Mark the test case failed
            self.result.status = vyg.Status.RUNTIME_ERROR
            # Provide a descriptive message
            self.result.message = vyg.append(self.result.message,
                    f'Invalid amount of secondary threads ({self.result.threadCount})')

    def _after_run_proofs(self):
        """ Run after test case proofs, e.g: linting """
        if 'lint' in self.tools:
            flags = LANGUAGE_DEFAULTS[self.language]
            # Run the linter, e.g: cpplint.py
            cmd = ['cpplint', f'--filter={flags.linting_options}', self.source_file]
            stdout, stderr, exit_code = self._run_in_container(cmd, LINT_TIMEOUT)
            if exit_code != 0:
                # Linter found errors, report them
                self.result.compileOutput += vyg.append(stdout, stderr, '\n')
                self.result.status = vyg.Status.COMPILER_ERROR
                self.result.message = vyg.append(self.result.message,
                        'Linter found errors in the code')
