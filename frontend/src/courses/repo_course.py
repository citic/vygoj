""" Courses of the professor repos in the database. A course is in version control: its contents are
in the clone of a professor repo (repos/professor_repo.py). The database has a row for each course
found in the configuration file of a repo, with the repo that has it and its state, and the
professor offers it in one or more sections (groups, courses/course_section.py):

- Prepared: found in the configuration file of the main branch of its repo by its last clone or
  pull. Only the professor who owns the repo sees it in the home page, enters it to review it,
  and offers it in sections, as many as they want.
- Hidden: a course that is not in the configuration file of its repo anymore, but has sections.
  Its sections keep showing the commit where they were offered, until a pull finds it again.

Course names are unique in the judge, because routes (/course/<name>), progress, and student repos
identify courses by name. A course whose name another repo has already is skipped """

import datetime

import vyg
from db import db
from repos.professor_repo import ProfessorRepo
from repos.student_repo import NAME_PATTERN

# Names of courses with another name that a sync reports, so a repo with many of them cannot make
# a large state of its job
MAX_REPORTED_NAMES = 20

def now() -> datetime.datetime:
    """ Return the current time in UTC """
    return datetime.datetime.now(datetime.timezone.utc)

class RepoCourse(db.Model):
    """ A course of the main branch of a professor repo, which the professor offers in sections """
    __tablename__ = 'repo_courses'
    id = db.Column(db.Integer, primary_key=True)
    # Name of the course in vygoj.json, e.g. 'CI0112'
    name = db.Column(db.String(64), unique=True, nullable=False)
    # The repo that has the course. Deleting the repo (or its user) deletes the course, with its
    # sections and their enrollments
    repo_id = db.Column(db.Integer, db.ForeignKey('professor_repos.id', ondelete='CASCADE'),
        nullable=False)
    # Commit of the clone when the course was last found, so the workers of gunicorn notice that a
    # pull changed it and load it again. New sections show this commit
    commit = db.Column(db.String(64), nullable=False)
    # A course with sections that its repo does not have anymore
    hidden = db.Column(db.Boolean, nullable=False, default=False)
    repo = db.relationship('ProfessorRepo')
    # The database deletes the sections with the course
    sections = db.relationship('CourseSection', back_populates='course', passive_deletes=True)

    @staticmethod
    def find(name: str) -> 'RepoCourse | None':
        """ Return the course of the given name, or None """
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            return None
        return db.session.scalar(db.select(RepoCourse).filter_by(name=name))

    @staticmethod
    def prepared_by(user_id: int) -> list:
        """ Return the visible courses of the repos of the user, by name """
        return db.session.scalars(db.select(RepoCourse).join(ProfessorRepo)
            .where(ProfessorRepo.user_id == user_id, RepoCourse.hidden.is_(False))
            .order_by(RepoCourse.name)).all()

    @staticmethod
    def all_courses() -> list:
        """ Return every course, also the hidden ones, by name """
        return db.session.scalars(db.select(RepoCourse).order_by(RepoCourse.name)).all()

    def owned_by(self, user_id: int) -> bool:
        """ True if the course is in a repo of the user """
        return self.repo.user_id == user_id

def parse_courses(catalog: dict, folder: str) -> tuple:
    """ Return the valid courses of the catalog of a repo (the object of its configuration file),
    with the files in the folder, as {name: vyg.Course}, and the number of courses that are not
    valid: their contents are not a valid tree of materials, or their names are not valid or
    repeated """
    courses, invalid = {}, 0
    for contents in catalog.values():
        try:
            course = vyg.Course(contents, folder)
        # Repos are written by professors, so any error of their contents skips the course, never
        # the others nor the job
        except Exception: # pylint: disable=broad-exception-caught
            invalid += 1
            continue
        if (not isinstance(course.name, str) or not NAME_PATTERN.fullmatch(course.name)
                or course.name in courses):
            invalid += 1
            continue
        courses[course.name] = course
    return courses, invalid

def sync_courses(repo: ProfessorRepo, names: list, commit: str) -> list:
    """ Make the courses of the repo be the ones of the given names, found in its commit: new
    courses are prepared, the others get the commit, and the missing ones are deleted, or hidden if
    they have sections. Return the names that other repos have already, which are skipped """
    courses = { course.name: course for course in db.session.scalars(
        db.select(RepoCourse).where(RepoCourse.name.in_(names)
            | (RepoCourse.repo_id == repo.id))) }
    skipped = []
    for name in names:
        course = courses.get(name)
        if course is None:
            db.session.add(RepoCourse(name=name, repo_id=repo.id, commit=commit))
        elif course.repo_id != repo.id:
            skipped.append(name)
        else:
            course.commit, course.hidden = commit, False
    for name, course in courses.items():
        if course.repo_id == repo.id and name not in names:
            if course.sections:
                course.hidden = True
            else:
                db.session.delete(course)
    db.session.commit()
    return skipped[:MAX_REPORTED_NAMES]
