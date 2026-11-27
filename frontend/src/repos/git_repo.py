""" Git repos of the users, kept in their folders of DATA_FOLDER:

    user/<username>/<STUDENT_REPO_NAME>    # student repo, see student_repo.py
    user/<username>/<repo>                 # clones of the repos of professors with their
                                           # courses, see professor_repo.py

GitRepo runs git on a repo with a timeout, and offers the operations that every kind of repo
needs: commit a file at the end of a branch, list the versions of a file, read a version, archive
the last files of some branches, copy the repo with a working tree, and push it to a remote. Files
are committed with the plumbing commands of git (hash-object, update-index on a temporary index,
write-tree, commit-tree, update-ref), which need no working tree, so they work on bare repos too.
Subclasses map their own concepts (e.g. courses and problems) to branches and paths, and validate
them """

import hashlib
import os
import re
import subprocess
import tempfile
import urllib.parse

from flask import current_app as app

# Seconds that a git command may take. Commands are local and their files small
GIT_TIMEOUT = 5
# Folder of DATA_FOLDER with a folder per user, and folder of the background jobs in the folder of
# each user (repo_jobs.py)
USERS_FOLDER = 'user'
JOBS_FOLDER = 'jobs'
# A commit given by the client, as the full hash of git
COMMIT_PATTERN = re.compile(r'[0-9a-f]{40}')
# Value of a ref that does not exist yet, for update-ref
NO_COMMIT = '0' * 40
# Maximum number of versions listed, the newest ones
MAX_VERSIONS = 1000
# Remotes that repos may push to, as SSH URLs, the only protocol allowed:
# ssh://[user@]host[:port]/path or user@host:path (scp syntax). Names start with a letter or digit,
# so no part is read as an option of ssh, and paths have no spaces nor characters of the shell
MAX_URL_LENGTH = 256
HOST = r'(?P<host>[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?)'
REMOTE_PATH = r'(?P<path>[A-Za-z0-9_~][A-Za-z0-9._~/-]{0,200})'
SSH_USER = r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}'
SSH_URL_PATTERNS = (
    re.compile(rf'ssh://(?:{SSH_USER}@)?{HOST}(?::[0-9]{{1,5}})?/{REMOTE_PATH}'),
    re.compile(rf'{SSH_USER}@{HOST}:{REMOTE_PATH}'),
)
# Every command: hooks of the repo never run, git never asks for a password, and commits have the
# judge as author, because the repo belongs to one user
GIT_OPTIONS = ('-c', 'core.hooksPath=/dev/null')
GIT_ENV = {
    'GIT_TERMINAL_PROMPT': '0',
    'GIT_AUTHOR_NAME': 'VygOJ', 'GIT_AUTHOR_EMAIL': 'vygoj@localhost',
    'GIT_COMMITTER_NAME': 'VygOJ', 'GIT_COMMITTER_EMAIL': 'vygoj@localhost',
}

