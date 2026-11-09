""" Questions asked to students """
from vyg.activity import Activity
from vyg.material import Material


class Question(Activity, material_type='question'):
    """ A question is a request for information from students. If student matches the right answer,
    s/he gains points. Questions have variables. Each variable has its own type, text, and answer.
    """
    def __init__(self, json_dict: dict, parent: Material):
        """ Construct this object getting values from the given dictionary """
        super().__init__(json_dict, parent)
        # Sections may include a short description. For large text nest a Page object
        self.text = json_dict.get('text', '')
