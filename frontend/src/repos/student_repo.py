""" Student repos: the git repo of each user with the solutions to the questions and problems that
they submit as students. Every user may be a student of courses made by other professors.

Each user has a bare repo, without working tree, in DATA_FOLDER/user/<username>/<STUDENT_REPO_NAME>
(student_repo by default). The solution of a problem has this logical path, which does not exist
on disk:

    <course>/<term_group>/<problem>/src/solution.c, tree.h, tree.c...

The src folder holds the files of the solution in each language, told apart by their extensions
(vyg.SOLUTION_EXTENSIONS), the main file of the language first (solution_filename()).

Each problem has a branch problems/<course>/<term_group>/<problem> with the linear history of its
solution, a commit per run with new code. The trees of its commits hold the full logical path, so
the branches of the problems are merged without conflicts into the main branch, which is made
when the repo is copied or pushed: its files are the last version of every solution, so it is the
working tree of the copies. The user may push the repo to a remote of their own (origin) """

import os
import re

from flask import current_app as app

import vyg
from repos.git_repo import COMMIT_PATTERN, GitRepo, check_ssh_url, user_folder

# Offering of the courses (e.g. 2026b05 is group 05 of the second term of 2026). Courses have
# sections in the database now (courses/course_section.py)
# TODO(jhc): use the year, term, and number of the section of the student (issue #95)
TERM_GROUP = '2026b01'
# Names of courses and problems (folders of the course repos, e.g. collatz_3n+1) and files of
# solutions. They are parts of refs and paths of git, so they cannot have dots, slashes, or spaces
NAME_PATTERN = re.compile(r'[A-Za-z0-9_+-]{1,64}')
# Characters of the names of sections that the messages of commits replace with _, and the length
# of those names in messages. Messages are not refs nor paths, but course repos are untrusted, so a
# section name cannot break the line of the message
SECTION_UNSAFE = re.compile(r'[^\w.+-]+')
SECTION_LENGTH = 64
# Action of the commits made by runs, after the path of the problem in their messages
RUN_ACTION = 'run'
# Line of the messages of the commits of runs with the names of their files in the order of the
# tabs of the editor, which git does not keep: trees sort the files by name
FILES_LINE = 'Files: '
FILENAME_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,64}\.[a-z0-9]{1,8}')
# Prefix of the refs of the branches of the problems
PROBLEMS_REFS = 'refs/heads/problems/'
# Branch that merges the branches of the problems, and message of its commits
MAIN_BRANCH = 'main'
MAIN_REF = f'refs/heads/{MAIN_BRANCH}'
MAIN_MESSAGE = 'Merge the solutions of the problems'
# Setting of the config of the repo with the URL of the remote of the user
ORIGIN_SETTING = 'remote.origin.url'
# What a push sends: main and the branches of the problems
PUSH_REFSPECS = (f'{MAIN_REF}:{MAIN_REF}', f'{PROBLEMS_REFS}*:{PROBLEMS_REFS}*')

