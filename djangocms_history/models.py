from __future__ import annotations

import functools
import json
from typing import Any

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.signals import user_logged_in
from django.contrib.sites.models import Site
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import Q, QuerySet
from django.dispatch import receiver
from django.utils.functional import cached_property
from django.http import HttpRequest

from cms import operations
from cms.models import Placeholder
from cms.signals import post_placeholder_operation, pre_placeholder_operation

from . import action_handlers, actions, operation_handlers, signals
from .datastructures import ArchivedPlugin
from .helpers import get_operation_origin
from .utils import plugin_has_m2m

dump_json = functools.partial(json.dumps, cls=DjangoJSONEncoder)


# TODO: This will likely change into a class based pool integration
# to allow for custom operations and actions

_operation_handlers = {
    operations.ADD_PLUGIN: {
        'pre': operation_handlers.pre_add_plugin,
        'post': operation_handlers.post_add_plugin,
    },
    operations.CHANGE_PLUGIN: {
        'pre': operation_handlers.pre_change_plugin,
        'post': operation_handlers.post_change_plugin,
    },
    operations.DELETE_PLUGIN: {
        'pre': operation_handlers.pre_delete_plugin,
        'post': operation_handlers.post_delete_plugin,
    },
    operations.MOVE_PLUGIN: {
        'pre': operation_handlers.pre_move_plugin,
        'post': operation_handlers.post_move_plugin,
    },
    operations.CUT_PLUGIN: {
        'pre': operation_handlers.pre_cut_plugin,
        'post': operation_handlers.post_cut_plugin,
    },
    operations.PASTE_PLUGIN: {
        'pre': operation_handlers.pre_paste_plugin,
        'post': operation_handlers.post_paste_plugin,
    },
    operations.PASTE_PLACEHOLDER: {
        'pre': operation_handlers.pre_paste_placeholder,
        'post': operation_handlers.post_paste_placeholder,
    },
    operations.ADD_PLUGINS_FROM_PLACEHOLDER: {
        'pre': operation_handlers.pre_add_plugins_from_placeholder,
        'post': operation_handlers.post_add_plugins_from_placeholder,
    },
    operations.CLEAR_PLACEHOLDER: {
        'pre': operation_handlers.pre_clear_placeholder,
        'post': operation_handlers.post_clear_placeholder,
    },
}

_action_handlers = {
    actions.ADD_PLUGIN: {
        'undo': action_handlers.undo_add_plugin,
        'redo': action_handlers.redo_add_plugin,
    },
    actions.CHANGE_PLUGIN: {
        'undo': action_handlers.undo_change_plugin,
        'redo': action_handlers.redo_change_plugin,
    },
    actions.DELETE_PLUGIN: {
        'undo': action_handlers.undo_delete_plugin,
        'redo': action_handlers.redo_delete_plugin,
    },
    actions.MOVE_PLUGIN: {
        'undo': action_handlers.undo_move_plugin,
        'redo': action_handlers.redo_move_plugin,
    },
    actions.MOVE_OUT_PLUGIN: {
        'undo': action_handlers.undo_move_out_plugin,
        'redo': action_handlers.redo_move_out_plugin,
    },
    actions.MOVE_IN_PLUGIN: {
        'undo': action_handlers.undo_move_in_plugin,
        'redo': action_handlers.redo_move_in_plugin,
    },
    actions.MOVE_PLUGIN_OUT_TO_CLIPBOARD: {
        'undo': action_handlers.undo_move_plugin_out_to_clipboard,
        'redo': action_handlers.redo_move_plugin_out_to_clipboard,
    },
    actions.MOVE_PLUGIN_IN_TO_CLIPBOARD: {
        'undo': action_handlers.undo_move_plugin_in_to_clipboard,
        'redo': action_handlers.redo_move_plugin_in_to_clipboard,
    },
    actions.PASTE_PLUGIN: {
        'undo': action_handlers.undo_paste_plugin,
        'redo': action_handlers.redo_paste_plugin,
    },
    actions.PASTE_PLACEHOLDER: {
        'undo': action_handlers.undo_paste_placeholder,
        'redo': action_handlers.redo_paste_placeholder,
    },
    actions.ADD_PLUGINS_FROM_PLACEHOLDER: {
        'undo': action_handlers.undo_add_plugins_from_placeholder,
        'redo': action_handlers.redo_add_plugins_from_placeholder,
    },
    actions.CLEAR_PLACEHOLDER: {
        'undo': action_handlers.undo_clear_placeholder,
        'redo': action_handlers.redo_clear_placeholder,
    },
}


