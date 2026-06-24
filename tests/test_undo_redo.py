from cms.models import CMSPlugin

from .base import HistoryTestCase


class UndoRedoRoundTripMixin:
    """
    Implements the standard round-trip check:

        tree before -> operation -> tree after
        undo  -> tree == before
        redo  -> tree == after
    """

    def assert_round_trip(self, placeholders=None, language='en'):
        # Must be called from within the same login_user_context() the
        # operation was performed in: a new login starts a new session,
        # which (by design) archives the previous session's operations.
        placeholders = placeholders or [self.placeholder]

        def snapshot():
            return [self.tree(p, language) for p in placeholders]

        after = snapshot()

        self.undo(language=language)
        undone = snapshot()
        self.assertEqual(undone, self.before, 'undo did not restore the original tree')

        self.redo(language=language)
        redone = snapshot()
        self.assertEqual(redone, after, 'redo did not restore the new tree')

        # Round-trip again to ensure the operation stays replayable
        self.undo(language=language)
        self.assertEqual(snapshot(), self.before)
        self.redo(language=language)
        self.assertEqual(snapshot(), after)

    def snapshot_before(self, placeholders=None, language='en'):
        placeholders = placeholders or [self.placeholder]
        self.before = [self.tree(p, language) for p in placeholders]