class StudentRepo(GitRepo):
    """ The bare git repo with the solutions that a user submits as a student """

    def __init__(self, username: str):
        """ Find the folder of the repo from the username of the user """
        super().__init__(os.path.join(user_folder(username), app.config['STUDENT_REPO_NAME']))

    def save(self, problem: vyg.Problem, language: str, files: dict) -> bool:
        """ Commit the files of a run ({name: code}) as the solution of the problem in the
        language, at the end of its branch, unless the solution did not change. The files of the
        language that the solution no longer has are removed. Return whether a commit was made """
        self.create()
        course = problem.get_course().name
        branch = problem_branch(course, problem.name)
        folder = solution_folder(course, problem.name)
        old_names = (self.solution_files(branch, folder, language) if self.last_commit(branch)
            else [])
        return self.commit_files(branch,
            { solution_path(folder, name): code for name, code in files.items() },
            [solution_path(folder, name) for name in old_names if name not in files],
            f'{commit_message(problem, RUN_ACTION)}\n\n{FILES_LINE}{" ".join(files)}')

    def versions(self, course: str, problem: str, language: str) -> list:
        """ Return the versions of the solution of the problem in the language, the commits that
        changed its files, from the oldest to the newest, as [commit, time] pairs, with the time
        in seconds since the epoch """
        folder = solution_folder(course, problem)
        return self.file_versions(problem_branch(course, problem),
            [solution_path(folder, solution_filename(language))]
            + [f'{folder}/*.{extension}' for extension in vyg.SOLUTION_EXTENSIONS[language]])

    def last_problem(self, course: str) -> str | None:
        """ Return the name of the problem of the course whose solution got a version last, or
        None if the user has no solutions in the course """
        check_names(course)
        # The last part of the ref of the branch is the name of the problem
        return self.git('for-each-ref', '--sort=-committerdate', '--count=1',
            '--format=%(refname:lstrip=-1)', f'{PROBLEMS_REFS}{course}/{TERM_GROUP}/') or None

    def read(self, commit: str, course: str, problem: str, language: str) -> dict:
        """ Return the files of the solution of the problem in the language in the commit, as
        {name: code}, in the order of the tabs of its run (the main file first) """
        folder = solution_folder(course, problem)
        if not COMMIT_PATTERN.fullmatch(commit):
            raise ValueError('invalid commit')
        message = self.git('log', '-1', '--format=%B', commit).splitlines()
        order = next((line.removeprefix(FILES_LINE).split() for line in message
            if line.startswith(FILES_LINE)), [])
        names = sorted(self.solution_files(commit, folder, language),
            key=lambda name: order.index(name) if name in order else len(order))
        return { name: self.read_file(commit, solution_path(folder, name)) for name in names }

    def solution_files(self, commit: str, folder: str, language: str) -> list:
        """ Return the names of the files of the solution in the language in the folder of the
        commit (or the last commit of a branch), the main file first """
        extensions = vyg.SOLUTION_EXTENSIONS[language]
        main_file = solution_filename(language)
        names = [name for name in self.file_names(commit, folder)
            if name == main_file or name.rpartition('.')[2] in extensions]
        return sorted(names, key=lambda name: (name != main_file, name))

    def archive_solutions(self) -> bytes:
        """ Return a zip archive with the last version of the solution of every problem, in its
        logical path """
        self.create()
        return self.archive(PROBLEMS_REFS)

    def info(self) -> dict:
        """ Return the number of commits and problems of the repo, and the time of its last
        commit (None if it has none) """
        self.create()
        return {
            'commits': self.commit_count(PROBLEMS_REFS),
            'problems': len(self.refs(PROBLEMS_REFS)),
            'lastCommit': self.last_commit_time(PROBLEMS_REFS),
        }

    def version(self) -> str:
        """ Return an identifier of the solutions of the repo, which changes with each new version
        of a solution """
        return self.refs_version(PROBLEMS_REFS)

    def origin(self) -> str:
        """ Return the URL of the remote of the user, or an empty string if they have none """
        return self.get_config(ORIGIN_SETTING) or ''

    def set_origin(self, url: str) -> str:
        """ Set the remote of the user to the URL, or remove it if the URL is empty. Raise
        ValueError if it is not an SSH URL of the hosts of REPO_ORIGIN_HOSTS. Return the URL """
        self.create()
        url = url.strip() if isinstance(url, str) else ''
        if url:
            url = check_ssh_url(url, app.config['REPO_ORIGIN_HOSTS'])
        self.set_config(ORIGIN_SETTING, url or None)
        return url

    def build_main(self) -> str | None:
        """ Merge the new commits of the branches of the problems into the main branch, and make
        it the default branch. Return its last commit, or None if the repo has no solutions """
        commit = self.merge_branches(MAIN_REF, PROBLEMS_REFS, MAIN_MESSAGE)
        if commit:
            self.git('symbolic-ref', 'HEAD', MAIN_REF)
        return commit

    def copy_with_tree(self, folder: str, timeout: float) -> GitRepo:
        """ Copy the repo to the folder with the main branch in its working tree. Raise
        ValueError if the repo has no solutions """
        if not self.build_main():
            raise ValueError('empty repo')
        return self.copy_to(folder, MAIN_BRANCH, timeout)

    def push_to_origin(self, ssh_command: str, timeout: float) -> str:
        """ Push main and the branches of the problems to the remote of the user, with the given
        ssh command. Raise ValueError if the user has no valid remote or no solutions """
        # Checked again, in case the hosts of config.py changed since the user set it
        check_ssh_url(self.origin(), app.config['REPO_ORIGIN_HOSTS'])
        if not self.build_main():
            raise ValueError('empty repo')
        return self.push('origin', list(PUSH_REFSPECS), ssh_command, timeout)

def problem_branch(course: str, problem: str) -> str:
    """ Return the ref of the branch with the history of the solution of the problem """
    check_names(course, problem)
    return f'{PROBLEMS_REFS}{course}/{TERM_GROUP}/{problem}'

def solution_folder(course: str, problem: str) -> str:
    """ Return the logical path of the folder with the files of the solution of the problem """
    check_names(course, problem)
    return f'{course}/{TERM_GROUP}/{problem}/src'

def solution_path(folder: str, filename: str) -> str:
    """ Return the logical path of a file of the solution in its folder """
    if not FILENAME_PATTERN.fullmatch(filename):
        raise ValueError('invalid file name')
    return f'{folder}/{filename}'

def commit_message(problem: vyg.Problem, action: str) -> str:
    """ Return the message of a commit with the action on the solution of the problem: the path of
    the problem in the course, with its sections and subsections, and the action, e.g.
    CI0112/2026b01/1.1_intro_io/practice/sum_int: run """
    course = problem.get_course()
    sections = []
    parent = problem.get_parent()
    while parent and parent is not course:
        if parent.name:
            sections.append(SECTION_UNSAFE.sub('_', parent.name)[:SECTION_LENGTH])
        parent = parent.get_parent()
    path = '/'.join([course.name, TERM_GROUP, *reversed(sections), problem.name])
    return f'{path}: {action}'

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
