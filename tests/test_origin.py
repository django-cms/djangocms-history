from urllib.parse import urlencode

from cms.toolbar.utils import (
    get_object_edit_url,
    get_object_preview_url,
    get_object_structure_url,
)
from cms.utils.urlutils import admin_reverse

from djangocms_history.helpers import get_operation_origin

from .base import HistoryTestCase


class OperationOriginTestCase(HistoryTestCase):

    def test_object_endpoints_share_canonical_origin(self):
        edit = get_operation_origin(get_object_edit_url(self.page_content, 'en'))
        structure = get_operation_origin(get_object_structure_url(self.page_content, 'en'))
        preview = get_operation_origin(get_object_preview_url(self.page_content, 'en'))

        # All endpoints of the same object map to one "<ct>:<pk>" value.
        self.assertRegex(edit, r'^\d+:\d+$')
        self.assertEqual(edit, structure)
        self.assertEqual(edit, preview)

    def test_non_object_path_falls_back_to_path(self):
        self.assertEqual(get_operation_origin('/en/home/'), '/en/home/')
        self.assertEqual(get_operation_origin('/some/unknown/'), '/some/unknown/')


class StructureBoardStateTestCase(HistoryTestCase):
    """
    The undo/redo buttons must reflect the correct state on the structure
    endpoint, not only the edit endpoint. The two endpoints have different
    request paths, so operations are matched via the canonical object origin.
    """

    def _add_plugin_with_cms_path(self, cms_path):
        # Mimic the real frontend, which sends the browser path (the edit or
        # structure URL) as cms_path -- not the friendly page URL.
        endpoint = admin_reverse('cms_placeholder_add_plugin') + '?' + urlencode({
            'plugin_type': 'LinkPlugin',
            'placeholder_id': self.placeholder.pk,
            'plugin_language': 'en',
            'cms_path': cms_path,
            'plugin_position': 1,
        })
        response = self.client.post(endpoint, {
            'name': 'hello',
            'external_link': 'https://www.django-cms.org',
        })
        self.assertEqual(response.status_code, 200)

    def _undo_enabled(self, url):
        content = self.client.get(url).content.decode()
        index = content.find('history-button undo')
        self.assertNotEqual(index, -1, 'undo button is missing')
        snippet = content[max(0, index - 220):index + 40]
        return 'cms-btn-disabled' not in snippet

    def test_content_mode_operation_visible_on_both_endpoints(self):
        edit_url = get_object_edit_url(self.page_content, 'en')
        structure_url = get_object_structure_url(self.page_content, 'en')

        with self.login_user_context(self.superuser):
            # Operation performed in content mode (cms_path = edit URL).
            self._add_plugin_with_cms_path(edit_url)

            self.assertTrue(self._undo_enabled(edit_url))
            self.assertTrue(self._undo_enabled(structure_url))

    def test_structure_mode_operation_visible_on_both_endpoints(self):
        edit_url = get_object_edit_url(self.page_content, 'en')
        structure_url = get_object_structure_url(self.page_content, 'en')

        with self.login_user_context(self.superuser):
            # Operation performed in structure mode (cms_path = structure URL).
            self._add_plugin_with_cms_path(structure_url)

            self.assertTrue(self._undo_enabled(edit_url))
            self.assertTrue(self._undo_enabled(structure_url))
