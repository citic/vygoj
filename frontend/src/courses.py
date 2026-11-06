""" Classes for courses, sections, pages, questions, and problems """
import json
import math
import os
import threading
import flask
from flask import current_app as app
import vyg
#from users import logged_users
from users import Progress

# Random combinations for experiments of 4-problem courses
EXP_RAND_TYPE = [
    ['page',    'page',    'problem', 'problem'],
    ['page',    'problem', 'page',    'problem'],
    ['page',    'problem', 'problem', 'page'],
    ['problem', 'page',    'page',    'problem'],
    ['problem', 'page',    'problem', 'page'],
    ['problem', 'problem', 'page',    'page'],
]

# Course repository, relative to DATA_FOLDER, that lists the courses
# TODO(jhc): this path will be replaced by a database query
COURSES_REPO = 'u13/pexercises/vygoj.json'

# The threads of a gunicorn worker share the cache of courses. The lock prevents two threads from
# loading the course repository at once
_cache_lock = threading.Lock()

class CourseController:
    """ Manages courses created by instructors and enrolled by students """
    # Cache of all loaded courses. It is dictionary of {id: Course} pairs. Each gunicorn worker is
    # a separate process with its own cache, so do not read it directly, use find_course()
    all_courses = {}

    @staticmethod
    def fetch_my_courses():
        ''' Return the list of courses where current user is enrolled '''
        # TODO(jhc): this test will be replaced by a database query
        if not flask.session.get('user'):
            return []
        return CourseController.cache_courses()

    @staticmethod
    def cache_courses():
        ''' Load the courses from the repository and store them in the cache of this process '''
        repo = os.path.join(app.config['DATA_FOLDER'], COURSES_REPO)
        courses = CourseController.load_courses(repo)
        with _cache_lock:
            # Store each course in the cache as a pair {course.name: course}
            for course in courses:
                CourseController.all_courses[course.name] = course
        return courses

    @staticmethod
    def find_course(name):
        ''' Return the course with the given name, or None if it does not exist. The worker that
        serves a request may not be the one that loaded the courses, so a missing course in the
        cache of this process loads the repository before giving up '''
        course = CourseController.all_courses.get(name)
        if course is None:
            CourseController.cache_courses()
            course = CourseController.all_courses.get(name)
        return course

    @staticmethod
    def fetch_all_courses():
        ''' Return the list of all available courses to enroll '''
        # TODO(jhc): this test will be replaced by a database query
        #return [Course.findById('c1'), Course.findById('c08')]
        return []

    @staticmethod
    def get_index():
        ''' Get the homepage view '''
        # Show courses only for logged in users
        courses = CourseController.fetch_my_courses() #if flask.q.session.user else []
        # Show the homepage
        it = {
            'user': flask.session.get('user'),
            'breadcrumbs': [
            ],
            # The list of user's courses
            'my_courses': courses,
            # The total progress of the user in each of those courses, as {name: percentage}
            'progress': {course.name: CourseController.total_progress(course)
                for course in courses},
            # The list of available courses for this user
            'available_courses': CourseController.fetch_all_courses(),
        }
        # print(json.dumps(it, indent=2))
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
        average = sum(grades.get(problem, 0) for problem in problems) / len(problems)
        return math.floor(average + 0.5)

    @staticmethod
    def list_problems(contents) -> list:
        ''' Return the names of the problems in the contents, without the disabled ones (their
        type starts with '_'), which the course page does not list '''
        names = []
        for item in contents:
            if item.type == 'problem':
                names.append(item.name)
            elif item.type == 'section':
                names += CourseController.list_problems(item.contents)
        return names

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
            ],
            'progress': Progress.load(course.name),
        }
        # print(json.dumps(it, indent=2))
        return flask.render_template('course.html', it=it)

    @staticmethod
    def load_courses(path):
        """ Load courses from the given path """
        courses = []
        # Get the folder where the courses are stored
        folder = os.path.dirname(path)
        # Read the contents of the file
        with open(path, encoding='utf8') as file:
            # Courses in the json file are stored as a dictionary
            # { id1: {course1}, id2: {course2}...}
            json_dict = json.load(file)
            # Load each course from the JSON dictionary
            for contents in json_dict.values():
                courses.append(vyg.Course(contents, folder))
            return courses
        raise RuntimeError(f'could not find course {path}')

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
