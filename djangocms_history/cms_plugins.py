from cms.plugin_base import CMSPluginBase


try:
    # Patch the plugin action_options to force the cms
    # to reload the page once a plugin has been moved.
    # This is needed to update the undo/redo buttons.
    # A better option is to update the buttons via js,
    # this however will come in a later stage.
    CMSPluginBase.action_options['move'] = {'requires_reload': True}
except AttributeError:
    # django CMS 3.5 no longer supports reloading the page
    # on plugin actions.
    pass
