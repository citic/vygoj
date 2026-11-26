""" Sections (groups) of courses: the offers of the courses of professor repos, with their students.
When a professor offers a prepared course (courses/repo_course.py), they fill the form of a new
section: its duration, weeks, year, term, dates, institution, campus, number, modality of study,
methods of enrollment, and cost. The section shows the commit of the course when it was offered,
while the professor goes on changing the main branch of the repo, until they update it. Students
enroll in a section, not in a course, and in only one section of each course, so /course/<name>
shows them the commit of their section. Offered sections with self-enrollment are in the Available
courses of every user while their end and archive dates have not passed, and users enroll in them
from their start date """

import datetime

from flask_babel import lazy_gettext
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from db import db
from courses.repo_course import RepoCourse, now
from repos.professor_repo import ProfessorRepo

# Durations of the sections, from the shortest, as {value: name}
DURATIONS = {
    'intensive': lazy_gettext('Intensive or short'),
    'monthly': lazy_gettext('Monthly'),
    'two_months': lazy_gettext('Two months'),
    'quarter': lazy_gettext('Quarter'),
    'four_months': lazy_gettext('Four months'),
    'semester': lazy_gettext('Semester'),
    'annual': lazy_gettext('Annual'),
    'indefinite': lazy_gettext('Indefinite'),
}
# Weeks that the form suggests for each duration, the longest of its range: intensive 1 to 4,
# quarter 10 to 12, four months 14 to 16, semester 16 to 20, annual 30 to 40. Professors change
# them (e.g. semesters of 16 weeks), and the form estimates the end date (start date plus the
# weeks) and the archive date (twice them) from them. Indefinite sections have no weeks
DURATION_WEEKS = { 'intensive': 4, 'monthly': 4, 'two_months': 8, 'quarter': 12,
    'four_months': 16, 'semester': 20, 'annual': 40 }
# Range of the weeks of a section
MIN_WEEKS, MAX_WEEKS = 1, 60
# Terms of a year. A section may have none, e.g. an annual or indefinite one
TERMS = ('I', 'II', 'III')
# Modalities of study, as {value: (short name, long name)}
MODALITIES = {
    'regular': (lazy_gettext('Regular'), lazy_gettext('Regular (lessons with a professor)')),
    'tutoring': (lazy_gettext('Tutoring'), lazy_gettext('Tutoring (individual follow-up)')),
    'challenge': (lazy_gettext('Challenge exam'),
        lazy_gettext('Challenge exam (students already master the subject and take an exam)')),
    'adaptive': (lazy_gettext('Adaptive'),
        lazy_gettext('Adaptive (self-study with scheduled exams)')),
    'self_paced': (lazy_gettext('Self-paced'),
        lazy_gettext('Self-paced (at their own pace, without mediation)')),
}
# Range of the years and numbers of the sections
MIN_YEAR, MAX_YEAR = 2000, 2100
MIN_NUMBER, MAX_NUMBER = 1, 999
# Longest institution and campus names, and largest cost (the column has 12 digits, 2 of them
# decimals)
MAX_INSTITUTION_LENGTH = 128
MAX_CAMPUS_LENGTH = 64
MAX_COST = 10 ** 10 - 1
# Name of the constraint of the unique numbers of the sections, which manage.py updates
UNIQUE_NUMBER = 'course_sections_number_key'
# Sections that a course may have, so a professor cannot fill the database nor the disk with
# snapshots of commits (repos/professor_repo.py)
MAX_SECTIONS_PER_COURSE = 100

