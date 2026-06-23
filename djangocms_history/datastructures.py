from collections import namedtuple

from django.core.serializers import deserialize
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.functional import cached_property
from django.utils.timezone import now

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
            'model': force_str(self.model._meta),
            'fields': self.data,
        }

        # TODO: Handle deserialization error
        return list(deserialize('python', [data]))[0]

    @transaction.atomic
    def restore(self, placeholder, language, parent=None):
        # Creates the plugin row directly at the archived (global) position.
        # The caller is responsible for having opened a large enough gap in
        # the placeholder's plugin tree beforehand and for squashing the
        # positions afterwards (see action_handlers._restore_archived_plugins).
        plugin = CMSPlugin.objects.create(
            pk=self.pk,
            plugin_type=self.plugin_type,
            placeholder=placeholder,
            language=language,
            parent=parent,
            position=self.position,
            creation_date=self.creation_date or now(),
        )

        if self.plugin_type != 'CMSPlugin' and self.data is not None:
            _d_instance = self.deserialized_instance
            plugin.set_base_attr(_d_instance.object)
            _d_instance.save()
        return plugin
