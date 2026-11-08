""" Pages of a course """
from vyg.resource import Resource


class Page(Resource, material_type='page'):
    """ A page is a material that contains text, images, and videos. It can be used to
    present concepts, or instructions. After its description, other materials can be nested.
    Pages are not listed in the table of contents of the course. """