class CourseSection(db.Model):
    """ A section (group) of a course, where students enroll """
    __tablename__ = 'course_sections'
    # Two sections of a course in the same term, institution, and campus never share their number
    __table_args__ = (db.UniqueConstraint('course_id', 'year', 'term', 'institution', 'campus',
        'number', name=UNIQUE_NUMBER),)
    id = db.Column(db.Integer, primary_key=True)
    # Deleting the course (its repo or its user) deletes its sections
    course_id = db.Column(db.Integer, db.ForeignKey('repo_courses.id', ondelete='CASCADE'),
        nullable=False)
    # A key of DURATIONS, and its weeks, None if indefinite
    duration = db.Column(db.String(16), nullable=False)
    weeks = db.Column(db.Integer)
    year = db.Column(db.Integer, nullable=False)
    # One of TERMS, or empty
    term = db.Column(db.String(3), nullable=False, default='')
    # Optional dates. Without an end date, the section is available forever
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    archive_date = db.Column(db.Date)
    # Institution that offers the section and its campus (recinto), or empty
    institution = db.Column(db.String(MAX_INSTITUTION_LENGTH), nullable=False, default='')
    campus = db.Column(db.String(MAX_CAMPUS_LENGTH), nullable=False, default='')
    # Number of the section in the term, shown with 3 digits, e.g. 001
    number = db.Column(db.Integer, nullable=False)
    # A key of MODALITIES
    modality = db.Column(db.String(16), nullable=False)
    # Methods of enrollment, which do not exclude each other: students enroll themselves, with
    # the password if it has one, or the professor enrolls them
    self_enroll = db.Column(db.Boolean, nullable=False, default=True)
    # Hash of the password of self-enrollment, or None for a section without password
    password = db.Column(db.String(256))
    manual_enroll = db.Column(db.Boolean, nullable=False, default=False)
    # Cost in the currency, 0 if free. Payments are not implemented yet
    cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    currency = db.Column(db.String(3), nullable=False)
    # Commit of the course repo that the section shows
    commit = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    course = db.relationship('RepoCourse', back_populates='sections')

    @staticmethod
    def find(section_id: int) -> 'CourseSection | None':
        """ Return the section of the given id, or None """
        return db.session.get(CourseSection, section_id)

    @staticmethod
    def order() -> tuple:
        """ Return the order of the sections in the lists: by course, and the newest terms first """
        return (RepoCourse.name, CourseSection.year.desc(), CourseSection.term.desc(),
            CourseSection.institution, CourseSection.campus, CourseSection.number)

    @staticmethod
    def taught_by(user_id: int) -> list:
        """ Return the sections of the courses of the repos of the user, also of hidden courses """
        return db.session.scalars(db.select(CourseSection).join(RepoCourse).join(ProfessorRepo)
            .where(ProfessorRepo.user_id == user_id).order_by(*CourseSection.order())).all()

    @staticmethod
    def enrolled_by(user_id: int) -> list:
        """ Return the sections where the user is enrolled """
        return db.session.scalars(db.select(CourseSection).join(RepoCourse)
            .join(Enrollment, Enrollment.section_id == CourseSection.id)
            .where(Enrollment.user_id == user_id).order_by(*CourseSection.order())).all()

    @staticmethod
    def available_to(user_id: int) -> list:
        """ Return the open sections of the courses where the user is not enrolled """
        enrolled = db.select(Enrollment.course_id).where(Enrollment.user_id == user_id)
        return db.session.scalars(db.select(CourseSection).join(RepoCourse)
            .where(CourseSection.open_condition(), CourseSection.course_id.not_in(enrolled))
            .order_by(*CourseSection.order())).all()

    @staticmethod
    def open_condition():
        """ Return the SQL condition of the sections where users may enroll themselves: with
        self-enrollment, before their end date and archive date, if any """
        today = datetime.date.today()
        return db.and_(CourseSection.self_enroll.is_(True),
            db.or_(CourseSection.end_date.is_(None), CourseSection.end_date >= today),
            db.or_(CourseSection.archive_date.is_(None), CourseSection.archive_date > today))

    @staticmethod
    def of_student(course_id: int, user_id: int) -> 'CourseSection | None':
        """ Return the section of the course where the user is enrolled, or None """
        return db.session.scalar(db.select(CourseSection)
            .join(Enrollment, Enrollment.section_id == CourseSection.id)
            .where(Enrollment.course_id == course_id, Enrollment.user_id == user_id))

    @staticmethod
    def newest(course_id: int, open_only: bool) -> 'CourseSection | None':
        """ Return the last section offered of the course, or of its open ones if open_only, e.g.
        to show the card of the course to users who are not enrolled in it """
        query = db.select(CourseSection).where(CourseSection.course_id == course_id)
        if open_only:
            query = query.where(CourseSection.open_condition())
        return db.session.scalar(query.order_by(CourseSection.id.desc()).limit(1))

    @staticmethod
    def count(course_id: int) -> int:
        """ Return the number of sections of the course """
        return db.session.scalar(db.select(db.func.count()).select_from(CourseSection)
            .where(CourseSection.course_id == course_id))

    @staticmethod
    def shows_commit(repo_id: int, commit: str) -> bool:
        """ True if a section of a course of the repo shows the commit, so its snapshot is kept """
        return db.session.scalar(db.select(CourseSection.id).join(RepoCourse)
            .where(RepoCourse.repo_id == repo_id, CourseSection.commit == commit)
            .limit(1)) is not None

    @staticmethod
    def student_counts(sections: list) -> dict:
        """ Return the number of students enrolled in each section, as {section id: number} """
        ids = [section.id for section in sections]
        if not ids:
            return {}
        rows = db.session.execute(db.select(Enrollment.section_id, db.func.count())
            .where(Enrollment.section_id.in_(ids)).group_by(Enrollment.section_id))
        return dict(rows.all())

    def is_open(self) -> bool:
        """ True if users may enroll themselves in the section now (see open_condition()) """
        today = datetime.date.today()
        return bool(self.self_enroll and (self.end_date is None or self.end_date >= today)
            and (self.archive_date is None or self.archive_date > today))

    def has_started(self) -> bool:
        """ True if the start date of the section, if any, has come, so users may enroll """
        return self.start_date is None or self.start_date <= datetime.date.today()

    def place(self) -> str:
        """ Return the institution and campus of the section, e.g. 'UCR, Sede Rodrigo Facio' """
        return ', '.join(part for part in (self.institution, self.campus) if part)

    def set_password(self, password: str | None):
        """ Store the hash of the password of self-enrollment, or remove it if None or empty """
        self.password = generate_password_hash(password) if password else None

    def check_password(self, password: str) -> bool:
        """ True if the section has no password, or the given one is its password """
        return self.password is None or check_password_hash(self.password, password or '')

    def enroll(self, user_id: int) -> bool:
        """ Enroll the user in the section. Return False if they were enrolled in a section of its
        course already, also by another request meanwhile, e.g. a double click """
        if CourseSection.of_student(self.course_id, user_id):
            return False
        db.session.add(Enrollment(user_id=user_id, course_id=self.course_id, section_id=self.id))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return False
        return True

    def code(self) -> str:
        """ Return the number of the section with 3 digits, e.g. 001 """
        return f'{self.number:03d}'

    def period(self) -> str:
        """ Return the year and term of the section, e.g. 2026-I, or the year without term """
        return f'{self.year}-{self.term}' if self.term else str(self.year)

    def values(self) -> dict:
        """ Return the fields of the section that the professor fills, for the activity log, with
        dates as text, and whether it has a password instead of its hash """
        values = { name: getattr(self, name) for name in SECTION_FIELDS }
        values.update({ name: value.isoformat() for name, value in values.items()
            if isinstance(value, datetime.date) })
        values['cost'] = str(self.cost)
        values['password'] = self.password is not None
        return values

