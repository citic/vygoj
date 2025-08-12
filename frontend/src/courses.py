""" Classes for courses, sections, pages, questions, and problems """
import json
import os
import flask
from flask import current_app as app
#from users import logged_users
import vyg

class CourseController:
    """ Manages courses created by instructors and enrolled by students """
    # Cache of all loaded courses. It is dictionary of {id: Course} pairs
    all_courses = {}

    @staticmethod
    def fetch_my_courses():
        ''' Return the list of courses where current user is enrolled '''
        # TODO(jhc): this test will be replaced by a database query
        result = []
        user = flask.session.get('user')
        if user:
            repo = os.path.join(app.config.get('DATA_FOLDER'), 'u13/pexercises/vygoj.json')
            result = CourseController.load_courses(repo)
            # Store each course in the cache as a pair {course.name: course}
            for course in result:
                CourseController.all_courses[course.name] = course
        return result

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
            # The list of available courses for this user
            'available_courses': CourseController.fetch_all_courses(),
        }
        # print(json.dumps(it, indent=2))
        return flask.render_template('courses.html', it=it)

    @staticmethod
    def get_course(course_id):
        ''' User clicked a course '''
        course = CourseController.all_courses.get(course_id)
        if not course: # TODO(i): and user logged in
            flask.abort(404)
        # TODO(i): progress = user.load_progress()
        it = {
            'user': flask.session.get('user'),
            'breadcrumbs': [
                { 'href': f"/course/{course.name}", 'text': course.name },
            ],
            'course': course,
            # TODO(i): 'progress': progress,
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
                courses.append(vyg.Course(contents, False, folder))
            return courses
        raise RuntimeError(f'could not find course {path}')
