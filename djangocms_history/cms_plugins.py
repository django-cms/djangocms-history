from cms.constants import PLUGIN_MOVE_ACTION
from cms.plugin_base import CMSPluginBase


# Patch the plugin action_options to force the cms
# to reload the page once a plugin has been moved.
# This is needed to update the undo/redo buttons.
# A better option is to update the buttons via js,
# this however will come in a later stage.
CMSPluginBase.action_options[PLUGIN_MOVE_ACTION] = {'requires_reload': True}
