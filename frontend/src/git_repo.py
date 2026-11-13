""" Personal git repos of the users, with the history of their solutions.

Each user has a bare repo, without working tree, in DATA_FOLDER/u<username>/<PERSONAL_REPO_NAME>.
The solution of a problem has this logical path, which does not exist on disk:

    <course>/<term_group>/<problem>/src/solution.c

Each problem has a branch problems/<course>/<term_group>/<problem> with the linear history of its
solution, a commit per run with new code. The trees of its commits hold the full logical path, so
the branches of the problems can be merged later without conflicts. Files are committed with the
plumbing commands of git (hash-object, update-index on a temporary index, write-tree, commit-tree,
update-ref), which need no working tree """

import os
import re
import subprocess
import tempfile
import urllib.parse

from flask import current_app as app

import vyg

# Seconds that a git command may take. Commands are local and their files small
GIT_TIMEOUT = 5
# Offering of the courses (e.g. 2026b05 is group 05 of the second term of 2026), until courses
# have offerings in the database
TERM_GROUP = '2026b01'
# Names of courses and problems (folders of the course repos, e.g. collatz_3n+1) and files of
# solutions. They are parts of refs and paths of git, so they cannot have dots, slashes, or spaces
NAME_PATTERN = re.compile(r'[A-Za-z0-9_+-]{1,64}')
FILENAME_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,64}\.[a-z0-9]{1,8}')
# A commit given by the client, as the full hash of git
COMMIT_PATTERN = re.compile(r'[0-9a-f]{40}')
# Value of a ref that does not exist yet, for update-ref
NO_COMMIT = '0' * 40
# Maximum number of versions listed, the newest ones
MAX_VERSIONS = 1000
# Every command: hooks of the repo never run, git never asks for a password, and commits have the
# judge as author, because the repo belongs to one user
GIT_OPTIONS = ('-c', 'core.hooksPath=/dev/null')
GIT_ENV = {
    'GIT_TERMINAL_PROMPT': '0',
    'GIT_AUTHOR_NAME': 'VygOJ', 'GIT_AUTHOR_EMAIL': 'vygoj@localhost',
    'GIT_COMMITTER_NAME': 'VygOJ', 'GIT_COMMITTER_EMAIL': 'vygoj@localhost',
}

class GitError(Exception):
    """ A git command that failed or took too long """

