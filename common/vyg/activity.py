""" Materials that are graded """
from vyg.material import Material


class Activity(Material):
    """ An activity is a material that requires an action from the student and it is graded by
    professors or teaching assistants """

    def __init__(self, json_dict: dict, parent: Material):
        """ Construct this object getting values from the given dictionary """
        super().__init__(json_dict, parent)
        # Activities can have different weight over the final course grade
        self.weight = json_dict.get('weight', 1.0)
