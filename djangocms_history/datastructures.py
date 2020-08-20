from collections import namedtuple

from django.core.serializers import deserialize
from django.db import transaction
from django.utils.encoding import force_text
from django.utils.functional import cached_property

from cms.models import CMSPlugin

from .utils import get_plugin_model


BaseArchivedPlugin = namedtuple(
    'BaseArchivedPlugin',
    ['pk', 'creation_date', 'position', 'plugin_type', 'parent_id', 'data']
)


class ArchivedPlugin(BaseArchivedPlugin):

    @cached_property
    def model(self):
        return get_plugin_model(self.plugin_type)

    @cached_property
    def deserialized_instance(self):
        data = {
            'model': force_text(self.model._meta),
            'fields': self.data,
        }

        # TODO: Handle deserialization error
        return list(deserialize('python', [data]))[0]

    @transaction.atomic
    def restore(self, placeholder, language, parent=None):
        plugin_kwargs = {
            'pk': self.pk,
            'plugin_type': self.plugin_type,
            'placeholder': placeholder,
            'language': language,
            'parent': parent,
            'position': self.position,
        }

        if parent:
            plugin = parent.add_child(**plugin_kwargs)
        else:
            plugin = CMSPlugin.add_root(**plugin_kwargs)

        if self.plugin_type != 'CMSPlugin':
            _d_instance = self.deserialized_instance
            _d_instance.object._no_reorder = True
            plugin.set_base_attr(_d_instance.object)
            _d_instance.save()
        return plugin
