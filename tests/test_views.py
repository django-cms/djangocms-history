import json
import re
from unittest import skipUnless
from unittest.mock import patch

from django.urls import reverse

from djangocms_history.models import PlaceholderOperation
from djangocms_history.views import SUPPORTS_DATA_BRIDGE

from .base import HistoryTestCase


class UndoRedoViewTestCase(HistoryTestCase):

    def setUp(self):
        super().setUp()
        self.undo_url = reverse('admin:djangocms_history_undo')
        self.redo_url = reverse('admin:djangocms_history_redo')
        self.valid_data = {
            'language': 'en',
            'cms_path': self.page.get_absolute_url('en'),
        }

    def test_anonymous_user_denied(self):
        response = self.client.post(self.undo_url, self.valid_data)
        self.assertEqual(response.status_code, 403)

    def test_non_staff_user_denied(self):
        user = self._create_user('regular', is_staff=False)

        with self.login_user_context(user):
            response = self.client.post(self.undo_url, self.valid_data)

        self.assertEqual(response.status_code, 403)

    def test_get_not_allowed(self):
        with self.login_user_context(self.superuser):
            response = self.client.get(self.undo_url)

        self.assertEqual(response.status_code, 405)

    def test_invalid_form_returns_400(self):
        with self.login_user_context(self.superuser):
            response = self.client.post(self.undo_url, {})
            self.assertEqual(response.status_code, 400)

            response = self.client.post(self.undo_url, {
                'language': 'xx',
                'cms_path': '/en/',
            })
            self.assertEqual(response.status_code, 400)

    def test_no_operation_returns_400(self):
        with self.login_user_context(self.superuser):
            response = self.client.post(self.undo_url, self.valid_data)
            self.assertEqual(response.status_code, 400)

            response = self.client.post(self.redo_url, self.valid_data)
            self.assertEqual(response.status_code, 400)

    def test_undo_and_redo_flip_is_applied(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()

            operation = self.latest_operation()
            self.assertTrue(operation.is_applied)

            # Undoing the add deletes the plugin, so there is nothing to
            # render: an empty 204.
            response = self.client.post(self.undo_url, self.valid_data)
            self.assertEqual(response.status_code, 204)
            operation.refresh_from_db()
            self.assertFalse(operation.is_applied)

            # Redoing re-adds the plugin. On django CMS 5.1+ the close frame
            # (data bridge) is returned; on earlier versions it's an empty 204.
            response = self.client.post(self.redo_url, self.valid_data)
            expected = 200 if SUPPORTS_DATA_BRIDGE else 204
            self.assertEqual(response.status_code, expected)
            operation.refresh_from_db()
            self.assertTrue(operation.is_applied)

    def test_non_editable_operation_returns_403(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()

            with patch.object(PlaceholderOperation, 'is_editable', return_value=False):
                response = self.client.post(self.undo_url, self.valid_data)

            self.assertEqual(response.status_code, 403)
            # The operation was not applied
            self.assertTrue(self.latest_operation().is_applied)
            self.assertEqual(len(self.tree(self.placeholder)), 1)


@skipUnless(SUPPORTS_DATA_BRIDGE, 'data bridge requires django CMS 5.1+')
class CloseFrameResponseTestCase(HistoryTestCase):
    """
    Undo/redo returns the affected plugin's close frame (carrying the data
    bridge) when the result is a single plugin add or edit, and an empty 204
    otherwise.
    """

    def data_bridge(self, response):
        self.assertEqual(response.status_code, 200)
        match = re.search(
            rb'<script id="data-bridge"[^>]*>(.*?)</script>',
            response.content,
            re.DOTALL,
        )
        self.assertIsNotNone(match, 'no data bridge in response')
        return json.loads(match.group(1).decode())

    def test_redo_add_returns_add_close_frame(self):
        with self.login_user_context(self.superuser):
            plugin = self.add_plugin_via_endpoint()
            self.post_undo()  # undo the add -> plugin deleted
            response = self.post_redo()  # redo the add -> plugin recreated

        bridge = self.data_bridge(response)
        self.assertEqual(bridge['action'], 'add')
        self.assertEqual(bridge['plugin_id'], plugin.pk)

    def test_undo_change_returns_edit_close_frame(self):
        plugin = self.add_plugin(name='before')

        with self.login_user_context(self.superuser):
            self.change_plugin_via_endpoint(
                plugin,
                name='after',
                external_link='https://www.django-cms.org',
            )
            response = self.post_undo()

        bridge = self.data_bridge(response)
        self.assertEqual(bridge['action'], 'edit')
        self.assertEqual(bridge['plugin_id'], plugin.pk)

    def test_undo_delete_returns_add_close_frame(self):
        plugin = self.add_plugin(name='delete me')

        with self.login_user_context(self.superuser):
            self.delete_plugin_via_endpoint(plugin)
            response = self.post_undo()  # restore the plugin

        bridge = self.data_bridge(response)
        self.assertEqual(bridge['action'], 'add')
        self.assertEqual(bridge['plugin_id'], plugin.pk)

    def test_undo_add_returns_empty(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
            response = self.post_undo()  # add undone -> plugin gone

        self.assertEqual(response.status_code, 204)

    def test_move_returns_move_response(self):
        self.add_plugin(name='first')
        second = self.add_plugin(name='second')

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(second, target_position=1)
            response = self.post_undo()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        data = json.loads(response.content)
        self.assertEqual(data['plugin_id'], second.pk)
        self.assertEqual(data['target_position'], 2)
        self.assertFalse(data['move_a_copy'])
        # Same-placeholder move: source and target are the same placeholder
        self.assertEqual(data['placeholder_id'], self.placeholder.pk)
        self.assertEqual(data['source_placeholder_id'], self.placeholder.pk)
        self.assertIn('html', data)

    def test_cross_placeholder_move_reports_source(self):
        plugin = self.add_plugin(name='moves')

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(
                plugin, target_position=1, target_placeholder=self.sidebar,
            )
            response = self.post_undo()  # moved back to the content placeholder

        data = json.loads(response.content)
        self.assertEqual(data['plugin_id'], plugin.pk)
        self.assertEqual(data['placeholder_id'], self.placeholder.pk)
        self.assertEqual(data['source_placeholder_id'], self.sidebar.pk)

    def test_move_out_of_parent_refreshes_old_parent_content(self):
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')

        with self.login_user_context(self.superuser):
            # Move the child out of its parent into the sidebar.
            self.move_plugin_via_endpoint(
                child, target_position=1, target_placeholder=self.sidebar,
            )
            self.post_undo()             # child back under parent
            response = self.post_redo()  # child to sidebar; parent loses a child

        data = json.loads(response.content)
        content = data['content']
        placeholder_ids = [entry['placeholder_id'] for entry in content]

        # One content entry for the moved child in the sidebar, and one for the
        # old parent re-rendered in the (source) content placeholder.
        self.assertIn(self.sidebar.pk, placeholder_ids)
        self.assertIn(self.placeholder.pk, placeholder_ids)
        # The moved subtree is the first entry and is flagged for insertion.
        self.assertEqual(content[0]['pluginIds'], [child.pk])
        self.assertTrue(content[0]['insert'])
        # 'plugin_order' is intentionally not sent (the core omits it too).
        self.assertNotIn('plugin_order', data)