def archive_or_delete_operations(queryset: QuerySet) -> None:
    """
    Retires the given operations from the undo/redo system.

    Archived operations are never reconsidered for undo/redo
    (``get_operations_from_request`` filters out ``is_archived=True`` rows),
    so by default they are deleted outright, together with their actions.

    Set ``DJANGOCMS_HISTORY_ARCHIVE_OPERATIONS = True`` to keep them in the
    database with ``is_archived=True`` instead (e.g. for auditing). Such rows
    can later be removed with the ``purge_archived_operations`` management
    command.
    """
    if getattr(settings, 'DJANGOCMS_HISTORY_ARCHIVE_OPERATIONS', False):
        queryset.update(is_archived=True)
    else:
        queryset.delete()


@receiver(user_logged_in, dispatch_uid='archive_old_operations')
def archive_old_operations(
    sender: Any,
    request: HttpRequest,
    user: AbstractBaseUser,
    **kwargs: Any,
) -> None:
    """
    Retires all of the user's operations that don't match the new session.
    """
    site = Site.objects.get_current(request)

    if not hasattr(request, 'user'):
        # On test environments, its possible the user attribute has not
        # been set.
        return

    p_operations = (
        PlaceholderOperation
        .objects
        .filter(user=request.user, site=site)
        .exclude(user_session_key=request.session.session_key)
    )
    archive_or_delete_operations(p_operations)


# Note: operations are intentionally NOT retired when a page is moved, deleted
# or its translation removed. A move does not invalidate a placeholder's plugin
# history; a delete cascades to the placeholders (and therefore the recorded
# actions), leaving at most a harmless action-less operation; and any leftover
# becomes unreachable after the 24h undo window in any case. The previous
# pre_obj_operation handler also no longer worked with canonical object origins.


def is_unrecordable_change(operation_type: str, kwargs: dict[str, Any]) -> bool:
    """
    Whether the operation is a change to a plugin with a many-to-many
    relation. Such changes cannot be undone, because the snapshot is restored
    with ``queryset.update()``, which rejects M2M fields. Rather than record an
    operation that fails on undo, the history is cleared instead.
    """
    if operation_type != operations.CHANGE_PLUGIN:
        return False

    plugin = kwargs.get('new_plugin') or kwargs.get('old_plugin')
    return plugin is not None and plugin_has_m2m(plugin.plugin_type)


def clear_operation_history(request: HttpRequest, site: Site, origin: str) -> None:
    archive_or_delete_operations(
        PlaceholderOperation.objects.filter(
            site=site,
            origin=origin,
            user=request.user,
            user_session_key=request.session.session_key,
        )
    )


@receiver(pre_placeholder_operation)
def create_placeholder_operation(sender: Any, **kwargs: Any) -> None:
    """
    Creates the initial placeholder operation record
    """
    request = kwargs.pop('request')
    operation_type = kwargs.pop('operation')
    handler = _operation_handlers.get(operation_type, {}).get('pre')

    # Adding cms_history=0 to any of the operation endpoints
    # will prevent the recording of history for that one operation
    cms_history = request.GET.get('cms_history', True)
    cms_history = models.BooleanField().to_python(cms_history)

    if not handler or not cms_history:
        return

    site = Site.objects.get_current(request)
    origin = get_operation_origin(kwargs['origin'])

    if is_unrecordable_change(operation_type, kwargs):
        # The change cannot be undone; clear the (now unreliable) history.
        clear_operation_history(request, site, origin)
        return

    # kwargs['language'] can be None if the user has not enabled
    # I18N or is not using i18n_patterns
    language = kwargs['language'] or settings.LANGUAGE_CODE

    operation = PlaceholderOperation.objects.create(
        operation_type=operation_type,
        token=kwargs['token'],
        origin=origin,
        language=language,
        user=request.user,
        user_session_key=request.session.session_key,
        site=site,
    )
    handler(operation, **kwargs)


