from __future__ import unicode_literals
import json
import functools
import operator

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.signals import user_logged_in
from django.contrib.sites.models import Site
from django.db import models
from django.db import transaction
from django.db.models import Q
from django.dispatch import receiver
from django.utils import six

from cms import operations
from cms.models import Placeholder
from cms.signals import (
    pre_obj_operation,
    pre_placeholder_operation,
    post_placeholder_operation,
)

from . import actions
from . import action_handlers
from . import operation_handlers
from .datastructures import ArchivedPlugin


dump_json = functools.partial(json.dumps, cls=DjangoJSONEncoder)
reduce = six.moves.reduce


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


@receiver(user_logged_in, dispatch_uid='archive_old_operations')
def archive_old_operations(sender, request, user, **kwargs):
    """
    Archives all user operations that don't match the new user session
    """
    site = Site.objects.get_current(request)
    p_operations = (
        PlaceholderOperation
        .objects
        .filter(user=request.user, site=site)
        .exclude(user_session_key=request.session.session_key)
    )
    p_operations.update(is_archived=True)


@receiver(pre_obj_operation)
def pre_page_operation_handler(sender, **kwargs):
    operation_type = kwargs['operation']
    p_operations = PlaceholderOperation.objects.all()

    if operation_type == operations.PUBLISH_STATIC_PLACEHOLDER:
        # Fetch all operations which act on the published
        # static placeholder
        p_id = kwargs['obj'].draft_id
        p_operations = p_operations.filter(actions__placeholder=p_id)
    elif operation_type in operations.PAGE_TRANSLATION_OPERATIONS:
        # Fetch all operations which act on the translation only
        page = kwargs['obj']
        page.set_translations_cache()
        translation = kwargs['translation']
        page_urls = (page.get_absolute_url(lang) for lang in page._title_cache)
        p_operations = p_operations.filter(
            origin__in=page_urls,
            language=translation.language,
        )
    else:
        # Fetch all operations which act on a page including its children
        # for all languages of the page
        page = kwargs['obj']
        page.set_translations_cache()
        page_urls = (page.get_absolute_url(lang) for lang in page._title_cache)
        queries = [Q(origin__startswith=url) for url in page_urls]
        p_operations = p_operations.filter(reduce(operator.or_, queries))

    if kwargs['obj'].site_id:
        # Both cms.Page and cms.StaticPlaceholder have a site field
        # the site field on cms.StaticPlaceholder is optional though.
        p_operations = p_operations.filter(site=kwargs['obj'].site)

    # Archive all fetched operations
    p_operations.update(is_archived=True)


@receiver(pre_placeholder_operation)
def create_placeholder_operation(sender, **kwargs):
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

    # kwargs['language'] can be None if the user has not enabled
    # I18N or is not using i18n_patterns
    language = kwargs['language'] or settings.LANGUAGE_CODE

    operation = PlaceholderOperation.objects.create(
        operation_type=operation_type,
        token=kwargs['token'],
        origin=kwargs['origin'],
        language=language,
        user=request.user,
        user_session_key=request.session.session_key,
        site=Site.objects.get_current(request),
    )
    handler(operation, **kwargs)


@receiver(post_placeholder_operation)
def update_placeholder_operation(sender, **kwargs):
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

    # Mark any operation from this user's session made on a separate path
    # or made on the current path but not applied as archived.
    p_operations.filter(
        ~Q(origin=kwargs['origin'])
        |Q(origin=kwargs['origin'], is_applied=False)
    ).update(is_archived=True)

    # Last, mark any operation made by another user on the current path
    # as archived.
    # TODO: This will need to change to allow for concurrent editing
    # Its actually better to get the affected placeholders
    # and archive any operations that contains those
    foreign_operations = (
        PlaceholderOperation
        .objects
        .filter(origin=kwargs['origin'], site=site)
        .exclude(user=request.user)
     )
    foreign_operations.update(is_archived=True)


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
    site = models.ForeignKey(Site)

    class Meta:
        get_latest_by = "date_created"
        ordering = ['-date_created']

    def create_action(self, action, language, placeholder, **kwargs):
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

    def set_pre_action_data(self, action, data):
        self.actions.filter(action=action).update(pre_action_data=dump_json(data))

    def set_post_action_data(self, action, data):
        self.actions.filter(action=action).update(post_action_data=dump_json(data))

    @transaction.atomic
    def undo(self):
        for action in self.actions.order_by('order'):
            action.undo()
        self.is_applied = False
        self.save(update_fields=['is_applied'])

    @transaction.atomic
    def redo(self):
        for action in self.actions.order_by('-order'):
            action.redo()
        self.is_applied = True
        self.save(update_fields=['is_applied'])


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
    placeholder = models.ForeignKey(to=Placeholder)
    language = models.CharField(max_length=15, choices=settings.LANGUAGES)
    operation = models.ForeignKey(to=PlaceholderOperation, related_name='actions')
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']
        unique_together = ('operation', 'order')

    def _object_version_data_hook(self, data):
        if data and 'pk' in data:
            return ArchivedPlugin(**data)
        return data

    def _get_parsed_data(self, raw_data):
        data = json.loads(
            raw_data,
            object_hook=self._object_version_data_hook,
        )
        return data

    def get_pre_action_data(self):
        return self._get_parsed_data(self.pre_action_data)

    def get_post_action_data(self):
        return self._get_parsed_data(self.post_action_data)

    @transaction.atomic
    def undo(self):
        _action_handlers[self.action]['undo'](self)

    @transaction.atomic
    def redo(self):
        _action_handlers[self.action]['redo'](self)
