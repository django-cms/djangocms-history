from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from cms.models import CMSPlugin

from . import actions
from .helpers import get_bound_plugins, get_plugin_data

if TYPE_CHECKING:
    from .models import PlaceholderOperation

# A note on the kwargs sent by the django CMS operation signals (4.1 / 5.x):
#
# The various ``tree_order`` / ``source_order`` / ``target_order`` kwargs are
# unreliable and MUST NOT be used (see
# https://github.com/django-cms/django-cms/issues/8668):
#
#   ADD_PLUGIN pre              tree_order computed with swapped arguments
#   ADD_PLUGIN post             no tree_order at all
#   DELETE_PLUGIN post          tree_order is the stale pre-delete order
#   MOVE_PLUGIN pre/post        no order kwargs at all
#   MOVE_PLUGIN post            source_parent_id/source_language hold the
#                               *target* values
#   CUT_PLUGIN pre/post         source_order is hard-coded to []
#   ADD_PLUGINS_FROM_PLACEHOLDER post  target_order is the stale pre-copy order
#
# None of this matters for replay: since django CMS 4, ``CMSPlugin.position``
# is a global position (1..n per placeholder+language, descendants included,
# parents before children) and fully encodes the tree order. The handlers
# below therefore only store per-plugin data and parent ids.


def _with_callback(func: Callable) -> Callable:
    """
    Runs an operation callback defined in the plugin class
    for the given operation handler.
    """
    def wrapped(*args: Any, **kwargs: Any) -> None:
        func(*args, **kwargs)

        if 'new_plugin' in kwargs:
            plugin = kwargs['new_plugin']
        else:
            plugin = kwargs['plugin']

        PluginClass = plugin.get_plugin_class()

        try:
            callbacks = PluginClass.operation_handler_callbacks
            callback = callbacks[func.__name__]
            callback(*args, **kwargs)
        except (AttributeError, KeyError):
            pass
    return wrapped


def _get_subtree_data(plugin: CMSPlugin, only_meta: bool = False) -> list[dict[str, Any]]:
    # Returns plugin data for the given (bound) plugin and all of its
    # descendants, ordered by position (parents before children).
    descendants = plugin.get_descendants().order_by('position')
    plugin_data = [get_plugin_data(plugin=plugin, only_meta=only_meta)]
    plugin_data.extend(
        get_plugin_data(plugin=descendant, only_meta=only_meta)
        for descendant in get_bound_plugins(descendants)
    )
    return plugin_data


@_with_callback
def pre_add_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores the ID of the parent plugin where the new plugin
    # will be created.
    # The plugin itself is not saved yet at this point.
    plugin = kwargs['plugin']
    action_data = {'parent_id': plugin.parent_id}

    operation.create_action(
        action=actions.ADD_PLUGIN,
        language=plugin.language,
        placeholder=kwargs['placeholder'],
        pre_data=action_data,
    )


@_with_callback
def post_add_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores the ID of the parent plugin where the new plugin
    # was created and the plugin data for the new created plugin
    # (including its position in the placeholder).
    plugin = kwargs['plugin']
    action_data = {
        'parent_id': plugin.parent_id,
        'plugins': [get_plugin_data(plugin=plugin)],
    }

    operation.set_post_action_data(action=actions.ADD_PLUGIN, data=action_data)


@_with_callback
def pre_change_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * the plugin data before any updates

    plugin = kwargs['old_plugin']
    action_data = {'plugins': [get_plugin_data(plugin=plugin)]}

    operation.create_action(
        action=actions.CHANGE_PLUGIN,
        language=plugin.language,
        placeholder=kwargs['placeholder'],
        pre_data=action_data,
    )


@_with_callback
def post_change_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * the plugin data with updates already applied

    plugin = kwargs['new_plugin']
    action_data = {
        'plugins': [get_plugin_data(plugin=plugin)]
    }

    operation.set_post_action_data(
        action=actions.CHANGE_PLUGIN,
        data=action_data,
    )


