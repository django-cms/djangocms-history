from cms.models import CMSPlugin
from cms.utils.plugins import reorder_plugins

from .helpers import delete_plugins, disable_cms_plugin_signals


@disable_cms_plugin_signals
def _delete_plugins(action, plugin_ids, nested=True):
    delete_plugins(
        placeholder=action.placeholder,
        plugin_ids=plugin_ids,
        nested=nested,
    )
    action.placeholder.mark_as_dirty(action.language, clear_cache=False)


def _reorder_plugins(action, parent_id=None, order=None):
    if not order:
        return

    reorder_plugins(
        action.placeholder,
        parent_id=parent_id,
        language=action.language,
        order=order,
    )


@disable_cms_plugin_signals
def _restore_archived_plugins(action, data, root_plugin_id=None):
    plugins_by_id = {}

    if root_plugin_id:
        plugins_by_id[root_plugin_id] = CMSPlugin.objects.get(pk=root_plugin_id)

    for archived_plugin in data['plugins']:
        if archived_plugin.parent_id:
            parent = plugins_by_id[archived_plugin.parent_id]
        else:
            parent = None

        plugin = archived_plugin.restore(
            placeholder=action.placeholder,
            language=action.language,
            parent=parent,
        )
        plugins_by_id[plugin.pk] = plugin

    action.placeholder.mark_as_dirty(action.language, clear_cache=False)


@disable_cms_plugin_signals
def _restore_archived_plugins_tree(action, data, root_plugin_id=None):
    plugin_ids = [plugin.pk for plugin in data['plugins']]
    plugins_by_id = CMSPlugin.objects.in_bulk(plugin_ids)
    plugin_data = {'language': action.language, 'placeholder': action.placeholder}

    if root_plugin_id:
        root = CMSPlugin.objects.get(pk=root_plugin_id)
    else:
        root = None

    for _plugin in data['plugins']:
        plugin = plugins_by_id[_plugin.pk]

        if root:
            plugin = plugin.update(refresh=True, parent=root, **plugin_data)
            plugin = plugin.move(root, pos='last-child')
        else:
            target = CMSPlugin.get_last_root_node()
            plugin = plugin.update(refresh=True, parent=None, **plugin_data)
            plugin = plugin.move(target, pos='right')

        # Update all children to match the parent's
        # language and placeholder
        plugin.get_descendants().update(**plugin_data)

    action.placeholder.mark_as_dirty(action.language, clear_cache=False)


def undo_add_plugin(action):
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']
    tree_order = action.get_pre_action_data()['order']

    # Only delete plugins who are direct children (or parent-less) of the
    # target parent.
    # This allows for cascade delete of the children of these plugins.
    plugin_ids = [plugin.pk for plugin in post_data['plugins']
                  if plugin.parent_id == parent_id]
    _delete_plugins(action, plugin_ids=plugin_ids, nested=bool(parent_id))
    _reorder_plugins(action, parent_id=parent_id, order=tree_order)


def redo_add_plugin(action):
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']
    _restore_archived_plugins(
        action,
        data=post_data,
        root_plugin_id=parent_id,
    )
    _reorder_plugins(action, parent_id=parent_id, order=post_data['order'])


def undo_change_plugin(action):
    archived_plugins = action.get_pre_action_data()['plugins']

    for plugin in archived_plugins:
        if plugin.data:
            plugin.model.objects.filter(pk=plugin.pk).update(**plugin.data)


def redo_change_plugin(action):
    archived_plugins = action.get_post_action_data()['plugins']

    for plugin in archived_plugins:
        if plugin.data:
            plugin.model.objects.filter(pk=plugin.pk).update(**plugin.data)


def undo_delete_plugin(action):
    pre_data = action.get_pre_action_data()
    parent_id = pre_data['parent_id']
    _restore_archived_plugins(
        action,
        data=pre_data,
        root_plugin_id=parent_id,
    )
    _reorder_plugins(action, parent_id=parent_id, order=pre_data['order'])


def redo_delete_plugin(action):
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']
    plugin_ids = [plugin.pk for plugin in post_data['plugins']]
    _delete_plugins(action, plugin_ids=plugin_ids, nested=bool(parent_id))
    _reorder_plugins(action, parent_id=parent_id, order=post_data['order'])


