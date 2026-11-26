""" Professor repos: the git repos where professors write their courses, with external tools (e.g.
their editor and a Git host). A professor may have several repos, each one with one or more
courses listed in the configuration file of its root (vygoj.json, vygoj.yaml, info.json, or
info.yaml, see courses/course_config.py). VygOJ only reads them: the professor asks for a clone of
the main branch of each repo, and later for its changes (pull), in the Repositories section of the
home page. The courses found become prepared courses (courses/repo_course.py).

The clone of a repo is in DATA_FOLDER/user/<username>/<repo>, where <repo> is the last part of the
path of its URL, without .git (e.g. pexercises for git@github.com:jhc/pexercises.git). Its URL and
folder are rows of the professor_repos table. Clones and pulls run in background jobs
(repo_jobs.py), over SSH only, with the key of the user (ssh_key.py).

The sections (groups) of a course show the commit of the clone when they were offered or updated
(courses/course_section.py), while the professor goes on changing the main branch. Each of those
commits has a snapshot: a working tree of the clone (git worktree) without branch, in
DATA_FOLDER/user/<username>/snapshots/<repo>/<commit>, which shares the objects of the clone and
keeps the commit from being deleted by a pull that drops it (a push with force) """

import contextlib
import fcntl
import glob
import os
import re
import shutil
import tempfile

from flask import current_app as app
from sqlalchemy.exc import IntegrityError

from config_file import ConfigError
from courses.course_config import CourseConfig
from db import db
from repos.git_repo import (COMMIT_PATTERN, JOBS_FOLDER, MAX_URL_LENGTH, GitError, GitRepo,
    check_ssh_url, user_folder)
from repos.ssh_key import SSH_FOLDER
from users import User

# Repos that a professor may have, so a user cannot fill the disk with clones
MAX_PROFESSOR_REPOS = 20
# Folder of a clone: the last part of the path of its URL, without .git. It does not start with a
# dot, so it is never a hidden folder, . nor ..
FOLDER_PATTERN = re.compile(r'[A-Za-z0-9_][A-Za-z0-9._-]{0,63}')
# Branch of the repos that VygOJ clones and pulls, and ref of its copy from the remote
MAIN_BRANCH = 'main'
REMOTE_REF = f'refs/remotes/origin/{MAIN_BRANCH}'
# Prefix of the temporary folders of the clones, next to the folder of the repo
CLONE_PREFIX = '.clone-'
# Commands that reach a remote: only SSH (no local paths, file://, nor ext::), no submodules, and
# symbolic links checked out as plain files, so a link committed to a repo never points out of it
REMOTE_OPTIONS = ('-c', 'protocol.allow=never', '-c', 'protocol.ssh.allow=always',
    '-c', 'core.symlinks=false', '-c', 'submodule.recurse=false')
