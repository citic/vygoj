""" Course offers and enrollments in the database. A course is in version control: its contents are
in the clone of a professor repo (repos/professor_repo.py). Its offer is the instance of the course
in the judge, which keeps which repo has it and its state, and later will have groups (sections)
with their students:

- Prepared: found in the configuration file of a repo by its last clone or pull, but not offered
  yet. Only the professor who owns the repo sees it, in the home page, and enters it to review it.
- Offered: the professor offered it, so every user sees it in Available courses and may enroll.
- Hidden: an offered course that is not in the configuration file of its repo anymore. Nobody
  sees it, but it keeps its enrollments, until a pull finds it again.

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

class CourseOffer(db.Model):
    """ The offer of a course of a professor repo, prepared or offered """
    __tablename__ = 'course_offers'
    id = db.Column(db.Integer, primary_key=True)
    # Name of the course in vygoj.json, e.g. 'CI0112'
    # TODO(jhc): a course will have several offers (terms, groups), so names will be unique in
    # another level
    name = db.Column(db.String(64), unique=True, nullable=False)
    # The repo that has the course. Deleting the repo (or its user) deletes the offer
    repo_id = db.Column(db.Integer, db.ForeignKey('professor_repos.id', ondelete='CASCADE'),
        nullable=False)
    # Commit of the clone when the course was last found, so the workers of gunicorn notice that a
    # pull changed it and load it again
    commit = db.Column(db.String(64), nullable=False)
    # When the professor offered the course, or None while it is prepared
    offered_at = db.Column(db.DateTime(timezone=True))
    # An offered course that its repo does not have anymore
    hidden = db.Column(db.Boolean, nullable=False, default=False)
    repo = db.relationship('ProfessorRepo')

    @staticmethod
    def find(name: str) -> 'CourseOffer | None':
        """ Return the offer of the course of the given name, or None """
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            return None
        return db.session.scalar(db.select(CourseOffer).filter_by(name=name))

    @staticmethod
    def prepared_by(user_id: int) -> list:
        """ Return the visible offers of the courses of the repos of the user, offered or not, by
        name """
        return db.session.scalars(db.select(CourseOffer).join(ProfessorRepo)
            .where(ProfessorRepo.user_id == user_id, CourseOffer.hidden.is_(False))
            .order_by(CourseOffer.name)).all()

    @staticmethod
    def enrolled_by(user_id: int) -> list:
        """ Return the visible offers where the user is enrolled, by name """
        return db.session.scalars(db.select(CourseOffer).join(Enrollment)
            .where(Enrollment.user_id == user_id, CourseOffer.hidden.is_(False))
            .order_by(CourseOffer.name)).all()

    @staticmethod
    def available_to(user_id: int) -> list:
        """ Return the visible offered courses where the user is not enrolled, without the ones of
        their own repos, by name """
        enrolled = db.select(Enrollment.offer_id).where(Enrollment.user_id == user_id)
        return db.session.scalars(db.select(CourseOffer).join(ProfessorRepo)
            .where(CourseOffer.offered_at.is_not(None), CourseOffer.hidden.is_(False),
                ProfessorRepo.user_id != user_id, CourseOffer.id.not_in(enrolled))
            .order_by(CourseOffer.name)).all()

    @staticmethod
    def all_offers() -> list:
        """ Return every offer, also the prepared and hidden ones, by name """
        return db.session.scalars(db.select(CourseOffer).order_by(CourseOffer.name)).all()

    @staticmethod
    def student_counts(offers: list) -> dict:
        """ Return the number of students enrolled in each offer, as {offer id: number} """
        ids = [offer.id for offer in offers]
        if not ids:
            return {}
        rows = db.session.execute(db.select(Enrollment.offer_id, db.func.count())
            .where(Enrollment.offer_id.in_(ids)).group_by(Enrollment.offer_id))
        return dict(rows.all())

    def owned_by(self, user_id: int) -> bool:
        """ True if the course is in a repo of the user """
        return self.repo.user_id == user_id

    def is_offered(self) -> bool:
        """ True if the course is offered and visible """
        return self.offered_at is not None and not self.hidden

    def has_student(self, user_id: int) -> bool:
        """ True if the user is enrolled in the offer """
        return db.session.scalar(db.select(Enrollment.id)
            .filter_by(user_id=user_id, offer_id=self.id)) is not None

    def offer(self):
        """ Offer the course to every user """
        if self.offered_at is None:
            self.offered_at = now()
            db.session.commit()

    def enroll(self, user_id: int) -> bool:
        """ Enroll the user in the offer. Return False if they were enrolled already """
        if self.has_student(user_id):
            return False
        db.session.add(Enrollment(user_id=user_id, offer_id=self.id))
        db.session.commit()
        return True

class Enrollment(db.Model):
    """ A student enrolled in an offered course """
    __tablename__ = 'enrollments'
    __table_args__ = (db.UniqueConstraint('user_id', 'offer_id'),)
    id = db.Column(db.Integer, primary_key=True)
    # Deleting the user or the offer deletes their enrollments
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False)
    offer_id = db.Column(db.Integer, db.ForeignKey('course_offers.id', ondelete='CASCADE'),
        nullable=False)
    enrolled_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)

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

def sync_offers(repo: ProfessorRepo, names: list, commit: str) -> list:
    """ Make the offers of the repo be the ones of the courses of the given names, found in its
    commit: new courses are prepared, the others get the commit, and the missing ones are deleted,
    or hidden if they are offered. Return the names that other repos have already, which are
    skipped """
    offers = { offer.name: offer for offer in db.session.scalars(
        db.select(CourseOffer).where(CourseOffer.name.in_(names)
            | (CourseOffer.repo_id == repo.id))) }
    skipped = []
    for name in names:
        offer = offers.get(name)
        if offer is None:
            db.session.add(CourseOffer(name=name, repo_id=repo.id, commit=commit))
        elif offer.repo_id != repo.id:
            skipped.append(name)
        else:
            offer.commit, offer.hidden = commit, False
    for name, offer in offers.items():
        if offer.repo_id == repo.id and name not in names:
            if offer.offered_at is None:
                db.session.delete(offer)
            else:
                offer.hidden = True
    db.session.commit()
    return skipped[:MAX_REPORTED_NAMES]
