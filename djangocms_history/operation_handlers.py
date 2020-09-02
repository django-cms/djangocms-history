from functools import partial

from . import actions
from .helpers import get_bound_plugins, get_plugin_data


def _with_callback(func):
    """
    Runs an operation callback defined in the plugin class
    for the given operation handler.
    """
    def wrapped(*args, **kwargs):
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


@_with_callback
def pre_add_plugin(operation, **kwargs):
    # Stores the ID of the parent plugin where the new plugin
    # will be created and the original order of the tree
    # where this plugin is being added
    plugin = kwargs['plugin']
    action_data = {
        'parent_id': plugin.parent_id,
        'order': kwargs['tree_order'],
    }

    operation.create_action(
        action=actions.ADD_PLUGIN,
        language=plugin.language,
        placeholder=kwargs['placeholder'],
        pre_data=action_data,
    )


@_with_callback
def post_add_plugin(operation, **kwargs):
    # Stores the ID of the parent plugin where the new plugin
    # will be created, the plugin data for the new created plugin,
    # and the new order of the tree where this plugin is being added
    plugin = kwargs['plugin']
    action_data = {
        'parent_id': plugin.parent_id,
        'plugins': [get_plugin_data(plugin=plugin)],
        'order': kwargs['tree_order'],
    }

    operation.set_post_action_data(action=actions.ADD_PLUGIN, data=action_data)


@_with_callback
def pre_change_plugin(operation, **kwargs):
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
def post_change_plugin(operation, **kwargs):
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
def pre_delete_plugin(operation, **kwargs):
    # Stores
    #   * the id of the parent plugin for the plugin being deleted
    #   * plugin data for the plugin being deleted and all its descendants.
    #   * the tree order before the plugin got deleted

    get_data = get_plugin_data

    plugin = kwargs['plugin']
    descendants = plugin.get_descendants().order_by('path')
    plugin_data = [get_data(plugin=plugin)]
    plugin_data.extend(get_data(plugin) for plugin in get_bound_plugins(descendants))

    action_data = {
        'parent_id': plugin.parent_id,
        'plugins': plugin_data,
        'order': kwargs['tree_order'],
    }

    operation.create_action(
        action=actions.DELETE_PLUGIN,
        language=plugin.language,
        placeholder=kwargs['placeholder'],
        pre_data=action_data,
    )


@_with_callback
def post_delete_plugin(operation, **kwargs):
    # Stores
    #   * the id of the parent plugin for the deleted plugin
    #   * plugin meta data for the deleted plugin
    #   * the tree order after the plugin got deleted

    plugin = kwargs['plugin']
    plugin_data = [get_plugin_data(plugin=plugin, only_meta=True)]
    action_data = {
        'order': kwargs['tree_order'],
        'parent_id': plugin.parent_id,
        'plugins': plugin_data,
    }

    operation.set_post_action_data(action=actions.DELETE_PLUGIN, data=action_data)


