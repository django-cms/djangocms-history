from unittest.mock import patch

from django.urls import reverse

from djangocms_history.models import PlaceholderOperation

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

            response = self.client.post(self.undo_url, self.valid_data)
            self.assertEqual(response.status_code, 204)
            operation.refresh_from_db()
            self.assertFalse(operation.is_applied)

            response = self.client.post(self.redo_url, self.valid_data)
            self.assertEqual(response.status_code, 204)
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
