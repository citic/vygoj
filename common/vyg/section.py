""" Sections of a course """
from vyg.resource import Resource


class Section(Resource, material_type='section'):
    """ A section is a group of materials that are thematically related. They can be nested to
    represent parts, chapters, sections, subsections, and so on. Sections look similar to Pages,
    but sections are listed in the table of contents of the course, while Pages are not."""
