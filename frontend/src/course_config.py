""" Configuration file in the root of a professor repo, which lists its courses: an object with a
course per key, e.g. {"progra1": {"type": "course", "name": "CI0112", "contents": [...]}}.
parse_courses() in course_offer.py turns each course into a vyg.Course, and skips the invalid
ones """

from config_file import ConfigFile

class CourseConfig(ConfigFile):
    """ The configuration file of the root of a repo, with its courses """

    def interpret(self, data: dict) -> dict:
        """ Return the courses of the file, as {key: course}. Each course is checked when it is
        made a vyg.Course, so a wrong one is skipped without the others """
        return data
