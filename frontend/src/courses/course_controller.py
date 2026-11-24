""" Classes for courses, sections, pages, questions, and problems """
import math
import threading
import flask
from flask import current_app as app
import vyg
from courses.course_section import CourseSection, Enrollment
from courses.repo_course import RepoCourse, parse_courses
from repos.git_repo import GitError
from repos.professor_repo import CloneError, CourseRepo
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

# Versions of a course kept in the cache of each worker: the main branch of its repo and the
# commits of its sections. The oldest one loaded is dropped first
MAX_CACHED_VERSIONS = 8

# The threads of a gunicorn worker share the cache of courses. The lock prevents two threads from
# changing it at once
_cache_lock = threading.Lock()

class CourseController:
    """ Manages the courses that professors prepare and that students enter. Each user sees a
    version of a course: its professor and administrators the main branch of its repo, and its
    students the commit of their section (section_controller.py) """
    # Cache of the loaded courses, as {(name, folder, commit): vyg.Course}. Each gunicorn worker is
    # a separate process with its own cache, so do not read it directly, use load_course(): the
    # commit of the course or of the section tells when a pull or an update in another process
    # changed it. The folder is part of the key because problems load their files later from it:
    # the clone has the main branch, and each snapshot the commit of some sections
    all_courses = {}

    @staticmethod
    def load_course(repo_course: RepoCourse, section: CourseSection = None) -> vyg.Course | None:
        """ Return the course in the main branch of its clone, or in the snapshot of the commit of
        the section, from the cache if it has it. Return None if it cannot be loaded """
        try:
            if section is None:
                commit, folder = repo_course.commit, repo_course.repo.clone().path
            else:
                commit = section.commit
                folder = repo_course.repo.add_snapshot(commit)
        except (CloneError, GitError, OSError, ValueError):
            app.logger.exception('could not prepare the snapshot of %s', repo_course.name)
            return None
        key = (repo_course.name, folder, commit)
        cached = CourseController.all_courses.get(key)
        if cached:
            return cached
        try:
            course = parse_courses(CourseRepo(folder).read_catalog(), folder)[0].get(
                repo_course.name)
        except CloneError:
            app.logger.warning('could not read the courses of %s', folder)
            return None
        if course:
            CourseController.cache(key, course)
        return course

    @staticmethod
    def cache(key: tuple, course: vyg.Course):
        """ Keep the course in the cache, with up to MAX_CACHED_VERSIONS versions of its name """
        with _cache_lock:
            cache = CourseController.all_courses
            cache[key] = course
            versions = [other for other in cache if other[0] == key[0]]
            for old in versions[:-MAX_CACHED_VERSIONS]:
                del cache[old]

    @staticmethod
    def load_all_courses() -> list:
        """ Return every course that can be loaded, e.g. for the archives of the activity log: the
        main branch of its repo, or the commit of its last section if the main branch does not
        have it anymore (hidden) """
        courses = []
        for repo_course in RepoCourse.all_courses():
            course = None if repo_course.hidden else CourseController.load_course(repo_course)
            if course is None:
                section = CourseSection.newest(repo_course.id, open_only=False)
                course = section and CourseController.load_course(repo_course, section)
            if course:
                courses.append(course)
        return courses

    @staticmethod
    def find_course(name: str, to_enter: bool = True) -> vyg.Course | None:
        """ Return the course of the given name in the version that the logged user sees, if they
        may enter it (to_enter), or see its card (e.g. its image), or else None, as if it did not
        exist. The professor of the course sees the main branch of its repo, its students the
        commit of their section, administrators the main branch, and users who may enroll the
        card of its last open section. A hidden course is seen in the commit of a section """
        repo_course = RepoCourse.find(name)
        user_id = User.logged_id()
        if not repo_course or not user_id or not flask.session.get('user'):
            return None
        owner = repo_course.owned_by(user_id)
        if owner and not repo_course.hidden:
            return CourseController.load_course(repo_course)
        section = CourseSection.of_student(repo_course.id, user_id)
        if section:
            return CourseController.load_course(repo_course, section)
        manager = owner or has_role('admin')
        if manager and not repo_course.hidden:
            return CourseController.load_course(repo_course)
        if manager or not to_enter:
            section = CourseSection.newest(repo_course.id, open_only=not manager)
            return section and CourseController.load_course(repo_course, section)
        return None

    @staticmethod
    def is_owner(name: str) -> bool:
        """ True if the course of the given name is in a repo of the logged user """
        repo_course = RepoCourse.find(name)
        user_id = User.logged_id()
        return bool(repo_course and user_id and repo_course.owned_by(user_id))

    @staticmethod
    def prepared_entries(repo_courses: list) -> list:
        """ Return the cards of the courses of the repos of a professor that can be loaded, as
        dictionaries with the course, its row, and the number of its students in every section """
        counts = Enrollment.course_counts([repo_course.id for repo_course in repo_courses])
        entries = []
        for repo_course in repo_courses:
            course = CourseController.load_course(repo_course)
            if course:
                entries.append({ 'course': course, 'repo_course': repo_course,
                    'students': counts.get(repo_course.id, 0) })
        return entries

    @staticmethod
    def section_entries(sections: list, main_card: bool = False) -> list:
        """ Return the cards of the courses of the sections that can be loaded, in the order of
        the sections, as dictionaries with the course, its row, the number of its students in
        these sections, and its sections, as dictionaries with the section and its number of
        students. The card shows the main branch of the repo if main_card and the course is not
        hidden (e.g. for its professor), or else the commit of its last section """
        counts = CourseSection.student_counts(sections)
        entries = {}
        for section in sections:
            entry = entries.setdefault(section.course_id, { 'repo_course': section.course,
                'students': 0, 'sections': [] })
            students = counts.get(section.id, 0)
            entry['sections'].append({ 'section': section, 'students': students })
            entry['students'] += students
        for entry in entries.values():
            repo_course = entry['repo_course']
            course = None
            if main_card and not repo_course.hidden:
                course = CourseController.load_course(repo_course)
            if course is None:
                last = max((row['section'] for row in entry['sections']), key=lambda row: row.id)
                course = CourseController.load_course(repo_course, last)
            entry['course'] = course
        return [entry for entry in entries.values() if entry['course']]

    @staticmethod
    def get_index():
        """ Get the homepage view: the courses that the logged user prepared and the sections that
        they teach (professors), the courses where they are enrolled, and the open sections where
        they may enroll """
        user = flask.session.get('user')
        user_id = User.logged_id()
        professor = bool(user_id) and has_role('professor')
        prepared = taught = enrolled = available = []
        if user_id:
            if professor:
                prepared = CourseController.prepared_entries(RepoCourse.prepared_by(user_id))
                taught = CourseController.section_entries(CourseSection.taught_by(user_id),
                    main_card=True)
            enrolled = CourseController.section_entries(CourseSection.enrolled_by(user_id))
            available = CourseController.section_entries(CourseSection.available_to(user_id))
        it = {
            'user': user if user_id else None,
            'breadcrumbs': [
            ],
            # Cards of the courses of the repos of the professor, None for other users
            'prepared_courses': prepared if professor else None,
            # Cards of the courses with the sections that the professor teaches, None for others
            'taught_courses': taught if professor else None,
            # Cards of the courses where the user is enrolled, each one with their section
            'enrolled_courses': enrolled,
            # The total progress of the user in each of those courses, as {name: percentage}
            'progress': {entry['course'].name: CourseController.total_progress(entry['course'])
                for entry in enrolled},
            # Cards of the courses with the open sections where the user may enroll
            'available_courses': available,
            'scripts': [
                '<script src="/js/user/repos.js" type="module" async="async"></script>',
                '<script src="/js/courses/courses.js" type="module" async="async"></script>',
                '<script src="/js/site.js" type="module" async="async"></script>',
            ],
        }
        return flask.render_template('courses.html', it=it)

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
