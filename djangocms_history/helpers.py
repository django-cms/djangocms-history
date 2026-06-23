from collections import defaultdict
from datetime import timedelta

from django.contrib.sites.models import Site
from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from cms.utils import get_language_from_request

from .utils import get_plugin_fields, get_plugin_model


def delete_plugins(placeholder, plugin_ids):
    # plugin_ids contains the ids of subtree roots.
    # Placeholder.delete_plugin cascades to descendants and closes
    # the position gap left behind by the deleted subtree.
    # Iterate in reverse position order so earlier deletions don't
    # shift the positions of plugins still queued for deletion.
    plugins = (
        placeholder
        .cmsplugin_set
        .filter(pk__in=plugin_ids)
        .order_by('-position')
    )

    for plugin in plugins:
        placeholder.delete_plugin(plugin)


def get_bound_plugins(plugins):
    plugin_types_map = defaultdict(list)
    plugin_lookup = {}

    # make a map of plugin types, needed later for downcasting
    for plugin in plugins:
        plugin_types_map[plugin.plugin_type].append(plugin.pk)

    for plugin_type, pks in plugin_types_map.items():
        plugin_model = get_plugin_model(plugin_type)
        plugin_queryset = plugin_model.objects.filter(pk__in=pks)

        # put them in a map so we can replace the base CMSPlugins with their
        # downcasted versions
        for instance in plugin_queryset.iterator():
            plugin_lookup[instance.pk] = instance

    for plugin in plugins:
        yield plugin_lookup.get(plugin.pk, plugin)


def get_plugin_data(plugin, only_meta=False):
    if only_meta:
        custom_data = None
    else:
        plugin_fields = get_plugin_fields(plugin.plugin_type)
        _plugin_data = serializers.serialize('python', (plugin,), fields=plugin_fields)[0]
        custom_data = _plugin_data['fields']

    plugin_data = {
        'pk': plugin.pk,
        'creation_date': plugin.creation_date,
        'position': plugin.position,
        'plugin_type': plugin.plugin_type,
        'parent_id': plugin.parent_id,
        'data': custom_data,
    }
    return plugin_data


def get_active_operation(operations):
    operations = operations.filter(is_applied=True)

    try:
        operation = operations.latest()
    except ObjectDoesNotExist:
        operation = None
    return operation


def get_inactive_operation(operations, active_operation=None):
    active_operation = active_operation or get_active_operation(operations)

    if active_operation:
        date_created = active_operation.date_created
        operations = operations.filter(date_created__gt=date_created)

    try:
        operation = operations.filter(is_applied=False).earliest()
    except ObjectDoesNotExist:
        operation = None
    return operation


def get_operations_from_request(request, path=None, language=None):
    from .models import PlaceholderOperation

    if not language:
        language = get_language_from_request(request)

    origin = path or request.path

    # This is controversial :/
    # By design, we don't let undo/redo span longer than a day.
    # To be decided if/how this should be configurable.
    date = timezone.now() - timedelta(days=1)

    site = Site.objects.get_current(request)

    queryset = PlaceholderOperation.objects.filter(
        site=site,
        origin=origin,
        language=language,
        user=request.user,
        user_session_key=request.session.session_key,
        date_created__gt=date,
        is_archived=False,
    )
    return queryset