@receiver(post_placeholder_operation)
def update_placeholder_operation(sender: Any, **kwargs: Any) -> None:
    """
    Updates the created placeholder operation record,
    based on the configured post operation handlers.
    """
    request = kwargs.pop('request')
    operation_type = kwargs.pop('operation')

    handler = _operation_handlers.get(operation_type, {}).get('post')

    # Adding cms_history=0 to any of the operation endpoints
    # will prevent the recording of history for that one operation
    cms_history = request.GET.get('cms_history', True)
    cms_history = models.BooleanField().to_python(cms_history)

    if not handler or not cms_history:
        return

    site = Site.objects.get_current(request)
    origin = get_operation_origin(kwargs['origin'])

    if is_unrecordable_change(operation_type, kwargs):
        # Nothing was recorded in the pre handler; the history was cleared.
        return

    p_operations = PlaceholderOperation.objects.filter(
        site=site,
        user=request.user,
        user_session_key=request.session.session_key
    )

    operation = p_operations.get(token=kwargs['token'])

    # Run the placeholder operation handler
    handler(operation, **kwargs)

    # Mark the new operation as applied
    p_operations.filter(pk=operation.pk).update(is_applied=True)

    # Retire any operation from this user's session made on a separate origin
    # or made on the current origin but not applied.
    archive_or_delete_operations(
        p_operations.filter(
            ~ Q(origin=origin)
            | Q(origin=origin, is_applied=False)
        )
    )

    # Last, retire any operation made by another user on the current origin.
    # TODO: This will need to change to allow for concurrent editing
    # Its actually better to get the affected placeholders
    # and archive any operations that contains those
    foreign_operations = (
        PlaceholderOperation
        .objects
        .filter(origin=origin, site=site)
        .exclude(user=request.user)
     )
    archive_or_delete_operations(foreign_operations)


class PlaceholderOperation(models.Model):

    OPERATION_TYPES = (
        (operations.ADD_PLUGIN, 'Add plugin'),
        (operations.CHANGE_PLUGIN, 'Change plugin'),
        (operations.DELETE_PLUGIN, 'Delete plugin'),
        (operations.MOVE_PLUGIN, 'Move plugin'),
        (operations.CUT_PLUGIN, 'Cut plugin'),
        (operations.PASTE_PLUGIN, 'Paste plugin'),
        (operations.PASTE_PLACEHOLDER, 'Paste placeholder'),
        (operations.ADD_PLUGINS_FROM_PLACEHOLDER, 'Add plugins from placeholder'),
        (operations.CLEAR_PLACEHOLDER, 'Clear placeholder'),
    )

    operation_type = models.CharField(max_length=30, choices=OPERATION_TYPES)
    token = models.CharField(max_length=120, db_index=True)
    origin = models.CharField(max_length=255, db_index=True)
    language = models.CharField(max_length=15, choices=settings.LANGUAGES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="user",
    )
    # Django uses 40 character session keys but other backends might use longer..
    user_session_key = models.CharField(max_length=120, db_index=True)
    date_created = models.DateTimeField(
        db_index=True,
        auto_now_add=True,
        verbose_name="date created",
    )
    is_applied = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE)

    class Meta:
        get_latest_by = "date_created"
        ordering = ['-date_created']

    def create_action(
        self,
        action: str,
        language: str,
        placeholder: Placeholder,
        **kwargs: Any,
    ) -> None:
        pre_data = kwargs.pop('pre_data', '')

        if pre_data:
            pre_data = dump_json(pre_data)

        post_data = kwargs.pop('post_data', '')

        if post_data:
            post_data = dump_json(post_data)

        self.actions.create(
            action=action,
            pre_action_data=pre_data,
            post_action_data=post_data,
            language=language,
            placeholder=placeholder,
            **kwargs
        )

    def set_pre_action_data(self, action: str, data: dict[str, Any]) -> None:
        self.actions.filter(action=action).update(pre_action_data=dump_json(data))

    def set_post_action_data(self, action: str, data: dict[str, Any]) -> None:
        self.actions.filter(action=action).update(post_action_data=dump_json(data))

    @cached_property
    def cached_actions(self):
        """
        The operation's actions with their placeholders, fetched once and
        ordered by ``order``. The undo/redo paths inspect this small set
        several times (editability check, replay, response building); the
        cache keeps that to a single query.
        """
        return list(self.actions.select_related('placeholder'))

    def is_editable(self, user: AbstractBaseUser) -> bool:
        """
        Returns whether all placeholders touched by this operation are
        editable by the given user. With djangocms-versioning installed
        this is False for placeholders that belong to published (or
        otherwise locked) versions; undoing/redoing operations on such
        content would corrupt it.
        """
        # An operation's actions can share a placeholder (e.g. a
        # same-placeholder move); check_source resolves the placeholder's
        # source object, so only check each placeholder once.
        placeholders = {
            action.placeholder_id: action.placeholder
            for action in self.cached_actions
        }
        return all(
            placeholder.check_source(user)
            for placeholder in placeholders.values()
        )

    #: Operation types that center on a single plugin subtree. After an
    #: undo/redo the resulting state can be reflected to the frontend as the
    #: plugin's "add" or "edit" close frame (the data bridge), provided the
    #: plugin still exists (e.g. an undone "add" deletes the plugin, so there
    #: is nothing to render).
    CLOSE_FRAME_ACTIONS = {
        operations.ADD_PLUGIN: 'add',
        operations.CHANGE_PLUGIN: 'edit',
        operations.DELETE_PLUGIN: 'add',
        operations.PASTE_PLUGIN: 'add',
    }

    def get_close_frame_target(self) -> tuple[str, int, str, int | None] | None:
        """
        For single-plugin operations, returns
        ``(action, plugin_id, plugin_type, parent_id)`` where ``action`` is
        ``'add'`` or ``'edit'``, ``plugin_id``/``plugin_type`` identify the
        plugin the operation centers on and ``parent_id`` is its parent.
        Returns ``None`` for operations that don't map to a single plugin
        (move, cut, clear, paste placeholder, ...).

        The caller must still check whether the plugin exists after the replay:
        if it is gone (an undone "add", a redone "delete"/"paste") the net
        effect is a deletion, which should be reflected as a "delete" frame
        rather than an "add"/"edit" one.
        """
        action = self.CLOSE_FRAME_ACTIONS.get(self.operation_type)

        if action is None:
            return None

        if not self.cached_actions:
            return None

        operation_action = self.cached_actions[0]

        for data in (
            operation_action.get_post_action_data(),
            operation_action.get_pre_action_data(),
        ):
            if data and data.get('plugins'):
                archived = data['plugins'][0]
                return action, archived.pk, archived.plugin_type, data.get('parent_id')
        return None

    def get_move_plugin_id(self) -> int | None:
        """
        For a move operation, returns the id of the moved plugin (read from
        the stored action data, which records it for both same-placeholder
        and cross-placeholder moves). Returns ``None`` for other operations.
        """
        if self.operation_type != operations.MOVE_PLUGIN:
            return None

        for operation_action in self.cached_actions:
            for data in (
                operation_action.get_pre_action_data(),
                operation_action.get_post_action_data(),
            ):
                if data and data.get('plugins'):
                    return data['plugins'][0].pk
        return None

    @transaction.atomic
    def undo(self) -> None:
        actions = self.cached_actions

        for action in actions:
            action.undo()

        self.is_applied = False
        self.save(update_fields=['is_applied'])
        signals.post_operation_undo.send(
            sender=self.__class__,
            operation=self,
            actions=actions,
        )

    @transaction.atomic
    def redo(self) -> None:
        actions = list(reversed(self.cached_actions))

        for action in actions:
            action.redo()
        self.is_applied = True
        self.save(update_fields=['is_applied'])
        signals.post_operation_redo.send(
            sender=self.__class__,
            operation=self,
            actions=actions,
        )


