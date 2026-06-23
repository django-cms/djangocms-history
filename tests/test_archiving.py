from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from djangocms_history.models import (
    PlaceholderAction,
    PlaceholderOperation,
    archive_or_delete_operations,
)

from .base import HistoryTestCase


class RetirementModeTestCase(HistoryTestCase):
    """
    archive_or_delete_operations() either flags operations as archived or
    deletes them outright, depending on the
    DJANGOCMS_HISTORY_ARCHIVE_OPERATIONS setting.
    """

    def _create_operations(self, count):
        for index in range(count):
            operation = PlaceholderOperation.objects.create(
                operation_type='add_plugin',
                token='token-{}'.format(index),
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
            )

    def test_deletes_by_default(self):
        self._create_operations(2)

        archive_or_delete_operations(PlaceholderOperation.objects.all())

        self.assertEqual(PlaceholderOperation.objects.count(), 0)
        # Actions are cascade-deleted with their operation
        self.assertEqual(PlaceholderAction.objects.count(), 0)

    @override_settings(DJANGOCMS_HISTORY_ARCHIVE_OPERATIONS=True)
    def test_archives_when_enabled(self):
        self._create_operations(2)

        archive_or_delete_operations(PlaceholderOperation.objects.all())

        self.assertEqual(PlaceholderOperation.objects.count(), 2)
        self.assertEqual(
            PlaceholderOperation.objects.filter(is_archived=True).count(), 2
        )
        self.assertEqual(PlaceholderAction.objects.count(), 2)


class IntegrationRetirementTestCase(HistoryTestCase):
    """
    The same toggle applies when the CMS retires competing operations during
    the real recording flow.
    """

    def test_competing_operation_deleted_by_default(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
            first_pk = self.latest_operation().pk
            _, other_placeholder = self.create_other_page()
            self.add_plugin_via_endpoint(placeholder=other_placeholder)

        self.assertFalse(
            PlaceholderOperation.objects.filter(pk=first_pk).exists()
        )

    @override_settings(DJANGOCMS_HISTORY_ARCHIVE_OPERATIONS=True)
    def test_competing_operation_archived_when_enabled(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
            first = self.latest_operation()
            _, other_placeholder = self.create_other_page()
            self.add_plugin_via_endpoint(placeholder=other_placeholder)

        first.refresh_from_db()
        self.assertTrue(first.is_archived)


class PurgeCommandTestCase(HistoryTestCase):

    def _make_operation(self, is_archived=True):
        operation = PlaceholderOperation.objects.create(
            operation_type='add_plugin',
            token='token',
            origin='/en/',
            language='en',
            user=self.superuser,
            user_session_key='session',
            site_id=1,
            is_archived=is_archived,
        )
        operation.create_action(
            action='add_plugin',
            language='en',
            placeholder=self.placeholder,
        )
        return operation

    def _backdate(self, operation, days):
        PlaceholderOperation.objects.filter(pk=operation.pk).update(
            date_created=timezone.now() - timedelta(days=days),
        )

    def test_purges_only_archived_operations(self):
        archived = self._make_operation(is_archived=True)
        active = self._make_operation(is_archived=False)

        out = StringIO()
        call_command('purge_archived_operations', stdout=out)

        self.assertFalse(PlaceholderOperation.objects.filter(pk=archived.pk).exists())
        self.assertTrue(PlaceholderOperation.objects.filter(pk=active.pk).exists())
        self.assertIn('Deleted 1', out.getvalue())

    def test_cascade_deletes_actions(self):
        archived = self._make_operation(is_archived=True)
        self.assertEqual(
            PlaceholderAction.objects.filter(operation=archived).count(), 1
        )

        call_command('purge_archived_operations', stdout=StringIO())

        self.assertEqual(PlaceholderAction.objects.count(), 0)

    def test_dry_run_keeps_rows(self):
        self._make_operation(is_archived=True)

        out = StringIO()
        call_command('purge_archived_operations', '--dry-run', stdout=out)

        self.assertEqual(PlaceholderOperation.objects.count(), 1)
        self.assertIn('would be deleted', out.getvalue())

    def test_days_filter_keeps_recent(self):
        old = self._make_operation(is_archived=True)
        recent = self._make_operation(is_archived=True)
        self._backdate(old, days=10)

        call_command('purge_archived_operations', '--days', '7', stdout=StringIO())

        self.assertFalse(PlaceholderOperation.objects.filter(pk=old.pk).exists())
        self.assertTrue(PlaceholderOperation.objects.filter(pk=recent.pk).exists())
