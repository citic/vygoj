""" Git repos of the users, kept in their folders of DATA_FOLDER:

    user/<username>/<STUDENT_REPO_NAME>    # student repo, see student_repo.py
    user/<username>/<repo>                 # repos of professors, with their courses

GitRepo runs git on a repo with a timeout, and offers the operations that every kind of repo
needs: commit a file at the end of a branch, list the versions of a file, read a version, and
archive the last files of some branches. Files are committed with the plumbing commands of git
(hash-object, update-index on a temporary index, write-tree, commit-tree, update-ref), which need
no working tree, so they work on bare repos too. Subclasses map their own concepts (e.g. courses
and problems) to branches and paths, and validate them """

import os
import re
import subprocess
import tempfile
import urllib.parse

from flask import current_app as app

# Seconds that a git command may take. Commands are local and their files small
GIT_TIMEOUT = 5
# Folder of DATA_FOLDER with a folder per user
USERS_FOLDER = 'user'
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

class GitRepo:
    """ A git repo in a folder of the server. Branches and paths given to its methods must be
    validated by the caller, because they come from names chosen by users """

    def __init__(self, path: str):
        """ Use the repo in the given folder, which may not exist yet """
        self.path = path

    def create(self):
        """ Create the repo as a bare repo, without working tree, if it does not exist """
        if not os.path.isfile(os.path.join(self.path, 'HEAD')):
            os.makedirs(self.path, exist_ok=True)
            self.git('init', '--quiet', '--bare')

    def commit_file(self, branch: str, path: str, content: str, message: str) -> bool:
        """ Commit the content as the file of the given path, at the end of the branch, unless the
        file did not change. Return whether a commit was made """
        old_commit = self.last_commit(branch)
        blob = self.git('hash-object', '-w', '--stdin', stdin=content)
        # The tree of the last commit with the new file. The index is temporary, because workers
        # of gunicorn may commit at the same time
        with tempfile.TemporaryDirectory() as folder:
            index = { 'GIT_INDEX_FILE': os.path.join(folder, 'index') }
            if old_commit:
                self.git('read-tree', old_commit, env=index)
            self.git('update-index', '--add', '--cacheinfo', f'100644,{blob},{path}', env=index)
            tree = self.git('write-tree', env=index)
        if old_commit and tree == self.git('rev-parse', f'{old_commit}^{{tree}}'):
            return False
        parent = ('-p', old_commit) if old_commit else ()
        commit = self.git('commit-tree', tree, *parent, '-m', message)
        # Moves the branch only if it is still in the old commit, so a worker never overwrites the
        # commit of another one
        self.git('update-ref', branch, commit, old_commit or NO_COMMIT)
        return True

    def file_versions(self, branch: str, path: str) -> list:
        """ Return the versions of the file of the given path in the branch, from the oldest to
        the newest, as [commit, time] pairs, with the time in seconds since the epoch """
        if not self.last_commit(branch):
            return []
        output = self.git('log', f'--max-count={MAX_VERSIONS}', '--reverse', '--format=%H %ct',
            branch, '--', path)
        return [[commit, int(time)] for commit, time in
            (line.split() for line in output.splitlines())]

    def read_file(self, commit: str, path: str) -> str:
        """ Return the content of the file of the given path in the commit, a full hash that may
        come from the client """
        if not COMMIT_PATTERN.fullmatch(commit):
            raise ValueError('invalid commit')
        return self.git('cat-file', 'blob', f'{commit}:{path}', strip=False)

    def archive(self, refs_prefix: str) -> bytes:
        """ Return a zip archive with the files of the last commits of the branches whose refs
        start with the prefix (e.g. refs/heads/problems/). Their trees must have different paths:
        a temporary index joins them, and no working tree is needed """
        branches = self.git('for-each-ref', '--format=%(refname)', refs_prefix).split()
        with tempfile.TemporaryDirectory() as folder:
            index = { 'GIT_INDEX_FILE': os.path.join(folder, 'index') }
            # ls-tree writes the files of a branch in the format that update-index reads
            files = ''.join(self.git('ls-tree', '-r', '-z', branch, strip=False)
                for branch in branches)
            if files:
                self.git('update-index', '-z', '--index-info', stdin=files, env=index)
            tree = self.git('write-tree', env=index)
        return self.git('archive', '--format=zip', tree, binary=True)

    def last_commit(self, branch: str) -> str:
        """ Return the commit at the end of the branch, or None if it does not exist """
        return self.git('for-each-ref', '--format=%(objectname)', branch) or None

    def git(self, *args, stdin: str = None, env: dict = None, strip: bool = True,
            binary: bool = False) -> str | bytes:
        """ Run the git command in the repo and return its output, as bytes if binary, or as text
        without the final newline if strip. Texts are bytes, so files keep their line endings.
        Raise GitError if it fails """
        try:
            process = subprocess.run(['git', *GIT_OPTIONS, '-C', self.path, *args],
                input=stdin.encode() if stdin is not None else None, capture_output=True,
                timeout=GIT_TIMEOUT, check=False, env={ **os.environ, **GIT_ENV, **(env or {}) })
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GitError(f'git {args[0]} failed') from error
        if process.returncode != 0:
            raise GitError(f'git {args[0]} failed: {process.stderr.decode(errors="replace")}')
        if binary:
            return process.stdout
        output = process.stdout.decode(errors='replace')
        return output.rstrip('\n') if strip else output

def user_folder(username: str) -> str:
    """ Return the folder of the user, with their repos: DATA_FOLDER/user/<username>, e.g.
    DATA_FOLDER/user/e14 for the user e14. Usernames may be emails of single sign-on, so
    characters other than letters, digits, and @.+-_~ are encoded as in URLs (a/b is a%2Fb): the
    folder has no slash, so it is always inside DATA_FOLDER/user, and two users never share it.
    The first dot of names that start with one is encoded too (.. is %2E.), so the folder of a
    user is never DATA_FOLDER/user nor DATA_FOLDER """
    if not username:
        raise ValueError('empty username')
    folder = urllib.parse.quote(username, safe='@.+-_~')
    if folder.startswith('.'):
        folder = '%2E' + folder[1:]
    return os.path.join(app.config['DATA_FOLDER'], USERS_FOLDER, folder)
