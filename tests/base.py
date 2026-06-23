from django.urls import reverse

from cms.api import add_plugin, create_page
from cms.models import Placeholder, UserSettings
from cms.test_utils.testcases import CMSTestCase

from djangocms_history.models import PlaceholderOperation


class HistoryTestCase(CMSTestCase):
    """
    Shared helpers for the djangocms-history test suite.

    Operations are driven through the real django CMS placeholder admin
    endpoints so that the operation signals carry exactly the kwargs the
    CMS sends in production.
    """

    def setUp(self):
        self.superuser = self.get_superuser()
        self.page = create_page('home', 'page.html', 'en', created_by=self.superuser)
        # Use the admin manager: with djangocms-versioning installed the
        # default manager hides content that has no published version.
        from cms.models import PageContent

        self.page_content = PageContent.admin_manager.get(page=self.page, language='en')
        # Materialize the template's placeholder slots
        self.page_content.rescan_placeholders()
        self.placeholder = self.page_content.placeholders.get(slot='content')
        self.sidebar = self.page_content.placeholders.get(slot='sidebar')

    # -- tree inspection ---------------------------------------------------

    def tree(self, placeholder, language='en'):
        """
        Returns the full plugin tree of a placeholder as a list of
        (pk, parent_id, position, plugin_type) tuples ordered by position.
        """
        return list(
            placeholder
            .get_plugins(language)
            .order_by('position')
            .values_list('pk', 'parent_id', 'position', 'plugin_type')
        )

    def operations(self):
        return PlaceholderOperation.objects.order_by('date_created', 'pk')

    def latest_operation(self):
        return PlaceholderOperation.objects.latest()

    # -- fixtures ----------------------------------------------------------

    def add_plugin(self, placeholder=None, parent=None, language='en', **data):
        """
        Creates a Link plugin directly through the cms api (no signals,
        no history) - used to build fixtures.
        """
        data.setdefault('name', 'A Link')
        data.setdefault('external_link', 'https://www.django-cms.org')
        return add_plugin(
            placeholder or self.placeholder,
            'LinkPlugin',
            language,
            target=parent,
            **data
        )

    def create_other_page(self, title='other'):
        """
        Returns (page, content placeholder) for a freshly created page.
        """
        from cms.models import PageContent

        page = create_page(title, 'page.html', 'en', created_by=self.superuser)
        content = PageContent.admin_manager.get(page=page, language='en')
        content.rescan_placeholders()
        placeholder = content.placeholders.get(slot='content')
        return page, placeholder

    def get_clipboard(self, user=None):
        user = user or self.superuser
        try:
            user_settings = UserSettings.objects.get(user=user)
        except UserSettings.DoesNotExist:
            clipboard = Placeholder.objects.create(slot='clipboard')
            user_settings = UserSettings.objects.create(
                user=user,
                language='en',
                clipboard=clipboard,
            )
        return user_settings.clipboard

    # -- endpoint drivers --------------------------------------------------
    # All drivers expect the caller to be inside login_user_context().

    def add_plugin_via_endpoint(self, placeholder=None, parent=None,
                                language='en', position=None, **data):
        placeholder = placeholder or self.placeholder
        data.setdefault('name', 'A Link')
        data.setdefault('external_link', 'https://www.django-cms.org')
        endpoint = self.get_add_plugin_uri(
            placeholder,
            plugin_type='LinkPlugin',
            language=language,
            parent=parent,
            position=position,
        )
        response = self.client.post(endpoint, data)
        self.assertEqual(response.status_code, 200)
        return placeholder.get_plugins(language).latest('pk')

    def change_plugin_via_endpoint(self, plugin, language='en', **data):
        endpoint = self.get_change_plugin_uri(plugin, language=language)
        response = self.client.post(endpoint, data)
        self.assertEqual(response.status_code, 200)
        return plugin.reload()

    def delete_plugin_via_endpoint(self, plugin, language='en'):
        endpoint = self.get_delete_plugin_uri(plugin, language=language)
        response = self.client.post(endpoint, {'post': 'true'})
        # django CMS 4.1 redirects on success, 5.x renders a confirm frame
        self.assertIn(response.status_code, (200, 302))

    def move_plugin_via_endpoint(self, plugin, target_position, parent=None,
                                 target_placeholder=None, language='en'):
        endpoint = self.get_move_plugin_uri(plugin, language=language)
        data = {
            'plugin_id': plugin.pk,
            'target_language': language,
            'target_position': target_position,
        }

        if parent:
            data['plugin_parent'] = parent.pk

        if target_placeholder:
            data['placeholder_id'] = target_placeholder.pk

        response = self.client.post(endpoint, data)
        self.assertEqual(response.status_code, 200)
        return plugin.reload()

    def cut_plugin_via_endpoint(self, plugin, language='en'):
        clipboard = self.get_clipboard()
        endpoint = self.get_move_plugin_uri(plugin, language=language)
        data = {
            'plugin_id': plugin.pk,
            'target_language': language,
            'placeholder_id': clipboard.pk,
        }
        response = self.client.post(endpoint, data)
        self.assertEqual(response.status_code, 200)
        return plugin.reload()

    def paste_plugin_via_endpoint(self, clipboard_plugin, target_placeholder,
                                  target_position, parent=None, language='en'):
        # The cms_path must point at the page being edited (the target),
        # not at the clipboard the plugin currently lives in.
        from urllib.parse import urlencode

        from cms.utils.urlutils import admin_reverse

        if target_placeholder.page:
            path = target_placeholder.page.get_absolute_url(language)
        else:
            path = f'/{language}/'

        endpoint = admin_reverse('cms_placeholder_move_plugin')
        endpoint += '?' + urlencode({'cms_path': path})
        data = {
            'plugin_id': clipboard_plugin.pk,
            'target_language': language,
            'target_position': target_position,
            'placeholder_id': target_placeholder.pk,
            'move_a_copy': 'true',
        }

        if parent:
            data['plugin_parent'] = parent.pk

        response = self.client.post(endpoint, data)
        self.assertEqual(response.status_code, 200)
        return target_placeholder.get_plugins(language).latest('pk')

    def copy_plugin_to_clipboard_via_endpoint(self, plugin, language='en'):
        clipboard = self.get_clipboard()
        endpoint = self.get_copy_plugin_uri(plugin, language=language)
        data = {
            'source_language': language,
            'source_placeholder_id': plugin.placeholder.pk,
            'source_plugin_id': plugin.pk,
            'target_language': language,
            'target_placeholder_id': clipboard.pk,
        }
        response = self.client.post(endpoint, data)
        self.assertEqual(response.status_code, 200)
        return clipboard.get_plugins(language).get(parent__isnull=True)

    def copy_placeholder_to_clipboard_via_endpoint(self, placeholder, language='en'):
        clipboard = self.get_clipboard()
        endpoint = self.get_copy_placeholder_uri(placeholder, language=language)
        data = {
            'source_language': language,
            'source_placeholder_id': placeholder.pk,
            'target_language': language,
            'target_placeholder_id': clipboard.pk,
        }
        response = self.client.post(endpoint, data)
        self.assertEqual(response.status_code, 200)
        # The clipboard now holds a PlaceholderPlugin (reference)
        return clipboard.get_plugins(language).get(plugin_type='PlaceholderPlugin')

    def copy_from_language_via_endpoint(self, placeholder, source_language,
                                        target_language):
        endpoint = self.get_copy_placeholder_uri(placeholder, language=target_language)
        data = {
            'source_language': source_language,
            'source_placeholder_id': placeholder.pk,
            'target_language': target_language,
            'target_placeholder_id': placeholder.pk,
        }
        response = self.client.post(endpoint, data)
        self.assertEqual(response.status_code, 200)

    def clear_placeholder_via_endpoint(self, placeholder, language='en'):
        endpoint = self.get_clear_placeholder_url(placeholder, language=language)
        response = self.client.post(endpoint, {'post': 'true'})
        # django CMS 4.1 redirects on success, 5.x renders a confirm frame
        self.assertIn(response.status_code, (200, 302))

    # -- undo / redo -------------------------------------------------------

    def post_undo(self, language='en', path=None):
        endpoint = reverse('admin:djangocms_history_undo')
        data = {
            'language': language,
            'cms_path': path or self.page.get_absolute_url(language),
        }
        return self.client.post(endpoint, data)

    def post_redo(self, language='en', path=None):
        endpoint = reverse('admin:djangocms_history_redo')
        data = {
            'language': language,
            'cms_path': path or self.page.get_absolute_url(language),
        }
        return self.client.post(endpoint, data)

    def undo(self, language='en', path=None):
        response = self.post_undo(language, path)
        self.assertEqual(
            response.status_code, 204,
            'undo failed: {} / operations: {}'.format(
                response.content,
                list(PlaceholderOperation.objects.values(
                    'pk', 'operation_type', 'origin', 'language',
                    'is_applied', 'is_archived',
                )),
            ),
        )

    def redo(self, language='en', path=None):
        response = self.post_redo(language, path)
        self.assertEqual(
            response.status_code, 204,
            'redo failed: {} / operations: {}'.format(
                response.content,
                list(PlaceholderOperation.objects.values(
                    'pk', 'operation_type', 'origin', 'language',
                    'is_applied', 'is_archived',
                )),
            ),
        )
