""" Classes for courses, sections, pages, questions, and problems """
import math
import threading
import flask
from flask import current_app as app
from flask_babel import gettext
import vyg
from activity_log import log_event
from course_offer import CourseOffer, parse_courses
from repos.git_repo import GitError
from repos.professor_repo import CloneError
from repos.student_repo import StudentRepo
from users import Progress, User, has_role

# Random combinations for experiments of 4-problem courses
EXP_RAND_TYPE = [
    ['page',    'page',    'problem', 'problem'],
    ['page',    'problem', 'page',    'problem'],
    ['page',    'problem', 'problem', 'page'],
    ['problem', 'page',    'page',    'problem'],
    ['problem', 'page',    'problem', 'page'],
    ['problem', 'problem', 'page',    'page'],
]

# The threads of a gunicorn worker share the cache of courses. The lock prevents two threads from
# changing it at once
_cache_lock = threading.Lock()

class CourseController:
    """ Manages the courses that professors prepare and offer, and that students enroll """
    # Cache of the loaded courses, as {name: (commit, vyg.Course)}. Each gunicorn worker is a
    # separate process with its own cache, so do not read it directly, use load_course(): the
    # commit of its offer tells when a pull in another process changed a course
    all_courses = {}

    @staticmethod
    def load_course(offer: CourseOffer) -> vyg.Course | None:
        """ Return the course of the offer, from the cache if it has the commit of the offer, or
        else from the clone of its repo. Return None if the clone does not have it """
        cached = CourseController.all_courses.get(offer.name)
        if cached and cached[0] == offer.commit:
            return cached[1]
        clone = offer.repo.clone()
        try:
            course = parse_courses(clone.read_catalog(), clone.path)[0].get(offer.name)
        except CloneError:
            app.logger.warning('could not read the courses of %s', clone.path)
            return None
        if course:
            with _cache_lock:
                CourseController.all_courses[offer.name] = (offer.commit, course)
        return course

    @staticmethod
    def load_all_courses() -> list:
        """ Return every course that can be loaded, prepared, offered, or hidden, e.g. for the
        archives of the activity log """
        courses = (CourseController.load_course(offer) for offer in CourseOffer.all_offers())
        return [course for course in courses if course]

    @staticmethod
    def find_course(name: str, to_enter: bool = True) -> vyg.Course | None:
        """ Return the course of the given name if the logged user may enter it (to_enter), or
        see its card (e.g. its image), or else None, as if it did not exist """
        offer = CourseOffer.find(name)
        if not offer or offer.hidden or not CourseController.can_see(offer, to_enter):
            return None
        return CourseController.load_course(offer)

    @staticmethod
    def can_see(offer: CourseOffer, to_enter: bool) -> bool:
        """ True if the logged user may enter the course of the offer (to_enter), or see its
        card: administrators and the professor of the course always, students enrolled in it, and
        every user may see the cards of offered courses """
        user = flask.session.get('user')
        user_id = User.logged_id()
        if not user or not user_id:
            return False
        if has_role('admin') or offer.owned_by(user_id):
            return True
        return offer.has_student(user_id) or (not to_enter and offer.is_offered())

    @staticmethod
    def entries(offers: list) -> list:
        """ Return the cards of the courses of the offers that can be loaded, as dictionaries
        with the course, its offer, and the number of its students """
        counts = CourseOffer.student_counts(offers)
        entries = []
        for offer in offers:
            course = CourseController.load_course(offer)
            if course:
                entries.append({ 'course': course, 'offer': offer,
                    'students': counts.get(offer.id, 0) })
        return entries

    @staticmethod
    def get_index():
        """ Get the homepage view: the courses that the logged user prepared (professors), the
        ones where they are enrolled, and the offered ones where they may enroll """
        user = flask.session.get('user')
        user_id = User.logged_id()
        prepared = enrolled = available = []
        if user_id:
            if has_role('professor'):
                prepared = CourseController.entries(CourseOffer.prepared_by(user_id))
            enrolled = CourseController.entries(CourseOffer.enrolled_by(user_id))
            available = CourseController.entries(CourseOffer.available_to(user_id))
        it = {
            'user': user if user_id else None,
            'breadcrumbs': [
            ],
            # Cards of the courses of the repos of the professor, None for other users
            'prepared_courses': prepared if has_role('professor') else None,
            # Cards of the courses where the user is enrolled
            'enrolled_courses': enrolled,
            # The total progress of the user in each of those courses, as {name: percentage}
            'progress': {entry['course'].name: CourseController.total_progress(entry['course'])
                for entry in enrolled},
            # Cards of the offered courses where the user may enroll
            'available_courses': available,
            'scripts': [
                '<script src="/js/user/repos.js" type="module" async="async"></script>',
                '<script src="/js/courses/courses.js" type="module" async="async"></script>',
                '<script src="/js/site.js" type="module" async="async"></script>',
            ],
        }
        return flask.render_template('courses.html', it=it)

    @staticmethod
    def offer(name: str):
        """ The professor of a prepared course offers it to every user, who see it in Available
        courses """
        user_id = User.logged_id()
        offer = CourseOffer.find(name)
        if not user_id or not offer or offer.hidden:
            flask.abort(404)
        if not has_role('professor') or not offer.owned_by(user_id):
            flask.abort(403)
        if offer.offered_at is None:
            offer.offer()
            log_event('course_offer', course=name)
        flask.flash(gettext('Course %(name)s offered.', name=name), 'success')
        return flask.redirect(flask.url_for('get_index'))

    @staticmethod
    def enroll(name: str):
        """ The logged user enrolls in an offered course, which goes to their enrolled courses """
        user_id = User.logged_id()
        if not user_id:
            flask.abort(401)
        offer = CourseOffer.find(name)
        if not offer or not offer.is_offered():
            flask.abort(404)
        if offer.enroll(user_id):
            log_event('course_enroll', course=name)
        flask.flash(gettext('You are enrolled in %(name)s.', name=name), 'success')
        return flask.redirect(flask.url_for('get_index'))

    @staticmethod
    def total_progress(course) -> int:
        ''' Return the average grade of the logged user in the problems of the course, the same
        total that the course page shows '''
        course = CourseController.customize_for(course, flask.session.get('user'))
        grades = Progress.load(course.name)
        problems = CourseController.list_problems(course.contents)
        if not problems:
            return 0
        # Problems without a grade count as 0. Rounded half up, as Math.round() in course.js
        average = sum(grades.get(problem.name, 0) for _, problem in problems) / len(problems)
        return math.floor(average + 0.5)

    @staticmethod
    def list_problems(contents, prefix='') -> list:
        ''' Return the problems in the contents as (number, problem), numbered as on the course page
        (e.g. '3.7.4'), without the disabled ones (their type starts with '_'), which the course
        page does not list '''
        problems = []
        enabled = [item for item in contents if not item.type.startswith('_')]
        for index, item in enumerate(enabled, 1):
            number = f'{prefix}{index}'
            if item.type == 'problem':
                problems.append((number, item))
            elif item.type == 'section':
                problems += CourseController.list_problems(item.contents, f'{number}.')
        return problems

    @staticmethod
    def neighbors(problem) -> tuple:
        ''' Return the problems before and after the given one in its course, as (number, problem)
        in the order of the course page, or None at the ends of the course '''
        course = CourseController.customize_for(problem.get_course(), flask.session.get('user'))
        problems = CourseController.list_problems(course.contents)
        names = [item.name for _, item in problems]
        if problem.name not in names:
            return None, None
        index = names.index(problem.name)
        previous = problems[index - 1] if index > 0 else None
        following = problems[index + 1] if index + 1 < len(problems) else None
        return previous, following

    @staticmethod
    def get_course(course_id):
        ''' User clicked a course '''
        course = CourseController.find_course(course_id)
        # TODO(jhc): Disable after experiments
        course = CourseController.customize_for(course, flask.session.get('user'))
        if not course: # TODO(i): and user logged in
            flask.abort(404)
        it = {
            'user': flask.session.get('user'),
            'breadcrumbs': [
                { 'href': f"/course/{course.name}", 'text': course.name },
            ],
            'course': course,
            'scripts': [
                '<script src="/js/course/course.js" type="module" async="async"></script>',
                '<script src="/js/site.js" type="module" async="async"></script>',
            ],
            'progress': Progress.load(course.name),
            # The problem where the user ran new code last, where the course page scrolls to
            'last_problem': CourseController.last_problem(course.name),
        }
        # print(json.dumps(it, indent=2))
        return flask.render_template('course.html', it=it)

    @staticmethod
    def last_problem(course_name: str) -> str | None:
        ''' Return the problem of the course whose solution the logged user changed last, from
        their student repo, or None. A failure is logged, and the course page does not scroll '''
        user = flask.session.get('user')
        if not user:
            return None
        try:
            return StudentRepo(user.get('email')).last_problem(course_name)
        except (GitError, OSError, ValueError):
            app.logger.exception('could not find the last problem of %s', course_name)
            return None

    @staticmethod
    def customize_for(course, user):
        """ Return a course dictionary according to the type of participant """
        if not user or not course:
            return course
        username = user.get('email') or ''
        # If not a student of the experiment (e01, e02...), return the course as is. Other names
        # such as 'eab' must not reach int(), otherwise the course page fails for that user
        if len(username) != 3 or username[0] != 'e' or not username[1:].isdigit():
            return course
        num = int(username[1:]) - 1  # Convert 'e01' to 0, 'e02' to 1, etc.
        permutation = EXP_RAND_TYPE[num % 6]
        problems = course.contents[0].contents
        if len(problems) != 4:
            return course
        for index in range(4):
            problems[index].type = permutation[index]
        return course
