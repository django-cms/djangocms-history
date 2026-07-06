from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Iterable, Iterator
from urllib.parse import urlparse

from django.contrib.sites.models import Site
from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import Resolver404, resolve
from django.utils import timezone

from cms.models import CMSPlugin, Placeholder
from cms.utils import get_language_from_request

from .utils import get_plugin_fields, get_plugin_model, get_session_key_hash

if TYPE_CHECKING:
    from .models import PlaceholderOperation

# The CMS object endpoints (edit / preview / structure) all render the same
# editable object. They live at different URLs, and the structure board even
# rewrites the browser path to the structure URL (history.replaceState), so an
# operation's recorded path depends on which mode it was performed in.
OBJECT_ENDPOINT_URL_NAMES = {
    'cms_placeholder_render_object_edit',
    'cms_placeholder_render_object_preview',
    'cms_placeholder_render_object_structure',
}


def get_operation_origin(path: str) -> str:
    """
    Canonicalises an operation origin so that the edit, preview and structure
    endpoints of the same object all map to a single value of the form
    ``"<content_type_id>:<object_id>"``.

    Falls back to the plain request path for anything that is not a CMS object
    endpoint (e.g. legacy/static placeholder editing), preserving the previous
    behaviour for those cases.
    """
    path = urlparse(path).path

    try:
        match = resolve(path)
    except Resolver404:
        return path

    if match.url_name in OBJECT_ENDPOINT_URL_NAMES:
        # The object endpoints capture (content_type_id, object_id). They use
        # positional groups, but fall back to named kwargs to be safe.
        if len(match.args) >= 2:
            content_type_id, object_id = match.args[0], match.args[1]
        else:
            content_type_id = match.kwargs.get('content_type_id')
            object_id = match.kwargs.get('object_id')
        if content_type_id and object_id:
            return '{}:{}'.format(content_type_id, object_id)
    return path


def delete_plugins(placeholder: Placeholder, plugin_ids: Iterable[int]) -> None:
    # plugin_ids contains the ids of subtree roots.
    # Placeholder.delete_plugin(s) cascades to descendants and closes
    # the position gap left behind by the deleted subtrees.
    plugins = (
        placeholder
        .cmsplugin_set
        .filter(pk__in=plugin_ids)
        .order_by('-position')
    )

    if hasattr(placeholder, 'delete_plugins'):
        # django CMS 5.1+: one bulk delete and a single position
        # re-compaction, instead of one of each per subtree root.
        placeholder.delete_plugins(plugins)
    else:
        # Iterate in reverse position order so earlier deletions don't
        # shift the positions of plugins still queued for deletion.
        for plugin in plugins:
            placeholder.delete_plugin(plugin)


def get_bound_plugins(plugins: Iterable[CMSPlugin]) -> Iterator[CMSPlugin]:
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


def get_plugin_data(plugin: CMSPlugin, only_meta: bool = False) -> dict[str, Any]:
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


def get_active_operation(operations: QuerySet) -> PlaceholderOperation | None:
    operations = operations.filter(is_applied=True)

    try:
        operation = operations.latest()
    except ObjectDoesNotExist:
        operation = None
    return operation


def get_inactive_operation(
    operations: QuerySet,
    active_operation: PlaceholderOperation | None = None,
) -> PlaceholderOperation | None:
    active_operation = active_operation or get_active_operation(operations)

    if active_operation:
        date_created = active_operation.date_created
        operations = operations.filter(date_created__gt=date_created)

    try:
        operation = operations.filter(is_applied=False).earliest()
    except ObjectDoesNotExist:
        operation = None
    return operation


def get_operations_from_request(
    request: HttpRequest,
    path: str | None = None,
    language: str | None = None,
) -> QuerySet:
    from .models import PlaceholderOperation

    if not language:
        language = get_language_from_request(request)

    origin = get_operation_origin(path or request.path)

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
        user_session_key=get_session_key_hash(request.session.session_key),
        date_created__gt=date,
        is_archived=False,
    )
    return queryset
