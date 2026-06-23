from cms import operations

from djangocms_history import actions
from djangocms_history.models import PlaceholderOperation

from .base import HistoryTestCase


class OperationRecordingTestCase(HistoryTestCase):

    def test_add_plugin_records_operation(self):
        with self.login_user_context(self.superuser):
            plugin = self.add_plugin_via_endpoint()

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, operations.ADD_PLUGIN)
        self.assertEqual(operation.language, 'en')
        self.assertEqual(operation.origin, self.page.get_absolute_url('en'))
        self.assertEqual(operation.user, self.superuser)
        self.assertEqual(operation.site_id, 1)
        self.assertTrue(operation.is_applied)
        self.assertFalse(operation.is_archived)
        self.assertTrue(operation.token)
        self.assertTrue(operation.user_session_key)

        action = operation.actions.get()
        self.assertEqual(action.action, actions.ADD_PLUGIN)
        self.assertEqual(action.placeholder, self.placeholder)
        self.assertEqual(action.language, 'en')
        self.assertEqual(action.order, 1)

        pre_data = action.get_pre_action_data()
        self.assertEqual(pre_data['parent_id'], None)

        post_data = action.get_post_action_data()
        self.assertEqual(post_data['parent_id'], None)
        archived = post_data['plugins'][0]
        self.assertEqual(archived.pk, plugin.pk)
        self.assertEqual(archived.position, 1)
        self.assertEqual(archived.plugin_type, 'LinkPlugin')
        self.assertEqual(archived.data['name'], 'A Link')

    def test_add_nested_plugin_records_parent(self):
        parent = self.add_plugin()

        with self.login_user_context(self.superuser):
            plugin = self.add_plugin_via_endpoint(parent=parent, name='child')

        action = self.latest_operation().actions.get()
        post_data = action.get_post_action_data()
        self.assertEqual(post_data['parent_id'], parent.pk)
        self.assertEqual(post_data['plugins'][0].pk, plugin.pk)
        self.assertEqual(post_data['plugins'][0].position, 2)

    def test_change_plugin_records_operation(self):
        plugin = self.add_plugin(name='before')

        with self.login_user_context(self.superuser):
            self.change_plugin_via_endpoint(
                plugin,
                name='after',
                external_link='https://www.django-cms.org',
            )

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, operations.CHANGE_PLUGIN)

        action = operation.actions.get()
        self.assertEqual(action.action, actions.CHANGE_PLUGIN)
        self.assertEqual(action.get_pre_action_data()['plugins'][0].data['name'], 'before')
        self.assertEqual(action.get_post_action_data()['plugins'][0].data['name'], 'after')

    def test_delete_plugin_records_subtree(self):
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')
        grandchild = self.add_plugin(parent=child, name='grandchild')

        with self.login_user_context(self.superuser):
            self.delete_plugin_via_endpoint(parent)

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, operations.DELETE_PLUGIN)

        action = operation.actions.get()
        self.assertEqual(action.action, actions.DELETE_PLUGIN)

        pre_data = action.get_pre_action_data()
        self.assertEqual(pre_data['parent_id'], None)
        archived = pre_data['plugins']
        self.assertEqual(
            [(p.pk, p.parent_id, p.position) for p in archived],
            [(parent.pk, None, 1), (child.pk, parent.pk, 2), (grandchild.pk, child.pk, 3)],
        )
        # Full data is stored for the whole subtree
        self.assertEqual(archived[1].data['name'], 'child')

        post_data = action.get_post_action_data()
        self.assertEqual([p.pk for p in post_data['plugins']], [parent.pk])

    def test_move_plugin_within_placeholder(self):
        self.add_plugin(name='first')
        second = self.add_plugin(name='second')

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(second, target_position=1)

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, operations.MOVE_PLUGIN)

        action = operation.actions.get()
        self.assertEqual(action.action, actions.MOVE_PLUGIN)

        pre_meta = action.get_pre_action_data()['plugins'][0]
        self.assertEqual((pre_meta.pk, pre_meta.position), (second.pk, 2))

        post_meta = action.get_post_action_data()['plugins'][0]
        self.assertEqual((post_meta.pk, post_meta.position), (second.pk, 1))

    def test_move_plugin_across_placeholders_creates_two_actions(self):
        parent = self.add_plugin(name='parent')
        self.add_plugin(parent=parent, name='child')
        self.add_plugin(placeholder=self.sidebar, name='sidebar plugin')

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(
                parent,
                target_position=2,
                target_placeholder=self.sidebar,
            )

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, operations.MOVE_PLUGIN)

        move_out = operation.actions.get(action=actions.MOVE_OUT_PLUGIN)
        move_in = operation.actions.get(action=actions.MOVE_IN_PLUGIN)
        self.assertEqual(move_out.order, 1)
        self.assertEqual(move_in.order, 2)
        self.assertEqual(move_out.placeholder, self.placeholder)
        self.assertEqual(move_in.placeholder, self.sidebar)

        # Source side: pre-move position and parent in the source placeholder
        out_pre = move_out.get_pre_action_data()
        self.assertEqual(out_pre['parent_id'], None)
        self.assertEqual(out_pre['plugins'][0].pk, parent.pk)
        self.assertEqual(out_pre['plugins'][0].position, 1)
        # The post data of the move-out action must hold the *source* parent,
        # not the target parent sent by the (buggy) post signal kwargs
        self.assertEqual(move_out.get_post_action_data()['parent_id'], None)

        # Target side: post-move position in the target placeholder
        in_post = move_in.get_post_action_data()
        self.assertEqual(in_post['parent_id'], None)
        self.assertEqual(in_post['plugins'][0].pk, parent.pk)
        self.assertEqual(in_post['plugins'][0].position, 2)

    def test_cut_plugin_records_clipboard_actions(self):
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')

        with self.login_user_context(self.superuser):
            self.cut_plugin_via_endpoint(parent)

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, operations.CUT_PLUGIN)

        clipboard_action = operation.actions.get(action=actions.MOVE_PLUGIN_IN_TO_CLIPBOARD)
        source_action = operation.actions.get(action=actions.MOVE_PLUGIN_OUT_TO_CLIPBOARD)
        self.assertEqual(clipboard_action.order, 1)
        self.assertEqual(source_action.order, 2)
        self.assertEqual(clipboard_action.placeholder, self.get_clipboard())
        self.assertEqual(source_action.placeholder, self.placeholder)

        # Clipboard data is renumbered to 1..n with a parent-less root
        clipboard_plugins = clipboard_action.get_post_action_data()['plugins']
        self.assertEqual(
            [(p.pk, p.parent_id, p.position) for p in clipboard_plugins],
            [(parent.pk, None, 1), (child.pk, parent.pk, 2)],
        )
        # Full data is stored so redo can recreate the rows
        self.assertEqual(clipboard_plugins[0].data['name'], 'parent')

        # Source data keeps the original positions
        source_plugins = source_action.get_pre_action_data()['plugins']
        self.assertEqual(
            [(p.pk, p.parent_id, p.position) for p in source_plugins],
            [(parent.pk, None, 1), (child.pk, parent.pk, 2)],
        )

    def test_paste_plugin_records_operation(self):
        existing = self.add_plugin(name='existing')

        with self.login_user_context(self.superuser):
            clipboard_root = self.copy_plugin_to_clipboard_via_endpoint(existing)
            new_plugin = self.paste_plugin_via_endpoint(
                clipboard_root,
                target_placeholder=self.placeholder,
                target_position=2,
            )

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, operations.PASTE_PLUGIN)

        action = operation.actions.get()
        self.assertEqual(action.action, actions.PASTE_PLUGIN)
        post_data = action.get_post_action_data()
        self.assertEqual(post_data['parent_id'], None)
        self.assertEqual(post_data['plugins'][0].pk, new_plugin.pk)
        self.assertEqual(post_data['plugins'][0].position, 2)

    def test_paste_placeholder_records_operation(self):
        self.add_plugin(name='first')
        self.add_plugin(name='second')

        with self.login_user_context(self.superuser):
            reference = self.copy_placeholder_to_clipboard_via_endpoint(self.placeholder)
            self.paste_plugin_via_endpoint(
                reference,
                target_placeholder=self.sidebar,
                target_position=1,
            )

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, operations.PASTE_PLACEHOLDER)

        action = operation.actions.get()
        self.assertEqual(action.action, actions.PASTE_PLACEHOLDER)
        post_plugins = action.get_post_action_data()['plugins']
        self.assertEqual(len(post_plugins), 2)
        self.assertEqual([p.position for p in post_plugins], [1, 2])
        self.assertEqual(
            sorted([p.data['name'] for p in post_plugins]),
            ['first', 'second'],
        )

    def test_copy_from_language_records_operation(self):
        self.add_plugin(name='english', language='en')

        with self.login_user_context(self.superuser):
            self.copy_from_language_via_endpoint(
                self.placeholder,
                source_language='en',
                target_language='de',
            )

        operation = self.latest_operation()
        self.assertEqual(
            operation.operation_type,
            operations.ADD_PLUGINS_FROM_PLACEHOLDER,
        )

        action = operation.actions.get()
        self.assertEqual(action.action, actions.ADD_PLUGINS_FROM_PLACEHOLDER)
        self.assertEqual(action.language, 'de')
        post_plugins = action.get_post_action_data()['plugins']
        self.assertEqual(len(post_plugins), 1)
        self.assertEqual(post_plugins[0].data['name'], 'english')

    def test_clear_placeholder_records_operation(self):
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')
        root = self.add_plugin(name='root')

        with self.login_user_context(self.superuser):
            self.clear_placeholder_via_endpoint(self.placeholder)

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, operations.CLEAR_PLACEHOLDER)

        action = operation.actions.get()
        self.assertEqual(action.action, actions.CLEAR_PLACEHOLDER)

        pre_plugins = action.get_pre_action_data()['plugins']
        self.assertEqual(
            [(p.pk, p.parent_id, p.position) for p in pre_plugins],
            [(parent.pk, None, 1), (child.pk, parent.pk, 2), (root.pk, None, 3)],
        )

        post_plugins = action.get_post_action_data()['plugins']
        self.assertEqual(
            sorted(p.pk for p in post_plugins),
            sorted([parent.pk, root.pk]),
        )

    def test_cms_history_flag_suppresses_recording(self):
        endpoint = self.get_add_plugin_uri(self.placeholder, 'LinkPlugin', language='en')
        endpoint += '&cms_history=0'

        with self.login_user_context(self.superuser):
            response = self.client.post(endpoint, {
                'name': 'A Link',
                'external_link': 'https://www.django-cms.org',
            })
            self.assertEqual(response.status_code, 200)

        self.assertEqual(PlaceholderOperation.objects.count(), 0)

    def test_new_operation_archives_operations_on_other_paths(self):
        other_page, other_placeholder = self.create_other_page()

        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
            first = self.latest_operation()
            self.add_plugin_via_endpoint(placeholder=other_placeholder)

        first.refresh_from_db()
        self.assertTrue(first.is_archived)

    def test_operation_by_other_user_archives_existing(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()

        first = self.latest_operation()
        other_admin = self._create_user('other_admin', is_staff=True, is_superuser=True)

        with self.login_user_context(other_admin):
            self.add_plugin_via_endpoint()

        first.refresh_from_db()
        self.assertTrue(first.is_archived)