def pre_move_plugin(operation, **kwargs):
    # Action 1 Stores
    #   * the tree order of the source placeholder before the plugin is moved
    #   * the id of the parent plugin for the plugin being moved
    #   * plugin meta data for the plugin being moved

    action_data = {
        'order': kwargs['source_order'],
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
    #   * the tree order of the target placeholder before the plugin is moved
    #   * the id of the new parent plugin

    if move_out:
        action_data = {
            'order': kwargs['target_order'],
            'parent_id': kwargs['target_parent_id'],
        }

        operation.create_action(
            action=actions.MOVE_IN_PLUGIN,
            language=kwargs['target_language'],
            placeholder=kwargs['target_placeholder'],
            pre_data=action_data,
            order=2,
        )


def post_move_plugin(operation, **kwargs):
    # Action 1 Stores
    #   * the tree order of the target placeholder after the plugin was moved
    #   * the id of the new parent plugin
    #   * plugin meta data for the moved plugin

    action_data = {
        'order': kwargs['target_order'],
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
    #   * the tree order of the source placeholder after the plugin was moved
    #   * the id of the old parent plugin

    if move_in:
        action_data = {
            'order': kwargs['source_order'],
            'parent_id': kwargs['source_parent_id'],
        }
        operation.set_post_action_data(action=actions.MOVE_OUT_PLUGIN, data=action_data)


def pre_paste_plugin(operation, **kwargs):
    # Stores
    #   * the tree order of the target placeholder before the plugin is pasted

    action_data = {'order': kwargs['target_order']}

    operation.create_action(
        action=actions.PASTE_PLUGIN,
        language=kwargs['target_language'],
        placeholder=kwargs['target_placeholder'],
        pre_data=action_data,
    )


def post_paste_plugin(operation, **kwargs):
    # Stores
    #   * the tree order of the target placeholder after the plugin was pasted
    #   * the id of the new parent plugin
    #   * plugin data for the pasted plugin and all its descendants

    get_data = get_plugin_data

    plugin = kwargs['plugin']
    descendants = plugin.get_descendants().order_by('path')
    plugin_data = [get_data(plugin=plugin)]
    plugin_data.extend(get_data(plugin) for plugin in get_bound_plugins(descendants))
    action_data = {
        'order': kwargs['target_order'],
        'parent_id': kwargs['target_parent_id'],
        'plugins': plugin_data,
    }

    operation.set_post_action_data(action=actions.PASTE_PLUGIN, data=action_data)


def pre_paste_placeholder(operation, **kwargs):
    # Stores
    #   * the tree order of the target placeholder before the plugins are pasted

    action_data = {
        'order': kwargs['target_order'],
    }

    operation.create_action(
        action=actions.PASTE_PLACEHOLDER,
        language=kwargs['target_language'],
        placeholder=kwargs['target_placeholder'],
        pre_data=action_data,
    )


def post_paste_placeholder(operation, **kwargs):
    # Stores
    #   * the tree order of the target placeholder after the plugins were pasted
    #   * plugin data for the pasted plugins

    get_data = get_plugin_data
    plugins = get_bound_plugins(kwargs['plugins'])
    plugin_data = [get_data(plugin=plugin) for plugin in plugins]
    action_data = {'order': kwargs['target_order'], 'plugins': plugin_data}
    operation.set_post_action_data(action=actions.PASTE_PLACEHOLDER, data=action_data)


def pre_cut_plugin(operation, **kwargs):
    # Action 1 Stores
    #   * plugin meta data for the cut plugin

    get_data = get_plugin_data

    plugin = kwargs['plugin']
    plugin_data = [get_data(plugin=plugin, only_meta=True)]
    action_data = {'plugins': plugin_data}

    operation.create_action(
        action=actions.MOVE_PLUGIN_IN_TO_CLIPBOARD,
        language=kwargs['clipboard_language'],
        placeholder=kwargs['clipboard'],
        post_data=action_data,
        order=1,
    )

    # Action 2 Stores
    #   * the tree order of the source placeholder before the plugin is cut
    #   * the id of the parent plugin for the plugin being cut
    #   * plugin data for the plugin being cut and all its descendants

    descendants = plugin.get_descendants().order_by('path')

    plugins = [plugin]
    plugins.extend(get_bound_plugins(descendants))

    plugin_data = [get_data(plugin=plugin) for plugin in plugins]
    action_data = {
        'order': kwargs['source_order'],
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


def post_cut_plugin(operation, **kwargs):
    # Stores
    #   * the tree order of the target placeholder after the plugin was cut
    #   * the id of the parent plugin for the cut plugin

    action_data = {
        'order': kwargs['source_order'],
        'parent_id': kwargs['source_parent_id'],
    }

    operation.set_post_action_data(
        action=actions.MOVE_PLUGIN_OUT_TO_CLIPBOARD,
        data=action_data,
    )


def pre_add_plugins_from_placeholder(operation, **kwargs):
    # Stores
    #   * plugin data for the pasted plugins

    action_data = {'order': kwargs['target_order']}

    operation.create_action(
        action=actions.ADD_PLUGINS_FROM_PLACEHOLDER,
        language=kwargs['target_language'],
        placeholder=kwargs['target_placeholder'],
        pre_data=action_data,
    )


def post_add_plugins_from_placeholder(operation, **kwargs):
    # Stores
    #   * plugin data for the new plugins
    #   * the tree order of the target placeholder after the new plugins are added

    get_data = get_plugin_data
    plugins = get_bound_plugins(kwargs['plugins'])
    plugin_data = [get_data(plugin=plugin) for plugin in plugins]
    action_data = {
        'plugins': plugin_data,
        'order': kwargs['target_order']
    }

    operation.set_post_action_data(
        action=actions.ADD_PLUGINS_FROM_PLACEHOLDER,
        data=action_data,
    )


def pre_clear_placeholder(operation, **kwargs):
    # Stores
    #   * plugin data for all the plugins being deleted

    get_data = get_plugin_data
    plugins = get_bound_plugins(kwargs['plugins'])
    plugin_data = [get_data(plugin=plugin) for plugin in plugins]
    action_data = {'plugins': plugin_data}

    operation.create_action(
        action=actions.CLEAR_PLACEHOLDER,
        language=operation.language,
        placeholder=kwargs['placeholder'],
        pre_data=action_data,
    )


def post_clear_placeholder(operation, **kwargs):
    # Stores
    #   * plugin meta data for all the deleted parent less  plugins

    get_data = partial(get_plugin_data, only_meta=True)
    root_plugins = [get_data(plugin=plugin) for plugin in kwargs['plugins']
                    if not plugin.parent_id]
    action_data = {'plugins': root_plugins}

    operation.set_post_action_data(action=actions.CLEAR_PLACEHOLDER, data=action_data)
