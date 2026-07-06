from django.contrib.auth import get_user_model
from django.urls import reverse

from djangocms_history.admin import PlaceholderOperationAdmin
from djangocms_history.models import PlaceholderOperation

from .base import HistoryTestCase


class PlaceholderOperationAdminDeletePermissionTestCase(HistoryTestCase):
    """
    Regression test: deleting a user cascades to their PlaceholderOperation
    history (user FK is on_delete=CASCADE). Django admin's delete view
    additionally checks has_delete_permission() on every cascaded model, so
    that check must never block the cascade - even for a non-superuser who
    has no permissions on the history models at all.
    """

    def test_has_delete_permission_is_always_true(self):
        model_admin = PlaceholderOperationAdmin(PlaceholderOperation, None)

        self.assertTrue(model_admin.has_delete_permission(request=None))
        self.assertTrue(
            model_admin.has_delete_permission(request=None, obj=object())
        )

    def test_non_superuser_can_cascade_delete_user_with_history(self):
        victim = self.get_standard_user()
        operation = PlaceholderOperation.objects.create(
            operation_type='add_plugin',
            token='token-0',
            origin='/en/',
            language='en',
            user=victim,
            user_session_key='session',
            site_id=1,
        )
        operation.create_action(
            action='add_plugin',
            language='en',
            placeholder=self.placeholder,
        )

        deleter = self.get_staff_user_with_no_permissions()
        self.add_permission(deleter, 'delete_user')

        with self.login_user_context(deleter):
            response = self.client.post(
                reverse('admin:auth_user_delete', args=[victim.pk]),
                {'post': 'yes'},
            )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(pk=victim.pk).exists())
        self.assertFalse(
            PlaceholderOperation.objects.filter(pk=operation.pk).exists()
        )