@_with_callback
def pre_delete_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * the id of the parent plugin for the plugin being deleted
    #   * plugin data for the plugin being deleted and all its descendants

    plugin = kwargs['plugin']
    action_data = {
        'parent_id': plugin.parent_id,
        'plugins': _get_subtree_data(plugin),
    }

    operation.create_action(
        action=actions.DELETE_PLUGIN,
        language=plugin.language,
        placeholder=kwargs['placeholder'],
        pre_data=action_data,
    )


@_with_callback
def post_delete_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * the id of the parent plugin for the deleted plugin
    #   * plugin meta data for the deleted plugin

    plugin = kwargs['plugin']
    action_data = {
        'parent_id': plugin.parent_id,
        'plugins': [get_plugin_data(plugin=plugin, only_meta=True)],
    }

    operation.set_post_action_data(action=actions.DELETE_PLUGIN, data=action_data)


def pre_move_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Action 1 Stores
    #   * the id of the parent plugin for the plugin being moved
    #   * plugin meta data for the plugin being moved
    #     (including its pre-move position in the source placeholder)

    action_data = {
        'parent_id': kwargs['source_parent_id'],
        'plugins': [get_plugin_data(plugin=kwargs['plugin'], only_meta=True)],
    }

    move_out = kwargs['source_placeholder'] != kwargs['target_placeholder']

    if move_out:
        action = actions.MOVE_OUT_PLUGIN
    else:
        action = actions.MOVE_PLUGIN

    operation.create_action(
        action=action,
        language=kwargs['source_language'],
        placeholder=kwargs['source_placeholder'],
        pre_data=action_data,
    )

    # Action 2 Stores
    #   * the id of the new parent plugin in the target placeholder

    if move_out:
        action_data = {'parent_id': kwargs['target_parent_id']}

        operation.create_action(
            action=actions.MOVE_IN_PLUGIN,
            language=kwargs['target_language'],
            placeholder=kwargs['target_placeholder'],
            pre_data=action_data,
            order=2,
        )


def post_move_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Action 1 Stores
    #   * the id of the new parent plugin
    #   * plugin meta data for the moved plugin
    #     (including its post-move position in the target placeholder)

    action_data = {
        'parent_id': kwargs['target_parent_id'],
        'plugins': [get_plugin_data(plugin=kwargs['plugin'], only_meta=True)],
    }

    move_in = kwargs['source_placeholder'] != kwargs['target_placeholder']

    if move_in:
        action = actions.MOVE_IN_PLUGIN
    else:
        action = actions.MOVE_PLUGIN

    operation.set_post_action_data(action=action, data=action_data)

    # Action 2 Stores
    #   * the id of the old parent plugin in the source placeholder.
    # The post kwargs' source_parent_id holds the *target* parent
    # (see comment table at the top of this module), so the source
    # parent is read back from the data captured by the pre handler.

    if move_in:
        move_out_action = operation.actions.get(action=actions.MOVE_OUT_PLUGIN)
        source_parent_id = move_out_action.get_pre_action_data()['parent_id']
        action_data = {'parent_id': source_parent_id}
        operation.set_post_action_data(action=actions.MOVE_OUT_PLUGIN, data=action_data)


def pre_paste_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * the id of the new parent plugin in the target placeholder

    action_data = {'parent_id': kwargs['target_parent_id']}

    operation.create_action(
        action=actions.PASTE_PLUGIN,
        language=kwargs['target_language'],
        placeholder=kwargs['target_placeholder'],
        pre_data=action_data,
    )


def post_paste_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * the id of the new parent plugin
    #   * plugin data for the pasted plugin and all its descendants

    plugin = kwargs['plugin']
    action_data = {
        'parent_id': kwargs['target_parent_id'],
        'plugins': _get_subtree_data(plugin),
    }

    operation.set_post_action_data(action=actions.PASTE_PLUGIN, data=action_data)


def pre_paste_placeholder(operation: PlaceholderOperation, **kwargs: Any) -> None:
    operation.create_action(
        action=actions.PASTE_PLACEHOLDER,
        language=kwargs['target_language'],
        placeholder=kwargs['target_placeholder'],
        pre_data={},
    )