# Folder of the user with the snapshots of the commits of their repos that course sections show, a
# folder per repo with a folder per commit, and a lock file per repo
SNAPSHOTS_FOLDER = 'snapshots'
# Seconds to check out or remove a snapshot. A request waits for it, and gunicorn stops requests
# after 30 seconds
SNAPSHOT_TIMEOUT = 20
# Suffix of the folder where a snapshot is checked out, before it takes its name at once, so
# readers never see a snapshot half checked out
SNAPSHOT_PARTIAL = '.partial'
# Without the config of the user and system of the server, whose filters (e.g. git-lfs), URL
# rewrites, or credential helpers would run for repos written by others
REMOTE_ENV = { 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1' }

class CloneError(Exception):
    """ A clone or pull that cannot be done, with the code of its message """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

class ProfessorRepo(db.Model):
    """ A repo of a professor: its URL and the folder of its clone. Deleting the user deletes their
    repos, and their courses with them (courses/repo_course.py) """
    __tablename__ = 'professor_repos'
    # Two repos of a user never share the folder of their clones
    __table_args__ = (db.UniqueConstraint('user_id', 'folder'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False)
    # SSH URL of the repo in a Git host of REPO_ORIGIN_HOSTS, which the professor may change
    url = db.Column(db.String(MAX_URL_LENGTH), nullable=False)
    # Folder of the clone in the folder of the user, taken from the first URL. It never changes,
    # so the courses keep their files when the URL changes (e.g. the repo was renamed)
    folder = db.Column(db.String(64), nullable=False)
    user = db.relationship('User')

    @staticmethod
    def of_user(username: str) -> list:
        """ Return the repos of the user, in the order they were added """
        return db.session.scalars(db.select(ProfessorRepo).join(ProfessorRepo.user)
            .where(User.username == username).order_by(ProfessorRepo.id)).all()

    @staticmethod
    def find(username: str, repo_id: int) -> 'ProfessorRepo | None':
        """ Return the repo of the given id if it belongs to the user, or None """
        return db.session.scalar(db.select(ProfessorRepo).join(ProfessorRepo.user)
            .where(User.username == username, ProfessorRepo.id == repo_id))

    @staticmethod
    def add(username: str, url: str) -> 'ProfessorRepo':
        """ Add a repo of the user with the URL, and return it. Raise ValueError with the code of
        its message if the URL or its folder is not valid, also when another request added the
        folder meanwhile (e.g. a double click), or the user has too many repos """
        url = check_url(url)
        folder = folder_of(url)
        repos = ProfessorRepo.of_user(username)
        if len(repos) >= MAX_PROFESSOR_REPOS:
            raise ValueError('too_many')
        if any(repo.folder == folder for repo in repos):
            raise ValueError('duplicate_name')
        user_id = db.session.scalar(db.select(User.id).filter_by(username=username))
        repo = ProfessorRepo(user_id=user_id, url=url, folder=folder)
        db.session.add(repo)
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError('duplicate_name') from error
        return repo

    def set_url(self, url: str):
        """ Change the URL of the repo, which keeps its folder. Raise ValueError if it is not
        valid """
        self.url = check_url(url)
        db.session.commit()

    def clone(self) -> 'CourseRepo':
        """ Return the clone of the repo, which may not exist yet """
        return CourseRepo(os.path.join(user_folder(self.user.username), self.folder))

    def snapshot_path(self, commit: str) -> str:
        """ Return the folder of the snapshot of the commit, which may not exist yet. Raise
        ValueError if the commit is not a full hash """
        if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit):
            raise ValueError('invalid commit')
        return os.path.join(self.snapshots_folder(), self.folder, commit)

    def snapshots_folder(self) -> str:
        """ Return the folder with the snapshots of every repo of the user """
        return os.path.join(user_folder(self.user.username), SNAPSHOTS_FOLDER)

    def add_snapshot(self, commit: str) -> str:
        """ Return the folder of the snapshot of the commit, checked out from the clone if it does
        not exist yet. Raise CloneError if the repo has no clone, or GitError if git fails """
        path = self.snapshot_path(commit)
        if os.path.isdir(path):
            return path
        clone = self.clone()
        if not clone.is_clone():
            raise CloneError('no_clone')
        with self.snapshot_lock():
            # Another process may have made it while this one waited for the lock
            if os.path.isdir(path):
                return path
            partial = path + SNAPSHOT_PARTIAL
            # Left by a process that stopped while checking it out
            if os.path.lexists(partial):
                clone.remove_worktree(partial, SNAPSHOT_TIMEOUT)
            clone.add_worktree(partial, commit, SNAPSHOT_TIMEOUT)
            clone.move_worktree(partial, path, SNAPSHOT_TIMEOUT)
        return path

    def remove_snapshot(self, commit: str):
        """ Delete the snapshot of the commit, when no section shows it anymore """
        path = self.snapshot_path(commit)
        with self.snapshot_lock():
            if os.path.lexists(path):
                self.clone().remove_worktree(path, SNAPSHOT_TIMEOUT)

    @contextlib.contextmanager
    def snapshot_lock(self):
        """ Hold the lock of the snapshots of the repo, so the processes of gunicorn never check
        out the same snapshot at once, nor change the list of working trees of the clone """
        folder = self.snapshots_folder()
        os.makedirs(folder, mode=0o700, exist_ok=True)
        with open(os.path.join(folder, f'{self.folder}.lock'), 'a', encoding='utf-8') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

class CourseRepo(GitRepo):
    """ The clone of a professor repo, with the main branch in its working tree, where the course
    pages and problems read their files """

    def is_clone(self) -> bool:
        """ True if the folder has a clone with its working tree. A symbolic link is refused, so
        a pull never resets a folder out of the folder of the user """
        git_folder = os.path.join(self.path, '.git')
        return (not os.path.islink(self.path) and os.path.isdir(git_folder)
            and not os.path.islink(git_folder))

    def clone_from(self, url: str, ssh_command: str, timeout: float):
        """ Clone the main branch of the repo of the URL into the folder, which must not exist.
        The clone is made in a temporary folder and then moved, so a failed clone leaves nothing.
        Raise CloneError if the folder exists, or GitError if git fails """
        if os.path.lexists(self.path):
            raise CloneError('folder_exists')
        parent, name = os.path.split(self.path)
        os.makedirs(parent, mode=0o700, exist_ok=True)
        # Clones of this repo interrupted before (e.g. the server restarted). Each repo runs one
        # job at a time, so none of them is running
        for stale in glob.glob(os.path.join(glob.escape(parent), f'{CLONE_PREFIX}{name}-*')):
            shutil.rmtree(stale, ignore_errors=True)
        with tempfile.TemporaryDirectory(dir=parent, prefix=f'{CLONE_PREFIX}{name}-') as folder:
            target = os.path.join(folder, name)
            # No template: hooks and other files of the template of the server are not copied
            GitRepo(folder).git(*REMOTE_OPTIONS, 'clone', '--quiet', '--no-tags',
                '--single-branch', f'--branch={MAIN_BRANCH}', '--no-recurse-submodules',
                '--template=', '--config=core.symlinks=false', '--', url, target,
                env={ **REMOTE_ENV, 'GIT_SSH_COMMAND': ssh_command }, timeout=timeout)
            os.rename(target, self.path)

    def pull_from(self, url: str, ssh_command: str, timeout: float) -> str:
        """ Bring the main branch of the repo of the URL, and make the working tree hold it as it
        is in the remote: commits that it lost (a push with force) and files that are not in it
        are dropped, since the clone is only read. Return the commit before the pull. Raise
        CloneError if the folder is not a clone, or GitError if git fails """
        if not self.is_clone():
            raise CloneError('folder_exists')
        old_commit = self.head()
        self.set_config('remote.origin.url', url)
        self.git(*REMOTE_OPTIONS, 'fetch', '--quiet', '--no-tags', '--no-recurse-submodules',
            'origin', f'+refs/heads/{MAIN_BRANCH}:{REMOTE_REF}',
            env={ **REMOTE_ENV, 'GIT_SSH_COMMAND': ssh_command }, timeout=timeout)
        self.check_out(REMOTE_REF, timeout)
        return old_commit

    def revert(self, commit: str, timeout: float):
        """ Go back to the commit, from before a pull, and delete the objects that the pull
        brought, so they free their space """
        self.git('update-ref', REMOTE_REF, commit, timeout=timeout)
        self.check_out(commit, timeout)
        self.git('reflog', 'expire', '--expire=now', '--all', timeout=timeout)
        self.git('gc', '--quiet', '--prune=now', timeout=timeout)

    def check_out(self, commit: str, timeout: float):
        """ Make the main branch point to the commit, with its files in the working tree, and
        remove the files that are not in it """
        self.git('-c', 'core.symlinks=false', 'checkout', '--quiet', '--force', '-B', MAIN_BRANCH,
            commit, timeout=timeout)
        self.git('clean', '-ffdxq', timeout=timeout)

    def add_worktree(self, path: str, commit: str, timeout: float):
        """ Check out the commit in a new working tree of the clone in the folder, which must not
        exist, without branch, and with symbolic links as plain files, as the clone. The folder is
        made by the server, never by users """
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        self.git(*REMOTE_OPTIONS, 'worktree', 'add', '--quiet', '--detach', path, commit,
            env=REMOTE_ENV, timeout=timeout)

    def move_worktree(self, path: str, new_path: str, timeout: float):
        """ Rename the folder of a working tree of the clone, which git keeps in its list """
        self.git('worktree', 'move', path, new_path, timeout=timeout)

    def remove_worktree(self, path: str, timeout: float):
        """ Delete a working tree of the clone. If git cannot (e.g. the clone or the folder is
        gone), the folder is deleted, and the clone forgets the working trees without folder """
        try:
            self.git('worktree', 'remove', '--force', '--force', path, timeout=timeout)
        except GitError:
            shutil.rmtree(path, ignore_errors=True)
            if self.is_clone():
                self.git('worktree', 'prune', timeout=timeout)

    def head(self) -> str:
        """ Return the commit of the working tree """
        return self.git('rev-parse', 'HEAD')

    def remove(self):
        """ Delete the clone """
        shutil.rmtree(self.path)

    def read_catalog(self) -> dict:
        """ Return the courses of the configuration file of the root (courses/course_config.py), as
        {key: course}. Raise CloneError if it has none (no_catalog), or the file is too big or not
        a valid object (invalid_catalog) """
        try:
            catalog = CourseConfig(self.path).load(self.path)
        except ConfigError as error:
            raise CloneError('invalid_catalog') from error
        if catalog is None:
            raise CloneError('no_catalog')
        return catalog

def check_url(url: str) -> str:
    """ Return the URL of a professor repo without surrounding spaces. Raise ValueError if it is
    not an SSH URL of the hosts of REPO_ORIGIN_HOSTS """
    try:
        return check_ssh_url(url, app.config['REPO_ORIGIN_HOSTS'])
    except ValueError as error:
        raise ValueError('invalid_url') from error

def folder_of(url: str) -> str:
    """ Return the folder of the clone of a valid URL: the last part of its path, without .git.
    Raise ValueError if it is not a valid name, or it is the name of another folder of the user
    (their student repo, SSH key, jobs, or snapshots), so the professor must rename the repo """
    folder = url.rstrip('/').rpartition('/')[2].rpartition(':')[2].removesuffix('.git')
    if not FOLDER_PATTERN.fullmatch(folder):
        raise ValueError('invalid_name')
    if folder in (app.config['STUDENT_REPO_NAME'], SSH_FOLDER, JOBS_FOLDER, SNAPSHOTS_FOLDER):
        raise ValueError('reserved_name')
    return folder
