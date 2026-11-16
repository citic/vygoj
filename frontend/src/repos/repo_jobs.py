""" Background jobs on the repos of a user, which take too long or too many resources for a
request: on the student repo, zip the last solutions, zip a copy of the repo with its history and
a working tree, and push the repo to the remote of the user; on each professor repo, clone it or
pull its changes, and update its courses. A request starts the job as a separate process,
`python manage.py repo-job <kind> <username> [<repo id>]`, with the lowest priority of the
operating system and a time limit, and the page asks for its state until it ends. The state is
kept in files, so it survives reloads, other browsers and computers, and restarts of the gunicorn
workers. A job of a professor repo is named <kind>_<repo id> (e.g. pull_7):

    user/<username>/jobs/<name>.json    # state: running, done, or failed, with times and message
    user/<username>/jobs/<name>.lock    # locked by the process while it runs
    user/<username>/jobs/<name>.log     # output of the last process, for the administrators
    user/<username>/jobs/<name>.zip     # the zip made by the job, kept for REPO_ZIP_RETENTION,
                                        # or until the repo gets a new version

A user runs one job of each name at a time, a minute after the last start of that name at least,
and the server at most REPO_MAX_JOBS """

import fcntl
import glob
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import zipfile

from flask import current_app as app

from course_offer import parse_courses, sync_offers
from repos.git_repo import JOBS_FOLDER, USERS_FOLDER, GitError, user_folder
from repos.professor_repo import CloneError, ProfessorRepo
from repos.ssh_key import UserKey
from repos.student_repo import StudentRepo

# Kinds of jobs, the ones that make a zip, and the ones of a professor repo, which need its id
JOB_KINDS = ('solutions', 'history', 'push', 'pull')
ZIP_KINDS = ('solutions', 'history')
PROFESSOR_KINDS = ('pull',)
# Priority of the processes of the jobs (nice): the lowest one, so runs and pages go first
NICENESS = 19
# Seconds that a new process may take to take its lock. Until then a job without lock is starting;
# after it, a job without lock that did not finish was interrupted (e.g. the server restarted)
STARTUP_GRACE = 30
# Seconds between two starts of a job of a user, so they cannot keep the server busy with jobs
JOB_INTERVAL = 60
# Seconds that a process waits for its lock, which a request may hold for a moment to check it
LOCK_WAIT = 2
# Script that runs the jobs, in the folder of the sources (src)
MANAGE_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'manage.py')
# Message codes of the jobs, which the page translates: errors of the request that starts a job,
# results of the jobs, and causes of their failures
RUNNING, BUSY, TOO_SOON = 'running', 'busy', 'too_soon'
UP_TO_DATE, PUSHED, CLONED, PULLED = 'up_to_date', 'pushed', 'cloned', 'pulled'
EMPTY, TOO_BIG, NO_ORIGIN, TIMEOUT, INTERRUPTED, FAILED = (
    'empty', 'too_big', 'no_origin', 'timeout', 'interrupted', 'failed')
# Fields of the state of a done job that the page receives, besides its times and message: the
# expiration of a zip, and the courses found by a pull, with the names that other repos have and
# the number of courses that are not valid
RESULT_FIELDS = ('expires', 'courses', 'skipped', 'invalid')
# Causes of failed pushes, clones, and pulls, by a text of the error output of git or ssh
REMOTE_ERRORS = (
    ('Remote branch main not found', 'no_main'),
    ("couldn't find remote ref", 'no_main'),
    ('Host key verification failed', 'host_key'),
    ('Permission denied', 'denied'),
    ('Repository not found', 'not_found'),
    ('does not appear to be a git repository', 'not_found'),
    ('[rejected]', 'rejected'),
    ('[remote rejected]', 'rejected'),
    ('Could not resolve hostname', 'connect'),
    ('Connection timed out', 'connect'),
    ('Connection refused', 'connect'),
    ('Network is unreachable', 'connect'),
)

# Processes started by this gunicorn worker. They are reaped when the worker starts another one,
# so they do not stay as zombies after they end
_children = []

class RepoJobError(Exception):
    """ A job that cannot start or failed, with the code of its message """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

class JobTimeout(Exception):
    """ The time limit of a job ended. Not a TimeoutError, which is an OSError that the code of
    the job may catch """