class GitError(Exception):
    """ A git command that failed or took too long. stderr has the error output of git, for the
    log of the server and to tell the cause apart: it may have paths of the server, so it is never
    shown to users """

    def __init__(self, message: str, stderr: str = '', timed_out: bool = False):
        super().__init__(message)
        self.stderr = stderr
        self.timed_out = timed_out

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

    def commit_files(self, branch: str, files: dict, removed: list, message: str) -> bool:
        """ Commit the files ({path: content}) and remove the removed paths, at the end of the
        branch, unless nothing changed. Return whether a commit was made """
        old_commit = self.last_commit(branch)
        # The tree of the last commit with the new files. The index is temporary, because workers
        # of gunicorn may commit at the same time
        with tempfile.TemporaryDirectory() as folder:
            index = { 'GIT_INDEX_FILE': os.path.join(folder, 'index') }
            if old_commit:
                self.git('read-tree', old_commit, env=index)
            # A bare repo has no working tree for --force-remove: a line of mode 0 removes a path
            if removed:
                self.git('update-index', '-z', '--index-info', env=index,
                    stdin=''.join(f'0 {NO_COMMIT}\t{path}\0' for path in removed))
            for path, content in files.items():
                blob = self.git('hash-object', '-w', '--stdin', stdin=content)
                self.git('update-index', '--add', '--cacheinfo', f'100644,{blob},{path}',
                    env=index)
            tree = self.git('write-tree', env=index)
        if old_commit and tree == self.git('rev-parse', f'{old_commit}^{{tree}}'):
            return False
        parent = ('-p', old_commit) if old_commit else ()
        commit = self.git('commit-tree', tree, *parent, '-m', message)
        # Moves the branch only if it is still in the old commit, so a worker never overwrites the
        # commit of another one
        self.git('update-ref', branch, commit, old_commit or NO_COMMIT)
        return True

    def file_versions(self, branch: str, paths: list) -> list:
        """ Return the versions of the files of the given paths (which may have wildcards, e.g.
        src/*.c) in the branch, from the oldest to the newest, as [commit, time] pairs, with the
        time in seconds since the epoch """
        if not self.last_commit(branch):
            return []
        output = self.git('log', f'--max-count={MAX_VERSIONS}', '--reverse', '--format=%H %ct',
            branch, '--', *paths)
        return [[commit, int(time)] for commit, time in
            (line.split() for line in output.splitlines())]

    def read_file(self, commit: str, path: str) -> str:
        """ Return the content of the file of the given path in the commit, a full hash that may
        come from the client """
        if not COMMIT_PATTERN.fullmatch(commit):
            raise ValueError('invalid commit')
        return self.git('cat-file', 'blob', f'{commit}:{path}', strip=False)

    def file_names(self, commit: str, folder: str) -> list:
        """ Return the names of the files in the folder of the commit (or the last commit of a
        branch), without their folder """
        return [os.path.basename(path) for path in
            self.git('ls-tree', '--name-only', commit, f'{folder}/').splitlines()]

    def archive(self, refs_prefix: str) -> bytes:
        """ Return a zip archive with the files of the last commits of the branches whose refs
        start with the prefix (e.g. refs/heads/problems/) """
        return self.git('archive', '--format=zip', self.union_tree(self.refs(refs_prefix)),
            binary=True)

    def union_tree(self, branches: list) -> str:
        """ Return the tree with the files of the last commits of the branches. Their trees must
        have different paths: a temporary index joins them, and no working tree is needed """
        with tempfile.TemporaryDirectory() as folder:
            index = { 'GIT_INDEX_FILE': os.path.join(folder, 'index') }
            # ls-tree writes the files of a branch in the format that update-index reads
            files = ''.join(self.git('ls-tree', '-r', '-z', branch, strip=False)
                for branch in branches)
            if files:
                self.git('update-index', '-z', '--index-info', stdin=files, env=index)
            return self.git('write-tree', env=index)

    def refs(self, refs_prefix: str, not_merged_into: str = None) -> list:
        """ Return the refs that start with the prefix, optionally only the ones whose last commit
        is not in the history of the given commit """
        merged = (f'--no-merged={not_merged_into}',) if not_merged_into else ()
        return self.git('for-each-ref', '--format=%(refname)', *merged, refs_prefix).split()

    def merge_branches(self, target: str, refs_prefix: str, message: str) -> str | None:
        """ Make the target branch (e.g. refs/heads/main) hold the files of every branch of the
        prefix and their histories: a commit whose parents are the target and the branches that
        it does not have yet, so the target only moves forward, and pushes of it never need force.
        Return its last commit, or None if there are no branches """
        old_commit = self.last_commit(target)
        branches = self.refs(refs_prefix, old_commit)
        if not branches:
            return old_commit
        tree = self.union_tree(self.refs(refs_prefix))
        parents = [old_commit] if old_commit else []
        parents += [self.git('rev-parse', branch) for branch in branches]
        commit = self.git('commit-tree', tree, *(arg for parent in parents
            for arg in ('-p', parent)), '-m', message)
        self.git('update-ref', target, commit, old_commit or NO_COMMIT)
        return commit

    def refs_version(self, refs_prefix: str) -> str:
        """ Return an identifier of the last commits of the branches of the prefix, which changes
        when a branch gets a commit, or is added or removed """
        refs = self.git('for-each-ref', '--format=%(objectname) %(refname)', refs_prefix)
        return hashlib.sha256(refs.encode()).hexdigest()[:16]

    def commit_count(self, refs_prefix: str) -> int:
        """ Return the number of commits in the histories of the branches of the prefix """
        branches = self.refs(refs_prefix)
        if not branches:
            return 0
        return int(self.git('rev-list', '--count', '--stdin', stdin='\n'.join(branches)))

    def last_commit_time(self, refs_prefix: str) -> int | None:
        """ Return the time of the newest commit of the branches of the prefix, in seconds since
        the epoch, or None if there are no branches """
        time = self.git('for-each-ref', '--sort=-committerdate', '--count=1',
            '--format=%(committerdate:unix)', refs_prefix)
        return int(time) if time else None

    def size(self) -> int:
        """ Return the bytes of the files of the repo """
        return sum(os.path.getsize(os.path.join(folder, name))
            for folder, _, names in os.walk(self.path) for name in names)

    def copy_to(self, folder: str, branch: str, timeout: float) -> 'GitRepo':
        """ Copy the branches of the repo to a new repo in the folder, with the branch of the given
        name (e.g. main) in its working tree, and return it. The copy has no remote nor log of
        where its commits came from, so it does not reveal the path of this repo in the server """
        os.makedirs(folder)
        copy = GitRepo(folder)
        # No template: hooks and other files of the template of the server are not copied
        copy.git('init', '--quiet', '--template=', f'--initial-branch={branch}')
        # The branch of the working tree does not exist yet, so the fetch may create it
        copy.git('-c', 'core.logAllRefUpdates=false', 'fetch', '--quiet', '--no-tags',
            '--update-head-ok', self.path, 'refs/heads/*:refs/heads/*', timeout=timeout)
        os.remove(os.path.join(folder, '.git', 'FETCH_HEAD'))
        copy.git('-c', 'core.logAllRefUpdates=false', 'reset', '--quiet', '--hard',
            timeout=timeout)
        return copy

    def push(self, remote: str, refspecs: list, ssh_command: str, timeout: float) -> str:
        """ Push the refspecs to the remote over SSH only, without force, and all of them or none
        (--atomic). Other protocols (file, ext...) are refused, so a remote cannot read or run
        anything in the server. Return the output of git """
        return self.git('-c', 'protocol.allow=never', '-c', 'protocol.ssh.allow=always', 'push',
            '--porcelain', '--atomic', remote, *refspecs, env={ 'GIT_SSH_COMMAND': ssh_command },
            timeout=timeout)

    def get_config(self, name: str) -> str | None:
        """ Return the value of the setting of the config of the repo, or None if it is not set """
        try:
            return self.git('config', '--get', name)
        except GitError:
            return None

    def set_config(self, name: str, value: str | None):
        """ Set the setting of the config of the repo, or remove it if value is None """
        if value is not None:
            self.git('config', name, value)
        elif self.get_config(name) is not None:
            self.git('config', '--unset', name)

    def last_commit(self, branch: str) -> str:
        """ Return the commit at the end of the branch, or None if it does not exist """
        return self.git('for-each-ref', '--format=%(objectname)', branch) or None

    def git(self, *args, stdin: str = None, env: dict = None, strip: bool = True,
            binary: bool = False, timeout: float = GIT_TIMEOUT) -> str | bytes:
        """ Run the git command in the repo and return its output, as bytes if binary, or as text
        without the final newline if strip. Texts are bytes, so files keep their line endings.
        Raise GitError if it fails or takes more than the timeout in seconds """
        # Name of the command for the errors: the first argument that is not an option of git
        command = next((arg for arg in args if not arg.startswith('-') and '=' not in arg), '')
        try:
            process = subprocess.run(['git', *GIT_OPTIONS, '-C', self.path, *args],
                input=stdin.encode() if stdin is not None else None, capture_output=True,
                timeout=timeout, check=False, env={ **os.environ, **GIT_ENV, **(env or {}) })
        except subprocess.TimeoutExpired as error:
            raise GitError(f'git {command} timed out', timed_out=True) from error
        except OSError as error:
            raise GitError(f'git {command} failed') from error
        if process.returncode != 0:
            stderr = process.stderr.decode(errors='replace')
            raise GitError(f'git {command} failed: {stderr}', stderr)
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

def check_ssh_url(url: str, hosts: list) -> str:
    """ Return the URL of a remote given by a user, without surrounding spaces, if it is an SSH URL
    of one of the hosts (e.g. github.com). Otherwise raise ValueError. Only known hosts are
    accepted, so users cannot make the server connect to other computers, e.g. of its network """
    url = url.strip() if isinstance(url, str) else ''
    match = next((match for pattern in SSH_URL_PATTERNS
        if len(url) <= MAX_URL_LENGTH and (match := pattern.fullmatch(url))), None)
    if (not match or '..' in match['path'].split('/')
            or match['host'].lower() not in (host.lower() for host in hosts)):
        raise ValueError('invalid remote URL')
    return url
