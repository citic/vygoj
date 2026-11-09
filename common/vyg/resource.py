""" Static materials that are not evaluated """
from vyg.material import Material


class Resource(Material):
    """ A resource is a static material that is not evaluated to students during the course """
    def __init__(self, json_dict: dict, parent: Material):
        """ Construct this object getting values from the given dictionary """
        super().__init__(json_dict, parent)
        # Resources may contain rich text in HTML format
        self.description = json_dict.get('description', '')