class PersonalRepo:
    """ The bare git repo with the solutions of a user """

    def __init__(self, username: str):
        """ Find the folder of the repo from the username of the user """
        # Path of the bare repo: DATA_FOLDER/u<username>/<PERSONAL_REPO_NAME>
        self.path = os.path.join(user_folder(username), app.config['PERSONAL_REPO_NAME'])

    def create(self):
        """ Create the repo if it does not exist """
        if not os.path.isfile(os.path.join(self.path, 'HEAD')):
            os.makedirs(self.path, exist_ok=True)
            self.git('init', '--quiet', '--bare')

    def save(self, course: str, problem: str, filename: str, code: str) -> bool:
        """ Commit the code as the file of the solution of the problem, at the end of its branch,
        unless the solution did not change. Return whether a commit was made """
        self.create()
        branch = problem_branch(course, problem)
        path = solution_path(course, problem, filename)
        old_commit = self.last_commit(branch)
        blob = self.git('hash-object', '-w', '--stdin', stdin=code)
        # The tree of the last commit with the new file. The index is temporary, because workers
        # of gunicorn may save at the same time
        with tempfile.TemporaryDirectory() as folder:
            index = { 'GIT_INDEX_FILE': os.path.join(folder, 'index') }
            if old_commit:
                self.git('read-tree', old_commit, env=index)
            self.git('update-index', '--add', '--cacheinfo', f'100644,{blob},{path}', env=index)
            tree = self.git('write-tree', env=index)
        if old_commit and tree == self.git('rev-parse', f'{old_commit}^{{tree}}'):
            return False
        parent = ('-p', old_commit) if old_commit else ()
        commit = self.git('commit-tree', tree, *parent, '-m', 'Run')
        # Moves the branch only if it is still in the old commit, so a worker never overwrites the
        # commit of another one
        self.git('update-ref', branch, commit, old_commit or NO_COMMIT)
        return True

    def versions(self, course: str, problem: str, filename: str) -> list:
        """ Return the versions of the file of the solution of the problem, from the oldest to the
        newest, as [commit, time] pairs, with the time in seconds since the epoch """
        branch = problem_branch(course, problem)
        if not self.last_commit(branch):
            return []
        output = self.git('log', f'--max-count={MAX_VERSIONS}', '--reverse', '--format=%H %ct',
            branch, '--', solution_path(course, problem, filename))
        return [[commit, int(time)] for commit, time in
            (line.split() for line in output.splitlines())]

    def read(self, commit: str, course: str, problem: str, filename: str) -> str:
        """ Return the code of the file of the solution of the problem in the commit """
        if not COMMIT_PATTERN.fullmatch(commit):
            raise ValueError('invalid commit')
        return self.git('cat-file', 'blob', f'{commit}:{solution_path(course, problem, filename)}',
            strip=False)

    def last_commit(self, branch: str) -> str:
        """ Return the commit at the end of the branch, or None if it does not exist """
        return self.git('for-each-ref', '--format=%(objectname)', branch) or None

    def git(self, *args, stdin: str = None, env: dict = None, strip: bool = True) -> str:
        """ Run the git command in the repo and return its output, without the final newline if
        strip. Texts are bytes, so the code keeps its line endings. Raise GitError if it fails """
        try:
            process = subprocess.run(['git', *GIT_OPTIONS, '-C', self.path, *args],
                input=stdin.encode() if stdin is not None else None, capture_output=True,
                timeout=GIT_TIMEOUT, check=False, env={ **os.environ, **GIT_ENV, **(env or {}) })
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GitError(f'git {args[0]} failed') from error
        if process.returncode != 0:
            raise GitError(f'git {args[0]} failed: {process.stderr.decode(errors="replace")}')
        output = process.stdout.decode(errors='replace')
        return output.rstrip('\n') if strip else output

def user_folder(username: str) -> str:
    """ Return the folder of the user in DATA_FOLDER, u<username>, e.g. ue14 for the user e14.
    Usernames may be emails of single sign-on, so characters other than letters, digits, and
    @.+-_~ are encoded as in URLs (a/b is ua%2Fb): the folder has no slash, so it is always inside
    DATA_FOLDER, and two users never share it. The u keeps the names . and .. away """
    if not username:
        raise ValueError('empty username')
    folder = 'u' + urllib.parse.quote(username, safe='@.+-_~')
    return os.path.join(app.config['DATA_FOLDER'], folder)

def problem_branch(course: str, problem: str) -> str:
    """ Return the ref of the branch with the history of the solution of the problem """
    check_names(course, problem)
    return f'refs/heads/problems/{course}/{TERM_GROUP}/{problem}'

def solution_path(course: str, problem: str, filename: str) -> str:
    """ Return the logical path of the file of the solution of the problem """
    check_names(course, problem)
    if not FILENAME_PATTERN.fullmatch(filename):
        raise ValueError('invalid file name')
    return f'{course}/{TERM_GROUP}/{problem}/src/{filename}'

def check_names(*names: str):
    """ Raise ValueError if a name of a course or problem is not valid. Course repos validate them
    too: this check keeps the refs and paths of the repo safe if they did not """
    for name in names:
        if not NAME_PATTERN.fullmatch(name):
            raise ValueError(f'invalid name: {name!r}')

def solution_filename(language: str) -> str:
    """ Return the name of the file of a solution in the language, as the backend and the default
    code of static/initial name it: Java needs the public class Solution in Solution.java """
    if language == 'Java':
        return 'Solution.java'
    return f'solution.{vyg.EXTENSION_LANGUAGES[language]}'