class PlaceholderAction(models.Model):
    ACTION_CHOICES = (
        (actions.ADD_PLUGIN, 'Add plugin'),
        (actions.CHANGE_PLUGIN, 'Change plugin'),
        (actions.DELETE_PLUGIN, 'Delete plugin'),
        (actions.MOVE_PLUGIN, 'Move plugin'),
        (actions.MOVE_OUT_PLUGIN, 'Move out plugin'),
        (actions.MOVE_IN_PLUGIN, 'Move in plugin'),
        (actions.MOVE_PLUGIN_OUT_TO_CLIPBOARD, 'Move out to clipboard'),
        (actions.MOVE_PLUGIN_IN_TO_CLIPBOARD, 'Move in to clipboard'),
        (actions.ADD_PLUGINS_FROM_PLACEHOLDER, 'Add plugins from placeholder'),
        (actions.PASTE_PLUGIN, 'Paste plugin'),
        (actions.PASTE_PLACEHOLDER, 'Paste placeholder'),
        (actions.CLEAR_PLACEHOLDER, 'Clear placeholder'),
    )

    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    pre_action_data = models.TextField(blank=True)
    post_action_data = models.TextField(blank=True)
    placeholder = models.ForeignKey(to=Placeholder, on_delete=models.CASCADE)
    language = models.CharField(max_length=15, choices=settings.LANGUAGES)
    operation = models.ForeignKey(to=PlaceholderOperation, related_name='actions', on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']
        unique_together = ('operation', 'order')

    def _object_version_data_hook(self, data: Any) -> Any:
        if isinstance(data, dict) and 'pk' in data and 'plugin_type' in data and 'position' in data:
            return ArchivedPlugin(**data)
        return data

    def _get_parsed_data(self, raw_data: str) -> Any:
        data = json.loads(
            raw_data,
            object_hook=self._object_version_data_hook,
        )
        return data

    def get_pre_action_data(self) -> Any:
        return self._get_parsed_data(self.pre_action_data)

    def get_post_action_data(self) -> Any:
        return self._get_parsed_data(self.post_action_data)

    @transaction.atomic
    def undo(self) -> None:
        _action_handlers[self.action]['undo'](self)

    @transaction.atomic
    def redo(self) -> None:
        _action_handlers[self.action]['redo'](self)
