"""
Actions are internal to djangocms-history
A placeholder operation can have multiple actions.

Example:
    User moves plugin from placeholder A to placeholder B
    This creates a MOVE_PLUGIN placeholder operation and this operation
    contains two actions:
        MOVE_OUT_PLUGIN -> Move plugin out of placeholder A
        MOVE_IN_PLUGIN -> Move plugin into placeholder B
"""
from __future__ import unicode_literals


ADD_PLUGIN = 'add_plugin'
CHANGE_PLUGIN = 'change_plugin'
DELETE_PLUGIN = 'delete_plugin'
MOVE_PLUGIN = 'move_plugin'
MOVE_OUT_PLUGIN = 'move_out_plugin'
MOVE_IN_PLUGIN = 'move_in_plugin'
PASTE_PLUGIN = 'paste_plugin'
PASTE_PLACEHOLDER = 'paste_placeholder'
ADD_PLUGINS_FROM_PLACEHOLDER = 'add_plugins_from_placeholder'
CLEAR_PLACEHOLDER = 'clear_placeholder'

# This action is bound to the clipboard
# Its triggered when a plugin is moved from a placeholder
# into the clipboard
MOVE_PLUGIN_OUT_TO_CLIPBOARD = 'move_plugin_out_to_clipboard'

# This action is triggered when a plugin is moved from a placeholder
# into the clipboard. Its bound to the source placeholder.
MOVE_PLUGIN_IN_TO_CLIPBOARD = 'move_plugin_in_to_clipboard'