def undo_move_plugin(action):
    pre_data = action.get_pre_action_data()
    parent_id = pre_data['parent_id']
    _restore_archived_plugins_tree(
        action,
        data=pre_data,
        root_plugin_id=parent_id,
    )
    _reorder_plugins(
        action,
        parent_id=parent_id,
        order=pre_data['order'],
    )


def redo_move_plugin(action):
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']
    _restore_archived_plugins_tree(
        action,
        data=post_data,
        root_plugin_id=parent_id,
    )
    _reorder_plugins(
        action,
        parent_id=parent_id,
        order=post_data['order'],
    )


def undo_move_in_plugin(action):
    pre_data = action.get_pre_action_data()
    _reorder_plugins(
        action,
        parent_id=pre_data['parent_id'],
        order=pre_data['order'],
    )


def redo_move_in_plugin(action):
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']
    _restore_archived_plugins_tree(
        action,
        data=post_data,
        root_plugin_id=parent_id,
    )
    _reorder_plugins(
        action,
        parent_id=parent_id,
        order=post_data['order'],
    )


def undo_move_out_plugin(action):
    pre_data = action.get_pre_action_data()
    parent_id = pre_data['parent_id']
    _restore_archived_plugins_tree(
        action,
        data=pre_data,
        root_plugin_id=parent_id,
    )
    _reorder_plugins(
        action,
        parent_id=parent_id,
        order=pre_data['order'],
    )


def redo_move_out_plugin(action):
    post_data = action.get_post_action_data()
    _reorder_plugins(
        action,
        parent_id=post_data['parent_id'],
        order=post_data['order'],
    )


def undo_move_plugin_in_to_clipboard(action):
    # clear the clipboard
    action.placeholder.clear()


def redo_move_plugin_in_to_clipboard(action):
    post_data = action.get_post_action_data()

    # clear the clipboard
    action.placeholder.clear()

    # Add the plugin back to the clipboard
    # by restoring the data which points it to the clipboard
    # placeholder.
    _restore_archived_plugins_tree(action, data=post_data)


def undo_move_plugin_out_to_clipboard(action):
    pre_data = action.get_pre_action_data()
    parent_id = pre_data['parent_id']

    # Plugin was moved to the clipboard
    # Add it back to the source placeholder
    _restore_archived_plugins(
        action,
        data=pre_data,
        root_plugin_id=parent_id,
    )
    _reorder_plugins(
        action,
        parent_id=parent_id,
        order=pre_data['order'],
    )


def redo_move_plugin_out_to_clipboard(action):
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']
    _reorder_plugins(
        action,
        parent_id=parent_id,
        order=post_data['order'],
    )


def undo_paste_plugin(action):
    tree_order = action.get_pre_action_data()['order']
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']
    plugin_ids = (plugin.pk for plugin in post_data['plugins'])
    _delete_plugins(action, plugin_ids=plugin_ids, nested=bool(parent_id))
    _reorder_plugins(action, parent_id=parent_id, order=tree_order)


def redo_paste_plugin(action):
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']
    _restore_archived_plugins(
        action,
        data=post_data,
        root_plugin_id=parent_id,
    )
    _reorder_plugins(
        action,
        parent_id=parent_id,
        order=post_data['order'],
    )


def undo_paste_placeholder(action):
    tree_order = action.get_pre_action_data()['order']
    post_data = action.get_post_action_data()
    plugin_ids = (plugin.pk for plugin in post_data['plugins'])
    _delete_plugins(action, plugin_ids=plugin_ids, nested=False)
    _reorder_plugins(action, parent_id=None, order=tree_order)


def redo_paste_placeholder(action):
    post_data = action.get_post_action_data()
    _restore_archived_plugins(action, data=post_data)
    _reorder_plugins(action, parent_id=None, order=post_data['order'])


def undo_add_plugins_from_placeholder(action):
    tree_order = action.get_pre_action_data()['order']
    post_data = action.get_post_action_data()
    plugin_ids = (plugin.pk for plugin in post_data['plugins'])
    _delete_plugins(action, plugin_ids=plugin_ids, nested=False)
    _reorder_plugins(action, parent_id=None, order=tree_order)


def redo_add_plugins_from_placeholder(action):
    post_data = action.get_post_action_data()
    _restore_archived_plugins(action, data=post_data)
    _reorder_plugins(action, parent_id=None, order=post_data['order'])


def undo_clear_placeholder(action):
    pre_data = action.get_pre_action_data()
    _restore_archived_plugins(action, data=pre_data)


def redo_clear_placeholder(action):
    action.placeholder.clear(action.language)
