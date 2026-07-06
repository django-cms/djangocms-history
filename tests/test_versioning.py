from unittest import skipUnless

from django.conf import settings

from .base import HistoryTestCase

VERSIONING_INSTALLED = 'djangocms_versioning' in settings.INSTALLED_APPS


@skipUnless(VERSIONING_INSTALLED, 'djangocms-versioning is not installed')
class VersioningGuardTestCase(HistoryTestCase):
    """
    Guard-only versioning support: undo/redo must refuse to touch
    placeholders whose content is not editable (e.g. published versions).

    Run with VERSIONING=1 so djangocms_versioning is added to
    INSTALLED_APPS.
    """

    def setUp(self):
        super().setUp()
        from djangocms_versioning.constants import DRAFT
        from djangocms_versioning.models import Version

        # djangocms-versioning creates a draft version for content
        # created through cms.api.create_page
        self.version = Version.objects.get_for_content(self.page_content)
        self.assertEqual(self.version.state, DRAFT)

    def test_operations_on_draft_record_and_undo(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint(name='draft plugin')

            operation = self.latest_operation()
            self.assertTrue(operation.is_editable(self.superuser))

            self.undo()
            self.assertEqual(self.tree(self.placeholder), [])

            self.redo()
            self.assertEqual(len(self.tree(self.placeholder)), 1)

    def test_publish_makes_operation_non_editable(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint(name='draft plugin')

        operation = self.latest_operation()
        self.assertTrue(operation.is_editable(self.superuser))

        self.version.publish(self.superuser)

        operation = self.latest_operation()  # reload to invalidate cache
        self.assertFalse(operation.is_editable(self.superuser))

    def test_undo_refused_on_published_version(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint(name='draft plugin')
            tree_before_undo = self.tree(self.placeholder)

            self.version.publish(self.superuser)

            response = self.post_undo()
            self.assertEqual(response.status_code, 403)

        # Nothing changed
        self.assertEqual(self.tree(self.placeholder), tree_before_undo)
        self.assertTrue(self.latest_operation().is_applied)

    def test_redo_refused_on_published_version(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint(name='draft plugin')
            self.undo()
            tree_after_undo = self.tree(self.placeholder)

            self.version.publish(self.superuser)

            response = self.post_redo()
            self.assertEqual(response.status_code, 403)

        self.assertEqual(self.tree(self.placeholder), tree_after_undo)
        self.assertFalse(self.latest_operation().is_applied)
