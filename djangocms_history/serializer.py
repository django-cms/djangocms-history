import json

from django.core.serializers.python import Serializer as PythonSerializer
from django.utils.encoding import is_protected_type


class PythonSerializerWithDetectNestedJsonField(PythonSerializer):
    """
    Serialize a QuerySet and detect nested JsonField to basic Python objects.
    """
    internal_use_only = True

    def _value_from_field(self, obj, field, jsonfield_to_dict=None):
        value = field.value_from_object(obj)
        if isinstance(value, str):
            try:
                value = json.loads(value)
                jsonfield_to_dict = True
            except ValueError:
                pass
        # Protected types (i.e., primitives like None, numbers, dates,
        # and Decimals) are passed through as is. And if is none JsonField,
        # all other values are converted to string first.
        return value if is_protected_type(value) or jsonfield_to_dict else field.value_to_string(obj)

    def handle_field(self, obj, field):
        self._current[field.name] = self._value_from_field(obj, field)
