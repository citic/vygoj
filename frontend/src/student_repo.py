""" Student repos: the git repo of each user with the solutions to the questions and problems that
they submit as students. Every user may be a student of courses made by other professors.

Each user has a bare repo, without working tree, in DATA_FOLDER/user/<username>/<STUDENT_REPO_NAME>
(student_repo by default). The solution of a problem has this logical path, which does not exist
on disk:

    <course>/<term_group>/<problem>/src/solution.c

Each problem has a branch problems/<course>/<term_group>/<problem> with the linear history of its
solution, a commit per run with new code. The trees of its commits hold the full logical path, so
the branches of the problems can be merged later without conflicts """

import os
import re

from flask import current_app as app

import vyg
from git_repo import GitRepo, user_folder

# Offering of the courses (e.g. 2026b05 is group 05 of the second term of 2026), until courses
# have offerings in the database
TERM_GROUP = '2026b01'
# Names of courses and problems (folders of the course repos, e.g. collatz_3n+1) and files of
# solutions. They are parts of refs and paths of git, so they cannot have dots, slashes, or spaces
NAME_PATTERN = re.compile(r'[A-Za-z0-9_+-]{1,64}')
FILENAME_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,64}\.[a-z0-9]{1,8}')
# Prefix of the refs of the branches of the problems
PROBLEMS_REFS = 'refs/heads/problems/'

class StudentRepo(GitRepo):
    """ The bare git repo with the solutions that a user submits as a student """

    def __init__(self, username: str):
        """ Find the folder of the repo from the username of the user """
        super().__init__(os.path.join(user_folder(username), app.config['STUDENT_REPO_NAME']))

    def save(self, course: str, problem: str, filename: str, code: str) -> bool:
        """ Commit the code as the file of the solution of the problem, at the end of its branch,
        unless the solution did not change. Return whether a commit was made """
        self.create()
        return self.commit_file(problem_branch(course, problem),
            solution_path(course, problem, filename), code, 'Run')

    def versions(self, course: str, problem: str, filename: str) -> list:
        """ Return the versions of the file of the solution of the problem, from the oldest to the
        newest, as [commit, time] pairs, with the time in seconds since the epoch """
        return self.file_versions(problem_branch(course, problem),
            solution_path(course, problem, filename))

    def read(self, commit: str, course: str, problem: str, filename: str) -> str:
        """ Return the code of the file of the solution of the problem in the commit """
        return self.read_file(commit, solution_path(course, problem, filename))

    def archive_solutions(self) -> bytes:
        """ Return a zip archive with the last version of the solution of every problem, in its
        logical path """
        self.create()
        return self.archive(PROBLEMS_REFS)

def problem_branch(course: str, problem: str) -> str:
    """ Return the ref of the branch with the history of the solution of the problem """
    check_names(course, problem)
    return f'{PROBLEMS_REFS}{course}/{TERM_GROUP}/{problem}'

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
