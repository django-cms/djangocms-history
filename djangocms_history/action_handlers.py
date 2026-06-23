from cms.models import CMSPlugin

from .helpers import delete_plugins


def _delete_plugins(action, plugin_ids):
    delete_plugins(
        placeholder=action.placeholder,
        plugin_ids=plugin_ids,
    )
    action.placeholder.clear_cache(action.language)


def _restore_archived_plugins(action, data):
    """
    Recreates the archived plugins (a subtree or a list of subtrees)
    in the action's placeholder, at their archived positions and with
    their original primary keys.

    Strategy: open a collision-free gap in the placeholder's plugin tree,
    create the rows at their archived (global) positions, then squash all
    positions to close any holes. Restoring plugin-by-plugin through
    ``Placeholder.add_plugin`` instead would renumber previously restored
    siblings and invalidate the archived positions.
    """
    placeholder = action.placeholder
    language = action.language
    archived_plugins = sorted(data['plugins'], key=lambda plugin: plugin.position)

    if not archived_plugins:
        return

    start = archived_plugins[0].position
    count = len(archived_plugins)
    last = placeholder.get_last_plugin_position(language) or 0

    if last >= start:
        # Shift all plugins at or after the first archived position out of
        # the way. The offset guarantees the shifted plugins land beyond
        # any archived position (which is at most the size of the tree at
        # archive time), so the unique (placeholder, language, position)
        # constraint cannot be violated by the inserts below.
        placeholder._shift_plugin_positions(
            language,
            start=start,
            offset=last + count,
        )

    restored_ids = {archived_plugin.pk for archived_plugin in archived_plugins}
    # Parents that are not part of the restored set survived in the
    # placeholder (e.g. a nested plugin restored under an existing parent).
    # Fetch them all in one query rather than one lookup per plugin.
    surviving_parent_ids = {
        archived_plugin.parent_id
        for archived_plugin in archived_plugins
        if archived_plugin.parent_id and archived_plugin.parent_id not in restored_ids
    }
    plugins_by_id = CMSPlugin.objects.in_bulk(surviving_parent_ids)

    for archived_plugin in archived_plugins:
        if archived_plugin.parent_id:
            parent = plugins_by_id[archived_plugin.parent_id]
        else:
            parent = None

        plugin = archived_plugin.restore(
            placeholder=placeholder,
            language=language,
            parent=parent,
        )
        plugins_by_id[plugin.pk] = plugin

    # Close the holes left by the shift; restored plugins keep their
    # relative order, surviving plugins keep theirs.
    placeholder._recalculate_plugin_positions(language)
    placeholder.clear_cache(language)


def _move_plugin(action, data):
    """
    Moves the live plugin referenced by the action data to the archived
    position (and parent) in the action's placeholder. A single
    ``Placeholder.move_plugin`` call fixes the positions of both the
    source and the target placeholder.
    """
    plugin_meta = data['plugins'][0]
    plugin = CMSPlugin.objects.select_related('placeholder').get(pk=plugin_meta.pk)

    if data['parent_id']:
        parent = CMSPlugin.objects.get(pk=data['parent_id'])
    else:
        parent = None

    source_placeholder = plugin.placeholder

    if action.placeholder.pk != source_placeholder.pk:
        target_placeholder = action.placeholder
    else:
        target_placeholder = None

    source_placeholder.move_plugin(
        plugin,
        target_position=plugin_meta.position,
        target_placeholder=target_placeholder,
        target_plugin=parent,
    )
    source_placeholder.clear_cache(action.language)

    if target_placeholder:
        target_placeholder.clear_cache(action.language)


def undo_add_plugin(action):
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']

    # Only delete plugins who are direct children (or parent-less) of the
    # target parent.
    # This allows for cascade delete of the children of these plugins.
    plugin_ids = [plugin.pk for plugin in post_data['plugins']
                  if plugin.parent_id == parent_id]
    _delete_plugins(action, plugin_ids=plugin_ids)


def redo_add_plugin(action):
    post_data = action.get_post_action_data()
    _restore_archived_plugins(action, data=post_data)


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
    _restore_archived_plugins(action, data=pre_data)


