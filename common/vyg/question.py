""" Questions asked to students """
from vyg.activity import Activity
from vyg.material import Material
from vyg.utils import decode_if


class Question(Activity):
    """ A question is a request for information from students. If student matches the right answer,
    s/he gains points. Questions have variables. Each variable has its own type, text, and answer.
    """
    # Fields to be encoded using base64 when serializing to JSON for network exchange.
    encoded_fields = ['text']

    def __init__(self, json_dict: dict, parent: Material, should_decode: bool):
        """ Construct this object getting values from the given dictionary """
        super().__init__(json_dict, parent, should_decode)
        # Sections may include a short description. For large text nest a Page object
        self.text = decode_if(json_dict.get('text', ''), should_decode)
