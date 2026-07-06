from unittest.mock import patch

from django.test import override_settings

from cms import operations
from cms.models import Placeholder

from djangocms_history import actions
from djangocms_history.datastructures import ArchivedPlugin
from djangocms_history.helpers import get_plugin_data
from djangocms_history.models import PlaceholderOperation

from .base import HistoryTestCase


class ActionDataTestCase(HistoryTestCase):

    def test_action_data_json_round_trip(self):
        plugin = self.add_plugin(name='archived')

        operation = PlaceholderOperation.objects.create(
            operation_type=operations.ADD_PLUGIN,
            token='token',
            origin='/en/',
            language='en',
            user=self.superuser,
            user_session_key='session',
            site_id=1,
        )
        from djangocms_history.helpers import get_plugin_data

        operation.create_action(
            action='add_plugin',
            language='en',
            placeholder=self.placeholder,
            pre_data={'parent_id': None, 'plugins': [get_plugin_data(plugin.get_bound_plugin())]},
        )

        action = operation.actions.get()
        data = action.get_pre_action_data()
        self.assertIsNone(data['parent_id'])

        archived = data['plugins'][0]
        self.assertIsInstance(archived, ArchivedPlugin)
        self.assertEqual(archived.pk, plugin.pk)
        self.assertEqual(archived.plugin_type, 'LinkPlugin')
        self.assertEqual(archived.position, 1)
        self.assertEqual(archived.data['name'], 'archived')
        self.assertEqual(archived.model, plugin.get_bound_plugin().__class__)

    def test_action_data_is_parsed_once(self):
        operation = PlaceholderOperation.objects.create(
            operation_type=operations.ADD_PLUGIN,
            token='token',
            origin='/en/',
            language='en',
            user=self.superuser,
            user_session_key='session',
            site_id=1,
        )
        operation.create_action(
            action='add_plugin',
            language='en',
            placeholder=self.placeholder,
            pre_data={'value': 'before'},
            post_data={'value': 'after'},
        )
        action = operation.actions.get()

        with patch.object(action, '_get_parsed_data', wraps=action._get_parsed_data) as parse:
            self.assertEqual(action.get_pre_action_data(), {'value': 'before'})
            self.assertEqual(action.get_pre_action_data(), {'value': 'before'})
            self.assertEqual(action.get_post_action_data(), {'value': 'after'})
            self.assertEqual(action.get_post_action_data(), {'value': 'after'})

        self.assertEqual(parse.call_count, 2)


class ArchiveOnLoginTestCase(HistoryTestCase):

    @override_settings(DJANGOCMS_HISTORY_ARCHIVE_OPERATIONS=True)
    def test_new_session_archives_previous_operations(self):
        from importlib import import_module

        from django.conf import settings
        from django.contrib.auth.signals import user_logged_in
        from django.test import RequestFactory

        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()

        operation = self.latest_operation()
        self.assertFalse(operation.is_archived)

        # Simulate a login with a fresh session
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore()
        session.create()

        request = RequestFactory().get('/')
        request.user = self.superuser
        request.session = session

        user_logged_in.send(
            sender=self.superuser.__class__,
            request=request,
            user=self.superuser,
        )

        operation.refresh_from_db()
        self.assertTrue(operation.is_archived)


class IsEditableTestCase(HistoryTestCase):

    def test_operation_is_editable_by_default(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()

        operation = self.latest_operation()
        self.assertTrue(operation.is_editable(self.superuser))

    def test_operation_not_editable_when_source_check_fails(self):
        from cms.models.fields import PlaceholderRelationField

        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()

        operation = self.latest_operation()

        def deny(placeholder, user):
            return False

        PlaceholderRelationField.default_checks.append(deny)
        try:
            self.assertFalse(operation.is_editable(self.superuser))
        finally:
            PlaceholderRelationField.default_checks.remove(deny)


class QueryEfficiencyTestCase(HistoryTestCase):
    """
    Locks in the query behaviour of the undo/redo inspection paths: an
    operation's actions are fetched from the database exactly once, and
    each touched placeholder is source-checked exactly once.
    """

    def create_operation(self, operation_type=operations.ADD_PLUGIN):
        return PlaceholderOperation.objects.create(
            operation_type=operation_type,
            token='token',
            origin='/en/',
            language='en',
            user=self.superuser,
            user_session_key='session',
            site_id=1,
        )

    def patch_check_source(self, checked):
        def check_source(placeholder, user):
            checked.append(placeholder.pk)
            return True
        return patch.object(Placeholder, 'check_source', check_source)

    def test_is_editable_fetches_actions_once_and_dedupes_placeholders(self):
        operation = self.create_operation()
        operation.create_action(
            action=actions.ADD_PLUGIN,
            language='en',
            placeholder=self.placeholder,
        )
        operation.create_action(
            action=actions.ADD_PLUGIN,
            language='en',
            placeholder=self.placeholder,
            order=2,
        )

        checked = []

        with self.patch_check_source(checked):
            # One query: the actions (with their placeholders) themselves.
            with self.assertNumQueries(1):
                self.assertTrue(operation.is_editable(self.superuser))

            # Both actions share one placeholder; its source is checked once.
            self.assertEqual(checked, [self.placeholder.pk])

            # The actions are cached on the operation; checking again is free.
            with self.assertNumQueries(0):
                self.assertTrue(operation.is_editable(self.superuser))

    def test_is_editable_checks_each_distinct_placeholder(self):
        operation = self.create_operation(operations.MOVE_PLUGIN)
        operation.create_action(
            action=actions.MOVE_OUT_PLUGIN,
            language='en',
            placeholder=self.placeholder,
        )
        operation.create_action(
            action=actions.MOVE_IN_PLUGIN,
            language='en',
            placeholder=self.sidebar,
            order=2,
        )

        checked = []

        with self.patch_check_source(checked):
            self.assertTrue(operation.is_editable(self.superuser))

        self.assertEqual(checked, [self.placeholder.pk, self.sidebar.pk])

    def test_action_inspection_runs_on_cached_actions(self):
        plugin = self.add_plugin(name='moved')

        operation = self.create_operation(operations.MOVE_PLUGIN)
        operation.create_action(
            action=actions.MOVE_PLUGIN,
            language='en',
            placeholder=self.placeholder,
            pre_data={
                'parent_id': None,
                'plugins': [get_plugin_data(plugin, only_meta=True)],
            },
            post_data={
                'parent_id': None,
                'plugins': [get_plugin_data(plugin, only_meta=True)],
            },
        )

        with self.assertNumQueries(1):
            self.assertEqual(len(operation.cached_actions), 1)

        # The inspection helpers work off the cached actions.
        with self.assertNumQueries(0):
            self.assertEqual(operation.get_move_plugin_id(), plugin.pk)
            self.assertIsNone(operation.get_close_frame_target())
