import json
import re
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from djangocms_history.models import PlaceholderAction, PlaceholderOperation
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

            # On django CMS 5.1+ both directions return a data bridge (undo a
            # "delete" frame, redo an "add" frame); earlier versions get 204.
            expected = 200 if SUPPORTS_DATA_BRIDGE else 204

            # Undoing the add deletes the plugin.
            response = self.client.post(self.undo_url, self.valid_data)
            self.assertEqual(response.status_code, expected)
            operation.refresh_from_db()
            self.assertFalse(operation.is_applied)

            # Redoing re-adds the plugin.
            response = self.client.post(self.redo_url, self.valid_data)
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


class ActionQueryCountTestCase(HistoryTestCase):
    """
    An undo/redo request inspects the operation's actions several times
    (editability check, replay, response building). The actions must be
    fetched from the database exactly once per request.
    """

    def assert_single_action_fetch(self, post):
        table = PlaceholderAction._meta.db_table

        with CaptureQueriesContext(connection) as ctx:
            response = post()

        self._assert_undo_redo_ok(response, 'undo/redo')
        action_selects = [
            query['sql'] for query in ctx.captured_queries
            if query['sql'].startswith('SELECT') and table in query['sql']
        ]
        self.assertEqual(
            len(action_selects), 1,
            'expected a single action fetch, got:\n{}'.format(
                '\n'.join(action_selects),
            ),
        )

    def test_undo_and_redo_of_add_fetch_actions_once(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
            self.assert_single_action_fetch(self.post_undo)
            self.assert_single_action_fetch(self.post_redo)

    def test_undo_and_redo_of_move_fetch_actions_once(self):
        # A move exercises the most action inspections in one request:
        # editability, old-parent capture, replay and the move data bridge.
        self.add_plugin(name='first')
        second = self.add_plugin(name='second')

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(second, target_position=1)
            self.assert_single_action_fetch(self.post_undo)
            self.assert_single_action_fetch(self.post_redo)


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

    def test_undo_add_returns_delete_frame(self):
        with self.login_user_context(self.superuser):
            plugin = self.add_plugin_via_endpoint()
            response = self.post_undo()  # add undone -> plugin deleted

        bridge = self.data_bridge(response)
        self.assertEqual(bridge['action'], 'delete')
        self.assertEqual(bridge['plugin_id'], plugin.pk)
        self.assertTrue(bridge['deleted'])

    def test_redo_delete_returns_delete_frame(self):
        plugin = self.add_plugin(name='delete me')

        with self.login_user_context(self.superuser):
            self.delete_plugin_via_endpoint(plugin)
            self.post_undo()             # restore
            response = self.post_redo()  # delete again -> plugin gone

        bridge = self.data_bridge(response)
        self.assertEqual(bridge['action'], 'delete')
        self.assertEqual(bridge['plugin_id'], plugin.pk)

    def test_undo_paste_returns_delete_frame(self):
        existing = self.add_plugin(name='existing')

        with self.login_user_context(self.superuser):
            clipboard_root = self.copy_plugin_to_clipboard_via_endpoint(existing)
            pasted = self.paste_plugin_via_endpoint(
                clipboard_root,
                target_placeholder=self.placeholder,
                target_position=2,
            )
            response = self.post_undo()  # paste undone -> pasted plugin deleted

        bridge = self.data_bridge(response)
        self.assertEqual(bridge['action'], 'delete')
        self.assertEqual(bridge['plugin_id'], pasted.pk)

    def test_move_returns_move_response(self):
        self.add_plugin(name='first')
        second = self.add_plugin(name='second')

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(second, target_position=1)
            response = self.post_undo()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        data = json.loads(response.content)
        # The frontend requires an 'action' to recognise the JSON data bridge.
        self.assertEqual(data['action'], 'move')
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
        # The child moved to the top level of the sidebar.
        self.assertEqual(data['plugin_order'], [child.pk])


@skipUnless(SUPPORTS_DATA_BRIDGE, 'data bridge requires django CMS 5.1+')
class MoveOrderDataBridgeTestCase(HistoryTestCase):
    """
    Undoing a move restores the plugin order, and the move data bridge
    reflects the restored position of the moved plugin.
    """

    def order(self):
        return list(
            self.placeholder
            .get_plugins('en')
            .order_by('position')
            .values_list('pk', flat=True)
        )

    def positions(self, data):
        # {plugin_id: position} for every plugin described in the data bridge.
        return {p['plugin_id']: p['position'] for p in data['plugins']}

    def test_move_a_after_b_then_undo(self):
        a = self.add_plugin(name='a')  # position 1
        b = self.add_plugin(name='b')  # position 2

        with self.login_user_context(self.superuser):
            # Move a after b -> order becomes b, a.
            self.move_plugin_via_endpoint(a, target_position=2)
            self.assertEqual(self.order(), [b.pk, a.pk])

            # Undo -> order is a, b again.
            response = self.post_undo()
            self.assertEqual(self.order(), [a.pk, b.pk])

            # The data bridge reflects the restored order: a back at position 1.
            data = json.loads(response.content)
            self.assertEqual(data['action'], 'move')
            self.assertEqual(data['plugin_id'], a.pk)
            self.assertEqual(data['target_position'], 1)
            # 'plugins' describes the WHOLE placeholder so the client refreshes
            # every cached position (not just the moved plugin's).
            self.assertEqual(self.positions(data), {a.pk: 1, b.pk: 2})
            # plugin_order tells the structure board the full restored order,
            # so it can re-position the moved node (the DOM is still b, a).
            self.assertEqual(data['plugin_order'], [a.pk, b.pk])
            # The structure board markup is the moved plugin's drag item.
            self.assertIn('cms-draggable-{}'.format(a.pk), data['html'])

    def test_move_b_before_a_then_undo(self):
        a = self.add_plugin(name='a')  # position 1
        b = self.add_plugin(name='b')  # position 2

        with self.login_user_context(self.superuser):
            # Move b before a -> order becomes b, a.
            self.move_plugin_via_endpoint(b, target_position=1)
            self.assertEqual(self.order(), [b.pk, a.pk])

            # Undo -> order is a, b again.
            response = self.post_undo()
            self.assertEqual(self.order(), [a.pk, b.pk])

            # The data bridge reflects the restored order: b back at position 2.
            data = json.loads(response.content)
            self.assertEqual(data['action'], 'move')
            self.assertEqual(data['plugin_id'], b.pk)
            self.assertEqual(data['target_position'], 2)
            self.assertEqual(self.positions(data), {a.pk: 1, b.pk: 2})
            # plugin_order tells the structure board the full restored order,
            # so it can re-position the moved node (the DOM is still b, a).
            self.assertEqual(data['plugin_order'], [a.pk, b.pk])
            self.assertIn('cms-draggable-{}'.format(b.pk), data['html'])

    def test_move_to_front_undo_describes_all_sibling_positions(self):
        # Regression: the content insert point is located from sibling
        # positions, so the data bridge must report every plugin's restored
        # position, not only the moved one. Moving the last plugin to the
        # front and undoing is the case that exposes a stale sibling.
        a = self.add_plugin(name='a')  # position 1
        b = self.add_plugin(name='b')  # position 2
        c = self.add_plugin(name='c')  # position 3

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(c, target_position=1)  # c to front
            self.assertEqual(self.order(), [c.pk, a.pk, b.pk])

            response = self.post_undo()  # back to a, b, c
            self.assertEqual(self.order(), [a.pk, b.pk, c.pk])

            data = json.loads(response.content)
            self.assertEqual(data['plugin_id'], c.pk)
            # Every sibling's restored position is reported, so the moved
            # plugin's content lands after b (not before it).
            self.assertEqual(self.positions(data), {a.pk: 1, b.pk: 2, c.pk: 3})
            self.assertEqual(data['plugin_order'], [a.pk, b.pk, c.pk])
