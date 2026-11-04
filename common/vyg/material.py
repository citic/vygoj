""" Base class of all educational materials """
import os
from abc import ABC as abstract

from vyg.utils import decode_if


class Material(abstract):
    """ A material is any educational resource created by professors to support the learning of
    students in a course. It can be a page, a question, a programming problem, even a course itself.
    """
    # Fields to be encoded using base64 when serializing to JSON when are send or received by
    # network. Fields loaded from vygoj.json files may be not encoded when created by hand.
    encoded_fields = ['title']

    def __init__(self, json_dict: dict, parent: 'Material', should_decode: bool):
        """ Construct the base part of a Material. json_dict is the dictionary where the values for
        attributes will be loaded from. If should_decode is false, means json_dict was read from a
        vygoj.json file created by humans, so the its values are not base64 encoded. If
        should_decode is true, means the json_dict was received by network. parent is the material
        that contains this material.
        """
        # Reference to the parent material that contains this material, or None if it is the course
        # It is a private attribute, not serialized to JSON, so it starts with _
        self._parent = parent
        # The type of material: 'course', 'section', 'page', 'question', 'problem'. This field is
        # no needed for the memory objects because the type is inferred from the class. It is kept
        # for the JSON representation of the object.
        self.type = json_dict.get('type', '')
        # The folder where this material is stored. Materials can be nested, and folders are
        # concatenated to form a path. For example, a problem in a section of a course may be
        # 'data/user@email.edu/repo/course/section/problem_name'.
        self.folder = json_dict.get('folder', '')
        # An identification name, such as 'CI0117', 'c_hello_world'. It must be unique within the
        # course. If no name is specified, use the folder as the identification name.
        self.name = json_dict.get('name', self.folder)
        # A human readable title, such as 'Programming I', 'Hello world'
        self.title = decode_if(json_dict.get('title', ''), should_decode)
        # Relative date when the material is enabled to students access it. Use relative dates in
        # repository, because they are recommendations. Absolute dates are override by course
        # offerings in the database. A real value means weeks. An empty value means "always enabled"
        self.start = json_dict.get('start', '')
        # Date when the material is overdue, empty means "never overdue". Same rules than start
        self.finish = json_dict.get('finish', '')
        # Action policy when a material is overdue: 'hidden', 'disabled', 'half'
        # 'hidden' means the material is not shown to students at all
        # 'disabled' means it is shown but read-only,
        # 'half' means students can solve the material but get half of the points
        self.overdue_policy = json_dict.get('overdue_policy', 'disabled')
        # Add this material to the course's symbols table, so it can be found by name
        if parent and parent.get_course():
            parent.get_course().add_symbol(self)
        # Materials can be nested, so a material can have a list of contents. Load them
        self.contents = []
        # Notice parent is not used for child materials, because self is the parent for them
        self.load(json_dict.get('contents', []), should_decode)

    def load(self, contents: list, should_decode: bool):
        """ Load the contents of this material that are also materials. """
        # For each entry in the JSON contents list, create a Material object
        for entry in contents:
            self.contents.append(Material.create(entry, self, should_decode))

    @staticmethod
    def create(json_dict: dict, parent: 'Material', should_decode: bool):
        """ Create a Material object from a JSON dictionary entry. """
        # Subclasses import this module, so importing them at the top would create a cycle
        # pylint: disable=import-outside-toplevel
        from vyg.page import Page
        from vyg.problem import Problem
        from vyg.question import Question
        from vyg.section import Section
        material_type = json_dict.get('type', '')
        # If material starts with underscore, it is disabled
        # TODO(jhc): do not load the disabled materials at all
        if material_type.startswith('_'):
            material_type = material_type[1:]
        if material_type == 'section':
            return Section(json_dict, parent, should_decode)
        if material_type == 'page':
            return Page(json_dict, parent, should_decode)
        if material_type == 'question':
            return Question(json_dict, parent, should_decode)
        if material_type == 'problem':
            return Problem(json_dict, parent, should_decode)
        raise TypeError(f'Unknown material type: {material_type}')

    def get_course(self) -> 'Course':
        """ Returns the course that contains this material """
        # Course is a subclass of Material, so importing it at the top would create a cycle
        # pylint: disable=import-outside-toplevel
        from vyg.course import Course
        # The course has no parent (root material), otherwise, search the parent material
        if self._parent is None:
            return self if isinstance(self, Course) else None
        return self._parent.get_course()

    def get_path(self) -> str:
        """ Returns the path where this material is stored, e.g:
        data/u13/pexercises/1.1_io/hello/ """
        # My path is the concatenation of all parent materials and my folder
        return os.path.join(self._parent.get_path(), self.folder) if self._parent else self.folder

    def build_url(self) -> str:
        """ Returns the URL to access this material in the web application """
        # The URL is the concatenation of the course name and my folder
        course_name = f'{self.get_course().name}/' if self._parent else ''
        return f'/{self.type}/{course_name}{self.name}'
