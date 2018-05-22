from django.core.serializers.python import Serializer as PythonSerializer
from django.utils.encoding import is_protected_type
import json

class PythonSerializerWithJsonField(PythonSerializer):

    """
    Serialize a QuerySet with JsonField to basic Python objects.
    """

    internal_use_only = True

    def _value_from_field(self, obj, field, jsonfield=None):
        value = field.value_from_object(obj)
        if isinstance(value, str):
            try:
                value_to_dict = json.loads(value)
                if isinstance(value_to_dict, dict):
                    value = value_to_dict
                    jsonfield = True
            except ValueError:
                pass
        # Protected types (i.e., primitives like None, numbers, dates,
        # and Decimals) are passed through as is. if is none JsonField,
        # all other values are converted to string first.
        return value if is_protected_type(value) or jsonfield else field.value_to_string(obj)

    def handle_field(self, obj, field):
        print(obj, field)
        self._current[field.name] = self._value_from_field(obj, field)