class RepoJob:
    """ A job of a kind on the student repo of a user, or on one of their professor repos """

    def __init__(self, username: str, kind: str, repo_id: int = None):
        """ Find the files of the job. Raise ValueError if the kind is not valid, or the id of
        the professor repo is missing in a job of a professor repo, or given in another one """
        if kind not in JOB_KINDS or (kind in PROFESSOR_KINDS) != (repo_id is not None):
            raise ValueError(f'invalid kind of job: {kind!r}')
        if repo_id is not None and (isinstance(repo_id, bool) or not isinstance(repo_id, int)
                or repo_id <= 0):
            raise ValueError(f'invalid repo id: {repo_id!r}')
        self.username = username
        self.kind = kind
        self.repo_id = repo_id
        self.name = kind if repo_id is None else f'{kind}_{repo_id}'
        self.folder = os.path.join(user_folder(username), JOBS_FOLDER)
        self.files = job_files(self.folder, self.name)
        # Fields that the job adds to its state when it is done, e.g. the version of its zip
        self.result = {}

    # State ---------------------------------------------------------------------------------------

    def state(self) -> dict:
        """ Return the state of the job for the page: state (none, running, done, or failed),
        started, finished, and expires (of the zip) in seconds since the epoch, and the code of
        its message. A zip that expired, or was made from an older version of the repo, is
        deleted, so the user makes a new one """
        state = read_state(self.files['json'])
        if state.get('state') == 'running' and not is_running(self.files, state):
            state = { **state, 'state': 'failed', 'message': INTERRUPTED }
        if self.kind in ZIP_KINDS and state.get('state') == 'done':
            expires = state.get('finished', 0) + app.config['REPO_ZIP_RETENTION']
            if (expires <= time.time() or not os.path.isfile(self.files['zip'])
                    or state.get('version') != self.repo_version()):
                remove_file(self.files['zip'])
                return { 'state': 'none' }
            state['expires'] = expires
        return { key: state[key] for key in ('state', 'started', 'finished', 'message',
            *RESULT_FIELDS) if key in state } or { 'state': 'none' }

    def repo_version(self) -> str | None:
        """ Return the version of the student repo of the user, or None if it cannot be read """
        try:
            return StudentRepo(self.username).version()
        except (GitError, OSError, ValueError):
            app.logger.exception('could not read the version of the repo of %s', self.username)
            return None

    def zip_path(self) -> str | None:
        """ Return the path of the zip of the job, or None if it is not ready or expired """
        return self.files['zip'] if self.state().get('state') == 'done' else None

    def write_state(self, **state):
        """ Replace the state of the job. The file is replaced at once, so it is never read half
        written """
        os.makedirs(self.folder, mode=0o700, exist_ok=True)
        with tempfile.NamedTemporaryFile('w', dir=self.folder, delete=False,
                encoding='utf-8') as file:
            json.dump({ 'kind': self.kind, **state }, file)
        os.replace(file.name, self.files['json'])

    # Start (in a request) -------------------------------------------------------------------------

    def start(self):
        """ Start the job as a separate process. Raise RepoJobError if this job is running or
        started less than JOB_INTERVAL seconds ago, or the server runs REPO_MAX_JOBS jobs """
        reap_children()
        delete_expired_zips()
        state = read_state(self.files['json'])
        if is_running(self.files, state):
            raise RepoJobError(RUNNING)
        if time.time() - state.get('started', 0) < JOB_INTERVAL:
            raise RepoJobError(TOO_SOON)
        if count_running() >= app.config['REPO_MAX_JOBS']:
            raise RepoJobError(BUSY)
        self.write_state(state='running', started=int(time.time()))
        try:
            with open(self.files['log'], 'w', encoding='utf-8') as log:
                # A new session, so the process goes on if the worker that started it stops.
                # Without shell: the username is one argument, whatever it has. The process
                # outlives this request, so it is not waited in a with block, but reaped later
                repo = [] if self.repo_id is None else [str(self.repo_id)]
                _children.append(subprocess.Popen( # pylint: disable=consider-using-with
                    [sys.executable, MANAGE_SCRIPT, 'repo-job', self.kind, self.username, *repo],
                    cwd=os.path.dirname(MANAGE_SCRIPT), stdin=subprocess.DEVNULL, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True))
        except OSError:
            self.write_state(state='failed', finished=int(time.time()), message=FAILED)
            raise

    # Run (in the process of the job) --------------------------------------------------------------

    def run(self) -> int:
        """ Do the job, with the lowest priority and a time limit, and write its result in its
        state. Return the exit status: 0 if it was done """
        with open(self.files['lock'], 'a', encoding='utf-8') as lock:
            if not take_lock(lock):
                # Another process runs this job, and writes its state
                return 1
            os.nice(NICENESS)
            started = read_state(self.files['json']).get('started', int(time.time()))
            state, message = 'failed', FAILED
            signal.signal(signal.SIGALRM, stop_job)
            signal.alarm(self.time_limit())
            try:
                message = getattr(self, f'run_{self.kind}')()
                state = 'done'
            except (RepoJobError, CloneError) as error:
                message = error.code
            except JobTimeout:
                message = TIMEOUT
            except GitError as error:
                app.logger.exception('repo job %s of %s failed', self.name, self.username)
                message = TIMEOUT if error.timed_out else remote_error(error.stderr)
            except (OSError, ValueError):
                app.logger.exception('repo job %s of %s failed', self.name, self.username)
            finally:
                signal.alarm(0)
            self.write_state(state=state, started=started, finished=int(time.time()),
                message=message, **(self.result if state == 'done' else {}))
        return 0 if state == 'done' else 1

    def time_limit(self) -> int:
        """ Return the seconds that the job may take: a clone of a professor repo may bring many
        materials, and a pull only their changes """
        if self.kind != 'pull':
            return app.config['REPO_JOB_TIMEOUT']
        repo = self.professor_repo()
        if repo and repo.clone().is_clone():
            return app.config['PROFESSOR_REPO_PULL_TIMEOUT']
        return app.config['PROFESSOR_REPO_CLONE_TIMEOUT']

    def run_solutions(self) -> str:
        """ Zip the last version of the solution of every problem """
        repo = self.checked_repo()
        self.write_zip(lambda path: write_bytes(path, repo.archive_solutions()))
        return ''

    def run_history(self) -> str:
        """ Zip a copy of the repo, with its history and the main branch in its working tree """
        repo = self.checked_repo()
        name = app.config['STUDENT_REPO_NAME']
        with tempfile.TemporaryDirectory(dir=self.folder) as folder:
            repo.copy_with_tree(os.path.join(folder, name), app.config['REPO_JOB_TIMEOUT'])
            self.write_zip(lambda path: zip_folder(folder, path))
        return ''

    def run_push(self) -> str:
        """ Push the repo to the remote of the user """
        repo = self.checked_repo()
        if not repo.origin():
            raise RepoJobError(NO_ORIGIN)
        output = repo.push_to_origin(UserKey(self.username).ssh_command(),
            app.config['REPO_JOB_TIMEOUT'])
        # --porcelain writes a line per ref, which starts with = when the ref was up to date
        refs = [line for line in output.splitlines() if line[:1] in '=*+-!' and '\t' in line]
        return UP_TO_DATE if all(line.startswith('=') for line in refs) else PUSHED

    def run_pull(self) -> str:
        """ Clone the professor repo, or pull its changes if it has a clone, and update its
        courses. A repo bigger than PROFESSOR_REPO_MAX_SIZE is removed, or goes back to the
        commit before the pull """
        repo = self.professor_repo()
        if not repo:
            raise RepoJobError(FAILED)
        clone = repo.clone()
        ssh_command, timeout = UserKey(self.username).ssh_command(), self.time_limit()
        # The commit before the pull, or None for a new clone
        old_commit = None
        if clone.is_clone():
            old_commit = clone.pull_from(repo.url, ssh_command, timeout)
        else:
            clone.clone_from(repo.url, ssh_command, timeout)
        if clone.size() > app.config['PROFESSOR_REPO_MAX_SIZE']:
            if old_commit:
                clone.revert(old_commit, timeout)
            else:
                clone.remove()
            raise RepoJobError(TOO_BIG)
        try:
            courses, invalid = parse_courses(clone.read_catalog(), clone.path)
        except CloneError:
            # Without a valid vygoj.json, the repo has no courses: the offered ones are hidden
            sync_offers(repo, [], clone.head())
            raise
        skipped = sync_offers(repo, list(courses), clone.head())
        self.result.update(courses=len(courses) - len(skipped), skipped=skipped, invalid=invalid)
        return PULLED if old_commit else CLONED

    def professor_repo(self) -> ProfessorRepo | None:
        """ Return the professor repo of the job, if it still belongs to the user """
        return ProfessorRepo.find(self.username, self.repo_id)

    def checked_repo(self) -> StudentRepo:
        """ Return the student repo of the user, and keep its version in the result of the job.
        Raise RepoJobError if it has no solutions or it is bigger than STUDENT_REPO_MAX_SIZE """
        repo = StudentRepo(self.username)
        repo.create()
        if repo.size() > app.config['STUDENT_REPO_MAX_SIZE']:
            raise RepoJobError(TOO_BIG)
        if not repo.info()['commits']:
            raise RepoJobError(EMPTY)
        # Taken before the job reads the repo: a version saved meanwhile makes the zip old, and
        # it is made again, never kept with missing solutions
        self.result['version'] = repo.version()
        return repo

    def write_zip(self, write):
        """ Make the zip of the job with the write function, which receives the path of a
        temporary file. The zip replaces the old one at once, when it is complete """
        temporary = f'{self.files["zip"]}.tmp'
        try:
            write(temporary)
            os.replace(temporary, self.files['zip'])
        finally:
            remove_file(temporary)

