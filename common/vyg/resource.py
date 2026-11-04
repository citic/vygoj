""" Static materials that are not evaluated """
from vyg.material import Material
from vyg.utils import decode_if


class Resource(Material):
    """ A resource is a static material that is not evaluated to students during the course """
    # Fields to be encoded using base64 when serializing to JSON for network exchange.
    encoded_fields = ['description']

    def __init__(self, json_dict: dict, parent: Material, should_decode: bool):
        """ Construct this object getting values from the given dictionary """
        super().__init__(json_dict, parent, should_decode)
        # Resources may contain rich text in HTML format
        self.description = decode_if(json_dict.get('description', ''), should_decode)