def redo_delete_plugin(action):
    post_data = action.get_post_action_data()
    plugin_ids = [plugin.pk for plugin in post_data['plugins']]
    _delete_plugins(action, plugin_ids=plugin_ids)


def undo_move_plugin(action):
    _move_plugin(action, data=action.get_pre_action_data())


def redo_move_plugin(action):
    _move_plugin(action, data=action.get_post_action_data())


def undo_move_out_plugin(action):
    # Moves the plugin from the placeholder it was moved to
    # back into this action's (source) placeholder.
    # This single move also restores the positions in the
    # other placeholder.
    _move_plugin(action, data=action.get_pre_action_data())


def redo_move_out_plugin(action):
    # No-op. Operations are redone in descending action order, so the
    # MOVE_IN_PLUGIN action (order=2) has already moved the plugin to
    # the target placeholder and fixed both placeholders' positions.
    pass


def undo_move_in_plugin(action):
    # No-op. Operations are undone in ascending action order, so the
    # MOVE_OUT_PLUGIN action (order=1) has already moved the plugin back
    # to the source placeholder and fixed both placeholders' positions.
    pass


def redo_move_in_plugin(action):
    # Moves the plugin from the source placeholder back into this
    # action's (target) placeholder.
    _move_plugin(action, data=action.get_post_action_data())


def undo_move_plugin_in_to_clipboard(action):
    # clear the clipboard
    action.placeholder.clear()
    action.placeholder.clear_cache(action.language)


def redo_move_plugin_in_to_clipboard(action):
    post_data = action.get_post_action_data()

    # clear the clipboard
    action.placeholder.clear()

    # Recreate the cut plugins on the clipboard.
    # The MOVE_PLUGIN_OUT_TO_CLIPBOARD action (order=2) has already
    # deleted them from the source placeholder (redo runs in descending
    # action order), so their primary keys are free to be reused.
    _restore_archived_plugins(action, data=post_data)


def undo_move_plugin_out_to_clipboard(action):
    pre_data = action.get_pre_action_data()

    # Plugin was moved to the clipboard.
    # Recreate it (and its descendants) in the source placeholder.
    # The MOVE_PLUGIN_IN_TO_CLIPBOARD action (order=1) has already
    # cleared the clipboard (undo runs in ascending action order),
    # so the original primary keys are free to be reused.
    _restore_archived_plugins(action, data=pre_data)


def redo_move_plugin_out_to_clipboard(action):
    pre_data = action.get_pre_action_data()
    root_pks = [plugin.pk for plugin in pre_data['plugins']
                if plugin.parent_id == pre_data['parent_id']]
    _delete_plugins(action, plugin_ids=root_pks)


def undo_paste_plugin(action):
    post_data = action.get_post_action_data()
    parent_id = post_data['parent_id']
    plugin_ids = [plugin.pk for plugin in post_data['plugins']
                  if plugin.parent_id == parent_id]
    _delete_plugins(action, plugin_ids=plugin_ids)


def redo_paste_plugin(action):
    post_data = action.get_post_action_data()
    _restore_archived_plugins(action, data=post_data)


def undo_paste_placeholder(action):
    post_data = action.get_post_action_data()
    plugin_ids = [plugin.pk for plugin in post_data['plugins']
                  if not plugin.parent_id]
    _delete_plugins(action, plugin_ids=plugin_ids)


def redo_paste_placeholder(action):
    post_data = action.get_post_action_data()
    _restore_archived_plugins(action, data=post_data)


def undo_add_plugins_from_placeholder(action):
    post_data = action.get_post_action_data()
    plugin_ids = [plugin.pk for plugin in post_data['plugins']
                  if not plugin.parent_id]
    _delete_plugins(action, plugin_ids=plugin_ids)


def redo_add_plugins_from_placeholder(action):
    post_data = action.get_post_action_data()
    _restore_archived_plugins(action, data=post_data)


def undo_clear_placeholder(action):
    pre_data = action.get_pre_action_data()
    _restore_archived_plugins(action, data=pre_data)


def redo_clear_placeholder(action):
    action.placeholder.clear(action.language)
    action.placeholder.clear_cache(action.language)