# Files and locks ---------------------------------------------------------------------------------

def job_files(folder: str, kind: str) -> dict:
    """ Return the paths of the files of the job of the kind in the jobs folder of a user """
    return { extension: os.path.join(folder, f'{kind}.{extension}')
        for extension in ('json', 'lock', 'log', 'zip') }

def read_state(path: str) -> dict:
    """ Return the state in the file, or an empty dictionary if it is missing or not valid """
    try:
        with open(path, encoding='utf-8') as file:
            state = json.load(file)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}

def is_running(files: dict, state: dict) -> bool:
    """ True if the job of the files is running: its state says so, and its process holds the
    lock or is still starting """
    if state.get('state') != 'running':
        return False
    if time.time() - state.get('started', 0) < STARTUP_GRACE:
        return True
    try:
        with open(files['lock'], encoding='utf-8') as lock:
            # A shared lock is refused while the process holds its exclusive lock
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(lock, fcntl.LOCK_UN)
            return False
    except BlockingIOError:
        return True
    except OSError:
        return False

def take_lock(lock) -> bool:
    """ Take the exclusive lock of the open file, waiting up to LOCK_WAIT seconds for a request
    that checks it. Return whether it was taken. The system releases it when the process ends """
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)

def jobs_pattern(extension: str) -> str:
    """ Return the glob pattern of the files of the jobs of every user with the extension """
    return os.path.join(glob.escape(app.config['DATA_FOLDER']), USERS_FOLDER, '*', JOBS_FOLDER,
        f'*.{extension}')

