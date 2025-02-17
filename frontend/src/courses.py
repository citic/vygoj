import flask
import json

# TODO(jhc): Move to database or fetch from filesystem
allCourses = {
  'c17': {
    'id': 'c17',
    'code': 'CI0117',
    'title': 'Programación paralela y concurrente',
    'image': '/img/logo2.svg',
    'instructors': [
      {
        'id': 'u13',
        'name': 'Jeisson Hidalgo-Céspedes'
      },
    ],
    'statistics': {
      'students': 21,
      'sections': 356, # lessons?
      'problems': 64,
      'questions': 128,
    },
    'contents': [
    ],
  },
  'c1': {
    'id': 'c1',
    'code': 'CI0112',
    'title': 'Programación I en C',
    'image': '/img/logo2.svg',
    'instructors': [
      {
        'id': 'u13',
        'name': 'Jeisson Hidalgo-Céspedes'
      },
    ],
    'statistics': {
      'students': 18,
      'sections': 148, # lessons?
      'problems': 39,
      'questions': 19,
    },
    'repo': 'progra1-21b',
    'contents': [
      {
        'name': 'IO',
        'title': 'Input/output',
        'folder': '1.1_intro_io',
        'contents': [
          {
            'name': 'lost_in_space_ints',
            'title': 'Enteros perdidos en el espacio',
            'folder': 'lost_in_space_ints',
          },
          {
            'name': 'enclosing_lines',
            'title': 'Encerrar las líneas',
            'folder': 'enclosing_lines',
          },
        ],
      },
      {
        'name': 'expr_cond',
        'title': 'Expresiones y condicionales',
        'folder': '1.2_expressions_if',
        'contents': [
          {
            'name': 'line_numbers',
            'title': 'Números de línea',
            'folder': 'line_numbers',
          },
          {
            'name': 'hours_mins_secs',
            'title': 'Normalizar horas, minutos, segundos',
            'folder': 'hours_mins_secs',
          },
        ],
      },
    ],
  },
  'c08': {
    'id': 'c08',
    'code': 'CI0113',
    'title': 'Programación II',
    'image': '/img/logo2.svg',
    'instructors': [
      { 'id': 'u8', 'name': 'Edgar Casasola-Murillo' },
    ],
    'statistics': {
      'students': 23,
      'sections': 123,
      'problems': 27,
      'questions': 94,
    },
    'contents': [
    ],
  },
  'stdthr': {
    'id': 'stdthr',
    'code': 'CI0117a',
    'title': 'Hilos estándar en C/C++',
    'image': '/img/logo2.svg',
    'repo': '',
    'instructors': [
      { 'id': 'u13', 'name': 'Jeisson Hidalgo-Céspedes' },
    ],
    'statistics': {
      'students': 20,
      'sections': 2,
      'problems': 7,
      'questions': 0,
    },
    'contents': [
      {
      'name': 'cstdthr',
      'title': 'Hilos estándar en C',
      'type': 'folder',
      'folder': 'problem',
      'contents': [ {
        'name': 'intro_vygoj',
        'title': 'Introducción al juez en línea',
        'type': 'problem',
        'folder': 'intro_vygoj',
      }, {
        'name': 'c_hello_std',
        'title': 'Hola mundo estándar en C',
        'type': 'problem',
        'folder': 'c_hello_std',
      }, {
        'name': 'c_thrd_sleep',
        'title': 'Hilos durmientes en C',
        'type': 'problem',
        'folder': 'c_thrd_sleep',
      }, {
        'name': 'c_thrd_mtx',
        'title': 'Exclusión mutua en C',
        'type': 'problem',
        'folder': 'c_thrd_mtx',
      # }, {
      #   'name': 'c_local_storage',
      #   'title': 'Local storage en C',
      #   'type': 'problem',
      #   'folder': 'c_local_storage',
      }, {
        'name': 'c_prime_counter',
        'title': 'Contador de primos en C',
        'type': 'problem',
        'folder': 'c_prime_counter',
      }, ],
    },
    # {
    #   'name': 'cppstdthr',
    #   'title': 'Hilos estándar en C++',
    #   'type': 'folder',
    #   'contents': [
    #     {
    #       'name': 'c_hello_std',
    #       'title': 'Hola mundo estándar en C++',
    #       'type': 'problem',
    #       'folder': 'c_hello_std',
    #     }, {
    #       'name': 'c_thrd_sleep',
    #       'title': 'Hilos durmientes en C++',
    #       'type': 'problem',
    #       'folder': 'c_thrd_sleep',
    #     }, {
    #       'name': 'c_thrd_mtx',
    #       'title': 'Exclusión mutua en C++',
    #       'type': 'problem',
    #       'folder': 'c_thrd_mtx',
    #     }, {
    #       'name': 'c_local_storage',
    #       'title': 'Local storage en C++',
    #       'type': 'problem',
    #       'folder': 'c_local_storage',
    #     },
    #   ],
    # },
    ],
  },
}

class Course:
    '''
    A course is an educative event, lasting -but not limited to- an academic term
    where professors and students share and build knowledge and skills. In a
    systems perspective, a course is compound of several resources:

    - Attributes: name, title, description, image, startDate, finishDate
    - Instructors (teachers, professors)
    - Students
    - Sections that can be nested
    - Pages that contain grading assignments, such as
      - Questions
      - Programming problems
    - Grades

    A course has four states:

    - Editing: When it is being created by professors
    - Active: When it is being used by students
    - Finalized: When its finish date passed or professors closed it.
    - Future: When it is ready but its start date is coming.
    '''
    def __init__(self):
        pass

    @staticmethod
    def fetch_my_courses():
        ''' Return the list of courses where current user is enrolled '''
        # TODO(jhc): this test will be replaced by a database query
        return [ allCourses['stdthr'] ]

    @staticmethod
    def fetch_all_courses():
        ''' Return the list of all available courses to enroll '''
        # TODO(jhc): this test will be replaced by a database query
        #return [Course.findById('c1'), Course.findById('c08')]
        return allCourses

    @staticmethod
    def get_index():
        ''' Get the homepage view '''
        # Show courses only for logged in users
        courses = Course.fetch_my_courses() #if flask.q.session.user else []
        # Show the homepage
        it = {
            'user': {'name': 'You', 'role': 'admin'}, # TODO(i): flask.q.session.user,
            'breadcrumbs': [
            ],
            # The list of user's courses
            'my_courses': courses,
            # The list of available courses for this user
            'available_courses': Course.fetch_all_courses(),
        }
        # print(json.dumps(it, indent=2))
        return flask.render_template('courses.html', it=it)

    @staticmethod
    def get_course(course_id):
        ''' User clicked a course '''
        course = allCourses.get(course_id)
        if not course: # TODO(i): and user logged in
            flask.abort(404)
        # TODO(i): progress = user.load_progress()
        it = {
            'user': {'name': 'You', 'role': 'professor'}, # TODO(i): session.user
            'breadcrumbs': [
                { 'href': f'/course/{course['id']}', 'text': course['code'] },
            ],
            'course': course,
            # TODO(i): 'progress': progress,
        }
        print(json.dumps(it, indent=2))
        return flask.render_template('course.html', it=it)
