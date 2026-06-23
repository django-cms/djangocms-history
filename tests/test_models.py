from cms import operations
from cms.signals import pre_obj_operation

from djangocms_history.datastructures import ArchivedPlugin
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


class ArchiveOnLoginTestCase(HistoryTestCase):

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


class PageOperationTestCase(HistoryTestCase):

    def record_operation(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
        return self.latest_operation()

    def test_page_operation_archives_page_operations(self):
        operation = self.record_operation()

        pre_obj_operation.send(
            sender=self.__class__,
            operation=operations.DELETE_PAGE,
            obj=self.page,
        )

        operation.refresh_from_db()
        self.assertTrue(operation.is_archived)

    def test_page_operation_does_not_archive_other_pages(self):
        operation = self.record_operation()
        other_page, _ = self.create_other_page()

        pre_obj_operation.send(
            sender=self.__class__,
            operation=operations.DELETE_PAGE,
            obj=other_page,
        )

        operation.refresh_from_db()
        self.assertFalse(operation.is_archived)

    def test_translation_operation_archives_translation_only(self):
        en_operation = self.record_operation()

        translation = self.page_content  # the English page content

        pre_obj_operation.send(
            sender=self.__class__,
            operation=operations.DELETE_PAGE_TRANSLATION,
            obj=self.page,
            translation=translation,
        )

        en_operation.refresh_from_db()
        self.assertTrue(en_operation.is_archived)

    def test_translation_operation_other_language_untouched(self):
        en_operation = self.record_operation()

        from cms.api import create_page_content

        de_translation = create_page_content('de', 'startseite', self.page)

        pre_obj_operation.send(
            sender=self.__class__,
            operation=operations.DELETE_PAGE_TRANSLATION,
            obj=self.page,
            translation=de_translation,
        )

        en_operation.refresh_from_db()
        self.assertFalse(en_operation.is_archived)

    def test_operation_signal_without_obj_does_not_crash(self):
        operation = self.record_operation()

        # ADD_PAGE_TRANSLATION is sent by the cms without an obj kwarg
        pre_obj_operation.send(
            sender=self.__class__,
            operation=operations.ADD_PAGE_TRANSLATION,
            language='de',
        )

        operation.refresh_from_db()
        self.assertFalse(operation.is_archived)


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