def count_running() -> int:
    """ Return the number of jobs that run in the server, of every user """
    count = 0
    for path in glob.glob(jobs_pattern('json')):
        folder, name = os.path.split(path)
        name = name.removesuffix('.json')
        # The name of a job of a professor repo has its kind before the id of the repo
        if (name.partition('_')[0] in JOB_KINDS
                and is_running(job_files(folder, name), read_state(path))):
            count += 1
    return count

def delete_expired_zips():
    """ Delete the zips of every user that are older than REPO_ZIP_RETENTION """
    oldest = time.time() - app.config['REPO_ZIP_RETENTION']
    for path in glob.glob(jobs_pattern('zip')):
        try:
            if os.path.getmtime(path) < oldest:
                os.remove(path)
        except OSError:
            pass

def remove_file(path: str):
    """ Remove the file if it exists """
    try:
        os.remove(path)
    except FileNotFoundError:
        pass

def reap_children():
    """ Forget the processes of jobs that ended, so they do not stay as zombies """
    _children[:] = [child for child in _children if child.poll() is None]

# Helpers of the jobs -----------------------------------------------------------------------------

def stop_job(*_):
    """ Stop the job when its time limit ends (handler of SIGALRM) """
    raise JobTimeout('the job took too long')

def remote_error(stderr: str) -> str:
    """ Return the code of the cause of a failed push, clone, or pull, from the error output of
    git and ssh. The output is not shown: it may have paths of the server """
    return next((code for text, code in REMOTE_ERRORS if text in stderr), FAILED)

def write_bytes(path: str, data: bytes):
    """ Write the data to a new file """
    with open(path, 'wb') as file:
        file.write(data)

def zip_folder(folder: str, path: str):
    """ Write a zip with the files of the folder, in paths relative to it. Links are skipped, so
    the zip never has files out of the folder """
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for parent, folders, names in os.walk(folder):
            folders[:] = [name for name in folders
                if not os.path.islink(os.path.join(parent, name))]
            for name in names:
                file = os.path.join(parent, name)
                if not os.path.islink(file):
                    archive.write(file, os.path.relpath(file, folder))

def check_config(config: dict):
    """ Raise RuntimeError if a setting of the repo jobs in config.py is not valid """
    for name in ('REPO_JOB_TIMEOUT', 'REPO_MAX_JOBS', 'REPO_ZIP_RETENTION',
            'STUDENT_REPO_MAX_SIZE', 'PROFESSOR_REPO_CLONE_TIMEOUT', 'PROFESSOR_REPO_PULL_TIMEOUT',
            'PROFESSOR_REPO_MAX_SIZE'):
        value = config[name]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RuntimeError(f'{name} in config.py must be an integer greater than 0')
    hosts = config['REPO_ORIGIN_HOSTS']
    if not isinstance(hosts, list) or not all(isinstance(host, str) for host in hosts):
        raise RuntimeError('REPO_ORIGIN_HOSTS in config.py must be a list of host names')
