from cms.models import CMSPlugin

from djangocms_history import actions
from djangocms_history.action_handlers import (
    _delete_plugins,
    _move_plugin,
    _restore_archived_plugins,
)
from djangocms_history.helpers import get_plugin_data
from djangocms_history.models import PlaceholderOperation

from .base import HistoryTestCase


class ActionHandlerPrimitivesTestCase(HistoryTestCase):
    """
    Unit tests for the replay primitives, exercising edge cases that the
    endpoint-driven round-trip tests don't reach.
    """

    def create_action(self, placeholder=None, language='en', **data):
        operation = PlaceholderOperation.objects.create(
            operation_type='add_plugin',
            token='test-token',
            origin='/en/',
            language=language,
            user=self.superuser,
            user_session_key='session',
            site_id=1,
        )
        operation.create_action(
            action=actions.ADD_PLUGIN,
            language=language,
            placeholder=placeholder or self.placeholder,
            **data
        )
        return operation.actions.get()

    def archive(self, plugins):
        return {'plugins': [get_plugin_data(p.get_bound_plugin()) for p in plugins]}

    def test_restore_into_placeholder_that_grew(self):
        # Archive a subtree at positions 1-2, then fill the placeholder
        # with more plugins than there were at archive time. The restore
        # must not collide with the (placeholder, language, position)
        # unique constraint.
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')
        data = self.archive([parent, child])

        action = self.create_action(post_data=data)

        self.placeholder.delete_plugin(parent)

        # Place four new plugins occupying positions 1..4
        survivors = [self.add_plugin(name=f'survivor {i}') for i in range(4)]

        _restore_archived_plugins(action, data=action.get_post_action_data())

        tree = self.tree(self.placeholder)
        self.assertEqual(len(tree), 6)
        # Restored subtree sits at its archived position (the start)
        self.assertEqual(tree[0][0], parent.pk)
        self.assertEqual(tree[1][0], child.pk)
        self.assertEqual(tree[1][1], parent.pk)
        # Positions are contiguous 1..6
        self.assertEqual([row[2] for row in tree], [1, 2, 3, 4, 5, 6])
        # Survivors keep their relative order
        self.assertEqual([row[0] for row in tree[2:]], [s.pk for s in survivors])

    def test_restore_into_placeholder_that_shrank(self):
        # Archive plugins at positions 3-4; restore after the placeholder
        # lost the plugins before them. The subtree lands at the end.
        self.add_plugin(name='first')
        second = self.add_plugin(name='second')
        third = self.add_plugin(name='third')
        fourth = self.add_plugin(name='fourth')
        data = self.archive([third, fourth])

        action = self.create_action(post_data=data)

        for plugin in (third, fourth, second):
            self.placeholder.delete_plugin(plugin)

        _restore_archived_plugins(action, data=action.get_post_action_data())

        tree = self.tree(self.placeholder)
        self.assertEqual(len(tree), 3)
        self.assertEqual([row[2] for row in tree], [1, 2, 3])
        self.assertEqual([row[0] for row in tree[1:]], [third.pk, fourth.pk])

    def test_restore_into_empty_placeholder(self):
        plugin = self.add_plugin(name='lonely')
        data = self.archive([plugin])
        action = self.create_action(post_data=data)
        self.placeholder.delete_plugin(plugin)

        _restore_archived_plugins(action, data=action.get_post_action_data())

        tree = self.tree(self.placeholder)
        self.assertEqual([(tree[0][0], tree[0][2])], [(plugin.pk, 1)])

    def test_restore_with_empty_data_is_noop(self):
        self.add_plugin(name='existing')
        action = self.create_action(post_data={'plugins': []})

        _restore_archived_plugins(action, data=action.get_post_action_data())

        self.assertEqual(len(self.tree(self.placeholder)), 1)

    def test_restore_under_surviving_parent(self):
        parent = self.add_plugin(name='parent')
        child = self.add_plugin(parent=parent, name='child')
        data = self.archive([child])
        action = self.create_action(post_data=data)

        self.placeholder.delete_plugin(child)

        _restore_archived_plugins(action, data=action.get_post_action_data())

        restored = CMSPlugin.objects.get(pk=child.pk)
        self.assertEqual(restored.parent_id, parent.pk)
        self.assertEqual(restored.position, 2)

    def test_move_plugin_to_position_beyond_range(self):
        # Archived position can exceed the current tree size if other
        # content was removed since; the move clamps to the end.
        first = self.add_plugin(name='first')
        self.add_plugin(name='second')

        data = {
            'parent_id': None,
            'plugins': [get_plugin_data(first, only_meta=True)],
        }
        data['plugins'][0]['position'] = 7
        action = self.create_action(pre_data=data)

        _move_plugin(action, data=action.get_pre_action_data())

        tree = self.tree(self.placeholder)
        self.assertEqual([row[2] for row in tree], [1, 2])
        self.assertEqual(tree[-1][0], first.pk)

    def test_delete_plugins_ignores_missing_ids(self):
        plugin = self.add_plugin(name='only')
        action = self.create_action()

        _delete_plugins(action, plugin_ids=[plugin.pk, plugin.pk + 999])

        self.assertEqual(self.tree(self.placeholder), [])

    def test_delete_plugins_with_multiple_roots(self):
        first = self.add_plugin(name='first')
        self.add_plugin(parent=first, name='first child')
        second = self.add_plugin(name='second')
        keeper = self.add_plugin(name='keeper')
        action = self.create_action()

        _delete_plugins(action, plugin_ids=[first.pk, second.pk])

        tree = self.tree(self.placeholder)
        self.assertEqual([(row[0], row[2]) for row in tree], [(keeper.pk, 1)])
