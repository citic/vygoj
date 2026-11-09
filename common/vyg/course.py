""" Courses, the root of the material tree """
from vyg.resource import Resource


class Course(Resource):
    """
    A course is an abstract structural concept. It is a collection of educative resources
    (materials) designed by professors to help students to learn about a specific subject.
    Do not confuse with a course offering/group, which is an instance of a course, that is an
    educative event, lasting -but not limited to- an academic term where professors and students
    share and build knowledge and skills. A course is compound of materials, a course offering
    is a course with dates and students enrolled in it.

    In a systems perspective, a course is compound of several resources:

    - Attributes: name, title, description, image, startDate, finishDate
    - Instructors (teachers, professors)
    - Students
    - Sections that can be nested
    - Pages that contain grading assignments, such as
      - Questions
      - Programming problems
    - Grades

    A course has four states:

    - Editing: When it is being modified by professors.
    - Future: When it is ready but its start date is coming.
    - Active: When it is being used by students.
    - Finalized: When its finish date passed or professors closed it.
    """
    def __init__(self, json_dict: dict, folder: str):
        """ Construct this object getting values from the given dictionary """
        # A table of symbols that maps the material names to their objects
        self._symbols = {}
        super().__init__(json_dict, None)
        # Override the folder with the repository folder where courses are stored, e.g:
        # data/u13/pexercises
        self.folder = folder
        # Courses may have an allusive image for helping users to identify it
        self.image = json_dict.get('image', '')
        # Professors that created the course, they may be different than professors who teach it
        self.authors = json_dict.get('authors', [])
        # Status of the course: 'editing', 'available', 'enabled', 'disabled'
        # TODO(jhc): is status needed? snapshots make editing unnecessary, available is the default
        # self.status = json_dict.get('status', '')

    def get_course(self) -> 'Course':
        """ A course is the root of the material tree, so it contains itself """
        return self

    def add_symbol(self, material: 'Material'):
        """ Add this material to the course's symbols table, so it can be found by name """
        if material.name:
            if material.name in self._symbols:
                raise ValueError(f'Material {material.name} duplicated in course {self.name}')
            self._symbols[material.name] = material

    def find_symbol(self, name: str) -> 'Material':
        """ Find a material by its name """
        return self._symbols.get(name)