def taken_numbers(section: CourseSection, numbers: list) -> list:
    """ Return the numbers of the given ones that other sections of the course of the section have
    in its year, term, institution, and campus """
    return db.session.scalars(db.select(CourseSection.number).where(
        CourseSection.course_id == section.course_id, CourseSection.year == section.year,
        CourseSection.term == section.term, CourseSection.institution == section.institution,
        CourseSection.campus == section.campus, CourseSection.number.in_(numbers))
        .order_by(CourseSection.number)).all()

# Fields of a section that its form fills, in the order of the form
SECTION_FIELDS = ('duration', 'weeks', 'year', 'term', 'start_date', 'end_date', 'archive_date',
    'institution', 'campus', 'number', 'modality', 'self_enroll', 'manual_enroll', 'cost',
    'currency')

class Enrollment(db.Model):
    """ A student enrolled in a section. A user enrolls in only one section of each course, so the
    course is kept too, and the database refuses a second section of the same course """
    __tablename__ = 'enrollments'
    __table_args__ = (db.UniqueConstraint('user_id', 'course_id'),)
    id = db.Column(db.Integer, primary_key=True)
    # Deleting the user, the course, or the section deletes their enrollments
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('repo_courses.id', ondelete='CASCADE'),
        nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id', ondelete='CASCADE'),
        nullable=False, index=True)
    enrolled_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)

    @staticmethod
    def course_counts(course_ids: list) -> dict:
        """ Return the number of students enrolled in each course, in any of its sections, as
        {course id: number} """
        if not course_ids:
            return {}
        rows = db.session.execute(db.select(Enrollment.course_id, db.func.count())
            .where(Enrollment.course_id.in_(course_ids)).group_by(Enrollment.course_id))
        return dict(rows.all())
