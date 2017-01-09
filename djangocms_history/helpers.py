from collections import defaultdict
from datetime import timedelta

from django.contrib.sites.models import Site
from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import signals
from django.utils import timezone

from cms.models import CMSPlugin
from cms.signals import (
    pre_delete_plugins,
    pre_save_plugins,
    post_delete_plugins
)
from cms.utils import get_language_from_request

from .utils import get_plugin_fields, get_plugin_model


def delete_plugins(placeholder, plugin_ids, nested=True):
    # With plugins, we can't do queryset.delete()
    # because this would trigger a bunch of internal
    # cms signals.
    # Instead, delete each plugin individually and turn off
    # position reordering using the _no_reorder trick.
    plugins = (
        placeholder
        .cmsplugin_set
        .filter(pk__in=plugin_ids)
        .order_by('-depth')
        .select_related()
    )

    bound_plugins = get_bound_plugins(plugins)

    for plugin in bound_plugins:
        plugin._no_reorder = True

        if hasattr(plugin, 'cmsplugin_ptr'):
            plugin.cmsplugin_ptr._no_reorder = True

        # When the nested option is False
        # avoid queries by preventing the cms from
        # recalculating the child counter of this plugin's
        # parent (for which there's none).
        plugin.delete(no_mp=not nested)


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
        language = get_language_from_request(language)

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


def disable_cms_plugin_signals(func):
    # The wrapped function NEEDS to set _no_reorder on any bound plugin instance
    # otherwise this does nothing because it only disconnects signals
    # for the cms.CMSPlugin class, not its subclasses
    plugin_signals = (
        (signals.pre_delete, pre_delete_plugins, 'cms_pre_delete_plugin', CMSPlugin),
        (signals.pre_save, pre_save_plugins, 'cms_pre_save_plugin', CMSPlugin),
        (signals.post_delete, post_delete_plugins, 'cms_post_delete_plugin', CMSPlugin),
    )

    def wrapper(*args, **kwargs):
        for signal, handler, dispatch_id, model_class in plugin_signals:
            signal.disconnect(
                handler,
                sender=model_class,
                dispatch_uid=dispatch_id
            )
            signal.disconnect(handler, sender=model_class)

        func(*args, **kwargs)

        for signal, handler, dispatch_id, model_class in plugin_signals:
            signal.connect(
                handler,
                sender=model_class,
                dispatch_uid=dispatch_id
            )

    return wrapper