class UndoRedoTestCase(UndoRedoRoundTripMixin, HistoryTestCase):

    def test_add_root_plugin(self):
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint(name='new plugin')
            self.assert_round_trip()

    def test_add_nested_plugin(self):
        parent = self.add_plugin(name='parent')
        self.add_plugin(name='sibling')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint(parent=parent, name='child')
            self.assert_round_trip()

    def test_change_plugin(self):
        plugin = self.add_plugin(name='before')

        with self.login_user_context(self.superuser):
            self.change_plugin_via_endpoint(
                plugin,
                name='after',
                external_link='https://www.django-cms.org',
            )
            self.undo()
            plugin.refresh_from_db()
            self.assertEqual(plugin.name, 'before')

            self.redo()
            plugin.refresh_from_db()
            self.assertEqual(plugin.name, 'after')

    def test_delete_leaf_plugin(self):
        self.add_plugin(name='first')
        leaf = self.add_plugin(name='second')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.delete_plugin_via_endpoint(leaf)
            self.assert_round_trip()

    def test_delete_plugin_with_nested_children(self):
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')
        self.add_plugin(parent=child, name='grandchild')
        self.add_plugin(name='last root')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.delete_plugin_via_endpoint(parent)
            self.assert_round_trip()

    def test_delete_undo_restores_plugin_data(self):
        plugin = self.add_plugin(name='precious', external_link='https://example.com')

        with self.login_user_context(self.superuser):
            self.delete_plugin_via_endpoint(plugin)
            self.undo()

        restored = self.placeholder.get_plugins('en').get(pk=plugin.pk)
        bound = restored.get_bound_plugin()
        self.assertEqual(bound.name, 'precious')
        self.assertEqual(bound.external_link, 'https://example.com')

    def test_move_plugin_up_within_placeholder(self):
        self.add_plugin(name='first')
        second = self.add_plugin(name='second')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(second, target_position=1)
            self.assert_round_trip()

    def test_move_plugin_down_within_placeholder(self):
        first = self.add_plugin(name='first')
        self.add_plugin(name='second')
        self.add_plugin(name='third')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(first, target_position=3)
            self.assert_round_trip()

    def assert_tree_invariant(self):
        # The position attribute must stay healthy after a move replay:
        # positions are contiguous 1..n, and every subtree occupies a
        # consecutive block (parents before their descendants). The latter is
        # the invariant ``Placeholder.move_plugin`` relies on, so a violation
        # would corrupt the *next* move.
        rows = list(
            self.placeholder.get_plugins('en')
            .order_by('position')
            .values_list('pk', 'parent_id', 'position')
        )
        positions = [position for _, _, position in rows]
        self.assertEqual(positions, list(range(1, len(rows) + 1)))

        position_by_pk = {pk: position for pk, _, position in rows}
        for pk, parent_id, position in rows:
            if parent_id is not None:
                self.assertGreater(
                    position, position_by_pk[parent_id],
                    'plugin %s precedes its parent %s' % (pk, parent_id),
                )

    def test_restore_subtree_in_middle_keeps_tree_healthy(self):
        # Undo of a delete restores the subtree via _restore_archived_plugins
        # (core internals _shift_plugin_positions + _recalculate_plugin_positions).
        # Deleting a nested subtree in the MIDDLE means the restore must shift the
        # suffix back out and slot the block in without splitting any subtree.
        self.add_plugin(name='root a')
        middle = self.add_plugin(name='middle parent')
        child = self.add_plugin(parent=middle, name='child')
        self.add_plugin(parent=child, name='grandchild')
        self.add_plugin(name='root c')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.delete_plugin_via_endpoint(middle)
            self.assert_tree_invariant()  # tree healthy after the delete

            self.undo()  # restore the subtree in the middle
            self.assert_tree_invariant()
            self.assertEqual(self.tree(self.placeholder), self.before[0])

            self.redo()  # delete again
            self.assert_tree_invariant()

    def test_restore_under_surviving_parent_keeps_tree_healthy(self):
        # Restore a nested subtree whose parent is NOT part of the archived set:
        # the restore must resolve the surviving parent and keep the block
        # consecutive among its surviving siblings.
        parent = self.add_plugin(name='surviving parent')
        target = self.add_plugin(parent=parent, name='delete me')
        self.add_plugin(parent=target, name='nested grandchild')
        self.add_plugin(parent=parent, name='surviving sibling')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.delete_plugin_via_endpoint(target)
            self.assert_tree_invariant()

            self.undo()  # restore under the surviving parent
            self.assert_tree_invariant()
            self.assertEqual(self.tree(self.placeholder), self.before[0])

            self.redo()
            self.assert_tree_invariant()

    def test_move_subtree_root_within_placeholder_keeps_tree_healthy(self):
        # Moving a root that has a nested subtree, then undoing/redoing, must
        # leave the position tree contiguous and the subtree consecutive.
        self.add_plugin(name='first')
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')
        self.add_plugin(parent=child, name='grandchild')
        self.add_plugin(name='last')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(parent, target_position=1)
            self.assert_tree_invariant()

            self.undo()
            self.assert_tree_invariant()
            self.assertEqual(self.tree(self.placeholder), self.before[0])

            self.redo()
            self.assert_tree_invariant()

    def test_move_plugin_into_parent(self):
        parent = self.add_plugin(name='parent')
        plugin = self.add_plugin(name='standalone')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(plugin, target_position=2, parent=parent)
            self.assert_round_trip()

    def test_move_plugin_out_of_parent(self):
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(child, target_position=2)
            self.assert_round_trip()

    def test_move_subtree_across_placeholders(self):
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')
        self.add_plugin(parent=child, name='grandchild')
        self.add_plugin(name='stays behind')
        self.add_plugin(placeholder=self.sidebar, name='sidebar existing')
        self.snapshot_before(placeholders=[self.placeholder, self.sidebar])

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(
                parent,
                target_position=2,
                target_placeholder=self.sidebar,
            )
            self.assert_round_trip(placeholders=[self.placeholder, self.sidebar])

    def test_move_into_parent_in_other_placeholder(self):
        target_parent = self.add_plugin(placeholder=self.sidebar, name='target parent')
        plugin = self.add_plugin(name='moves')
        self.snapshot_before(placeholders=[self.placeholder, self.sidebar])

        with self.login_user_context(self.superuser):
            self.move_plugin_via_endpoint(
                plugin,
                target_position=2,
                parent=target_parent,
                target_placeholder=self.sidebar,
            )
            self.assert_round_trip(placeholders=[self.placeholder, self.sidebar])

    def test_cut_plugin(self):
        parent = self.add_plugin(name='parent')
        self.add_plugin(parent=parent, name='child')
        self.add_plugin(name='stays behind')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.cut_plugin_via_endpoint(parent)

            clipboard = self.get_clipboard()
            self.assertEqual(len(self.tree(clipboard)), 2)
            self.assert_round_trip()

    def test_cut_undo_after_clipboard_overwritten(self):
        cut_me = self.add_plugin(name='cut me')
        other = self.add_plugin(name='copy me')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.cut_plugin_via_endpoint(cut_me)
            # Overwrite the clipboard; the cut plugin rows are deleted
            self.copy_plugin_to_clipboard_via_endpoint(other)

            self.undo()

        self.assertEqual(self.tree(self.placeholder), self.before[0])

    def test_paste_plugin(self):
        existing = self.add_plugin(name='existing')

        with self.login_user_context(self.superuser):
            clipboard_root = self.copy_plugin_to_clipboard_via_endpoint(existing)
            self.snapshot_before()
            self.paste_plugin_via_endpoint(
                clipboard_root,
                target_placeholder=self.placeholder,
                target_position=2,
            )
            self.assert_round_trip()

    def test_paste_nested_plugin(self):
        parent = self.add_plugin(name='parent')
        self.add_plugin(parent=parent, name='child')

        with self.login_user_context(self.superuser):
            clipboard_root = self.copy_plugin_to_clipboard_via_endpoint(parent)
            self.snapshot_before(placeholders=[self.placeholder, self.sidebar])
            self.paste_plugin_via_endpoint(
                clipboard_root,
                target_placeholder=self.sidebar,
                target_position=1,
            )
            self.assert_round_trip(placeholders=[self.placeholder, self.sidebar])

    def test_paste_placeholder(self):
        self.add_plugin(name='first')
        parent = self.add_plugin(name='second')
        self.add_plugin(parent=parent, name='nested')

        with self.login_user_context(self.superuser):
            reference = self.copy_placeholder_to_clipboard_via_endpoint(self.placeholder)
            self.snapshot_before(placeholders=[self.placeholder, self.sidebar])
            self.paste_plugin_via_endpoint(
                reference,
                target_placeholder=self.sidebar,
                target_position=1,
            )
            self.assert_round_trip(placeholders=[self.placeholder, self.sidebar])

    def test_copy_from_language(self):
        self.add_plugin(name='english one')
        parent = self.add_plugin(name='english two')
        self.add_plugin(parent=parent, name='english nested')
        self.snapshot_before(language='de')

        path = self.page.get_absolute_url('de')

        def snapshot():
            return [self.tree(self.placeholder, 'de')]

        with self.login_user_context(self.superuser):
            self.copy_from_language_via_endpoint(
                self.placeholder,
                source_language='en',
                target_language='de',
            )

            after = snapshot()

            self.undo(language='de', path=path)
            self.assertEqual(snapshot(), self.before)
            self.redo(language='de', path=path)
            self.assertEqual(snapshot(), after)

    def test_clear_placeholder(self):
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')
        self.add_plugin(parent=child, name='grandchild')
        self.add_plugin(name='another root')
        self.snapshot_before()

        with self.login_user_context(self.superuser):
            self.clear_placeholder_via_endpoint(self.placeholder)

            self.assertEqual(self.tree(self.placeholder), [])
            self.assert_round_trip()

    def test_multi_step_undo_redo_chain(self):
        with self.login_user_context(self.superuser):
            first = self.add_plugin_via_endpoint(name='first')
            self.add_plugin_via_endpoint(name='second')
            self.add_plugin_via_endpoint(parent=first, name='nested in first')

            tree_3 = self.tree(self.placeholder)

            self.undo()  # removes 'nested in first'
            tree_2 = self.tree(self.placeholder)
            self.assertEqual(len(tree_2), 2)

            self.undo()  # removes 'second'
            tree_1 = self.tree(self.placeholder)
            self.assertEqual(len(tree_1), 1)

            self.undo()  # removes 'first'
            self.assertEqual(self.tree(self.placeholder), [])

            # No further undo possible
            response = self.post_undo()
            self.assertEqual(response.status_code, 400)

            self.redo()
            self.assertEqual(self.tree(self.placeholder), tree_1)
            self.redo()
            self.assertEqual(self.tree(self.placeholder), tree_2)
            self.redo()
            self.assertEqual(self.tree(self.placeholder), tree_3)

            # No further redo possible
            response = self.post_redo()
            self.assertEqual(response.status_code, 400)

    def test_undo_preserves_primary_keys(self):
        # Restored plugins keep their original primary keys so that
        # older operations in the chain stay valid.
        plugin = self.add_plugin(name='keep my pk')
        original_pk = plugin.pk

        with self.login_user_context(self.superuser):
            self.delete_plugin_via_endpoint(plugin)
            self.assertFalse(CMSPlugin.objects.filter(pk=original_pk).exists())
            self.undo()

        self.assertTrue(CMSPlugin.objects.filter(pk=original_pk).exists())

    def test_undo_change_then_delete_chain(self):
        # change + delete + undo x2 returns the original data
        plugin = self.add_plugin(name='original')

        with self.login_user_context(self.superuser):
            self.change_plugin_via_endpoint(
                plugin,
                name='changed',
                external_link='https://www.django-cms.org',
            )
            self.delete_plugin_via_endpoint(plugin)

            self.undo()  # restores the (changed) plugin
            bound = CMSPlugin.objects.get(pk=plugin.pk).get_bound_plugin()
            self.assertEqual(bound.name, 'changed')

            self.undo()  # reverts the change
            bound = CMSPlugin.objects.get(pk=plugin.pk).get_bound_plugin()
            self.assertEqual(bound.name, 'original')