def post_paste_placeholder(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * plugin data for the pasted plugins

    plugins = sorted(kwargs['plugins'], key=lambda plugin: plugin.position)
    plugin_data = [
        get_plugin_data(plugin=plugin)
        for plugin in get_bound_plugins(plugins)
    ]
    action_data = {'plugins': plugin_data}
    operation.set_post_action_data(action=actions.PASTE_PLACEHOLDER, data=action_data)


def pre_cut_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Action 1 Stores
    #   * plugin data for the cut plugin and all its descendants,
    #     with positions renumbered to where they land in the clipboard
    #     (the clipboard is cleared before the plugin is moved into it,
    #     so the subtree always occupies positions 1..n with the root
    #     at the top level).

    plugin = kwargs['plugin']
    plugin_data = _get_subtree_data(plugin)

    clipboard_data = []

    for index, data in enumerate(plugin_data):
        data = dict(data, position=data['position'] - plugin.position + 1)

        if index == 0:
            # The root plugin sits at the clipboard's top level
            data['parent_id'] = None
        clipboard_data.append(data)

    operation.create_action(
        action=actions.MOVE_PLUGIN_IN_TO_CLIPBOARD,
        language=kwargs['clipboard_language'],
        placeholder=kwargs['clipboard'],
        post_data={'plugins': clipboard_data},
        order=1,
    )

    # Action 2 Stores
    #   * the id of the parent plugin for the plugin being cut
    #   * plugin data for the plugin being cut and all its descendants
    #     (with their original positions in the source placeholder)

    action_data = {
        'parent_id': kwargs['source_parent_id'],
        'plugins': plugin_data,
    }

    operation.create_action(
        action=actions.MOVE_PLUGIN_OUT_TO_CLIPBOARD,
        language=kwargs['source_language'],
        placeholder=kwargs['source_placeholder'],
        pre_data=action_data,
        order=2,
    )


def post_cut_plugin(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * the id of the parent plugin for the cut plugin

    action_data = {'parent_id': kwargs['source_parent_id']}

    operation.set_post_action_data(
        action=actions.MOVE_PLUGIN_OUT_TO_CLIPBOARD,
        data=action_data,
    )


def pre_add_plugins_from_placeholder(operation: PlaceholderOperation, **kwargs: Any) -> None:
    operation.create_action(
        action=actions.ADD_PLUGINS_FROM_PLACEHOLDER,
        language=kwargs['target_language'],
        placeholder=kwargs['target_placeholder'],
        pre_data={},
    )


def post_add_plugins_from_placeholder(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * plugin data for the new plugins

    plugins = sorted(kwargs['plugins'], key=lambda plugin: plugin.position)
    plugin_data = [
        get_plugin_data(plugin=plugin)
        for plugin in get_bound_plugins(plugins)
    ]
    action_data = {'plugins': plugin_data}

    operation.set_post_action_data(
        action=actions.ADD_PLUGINS_FROM_PLACEHOLDER,
        data=action_data,
    )


def pre_clear_placeholder(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * plugin data for all the plugins being deleted

    plugins = sorted(kwargs['plugins'], key=lambda plugin: plugin.position)
    plugin_data = [
        get_plugin_data(plugin=plugin)
        for plugin in get_bound_plugins(plugins)
    ]
    action_data = {'plugins': plugin_data}

    operation.create_action(
        action=actions.CLEAR_PLACEHOLDER,
        language=operation.language,
        placeholder=kwargs['placeholder'],
        pre_data=action_data,
    )


def post_clear_placeholder(operation: PlaceholderOperation, **kwargs: Any) -> None:
    # Stores
    #   * plugin meta data for all the deleted parent-less plugins

    root_plugins = [
        get_plugin_data(plugin=plugin, only_meta=True)
        for plugin in kwargs['plugins']
        if not plugin.parent_id
    ]
    action_data = {'plugins': root_plugins}

    operation.set_post_action_data(action=actions.CLEAR_PLACEHOLDER, data=action_data)
