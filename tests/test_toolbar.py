from unittest.mock import patch

from django.test import RequestFactory

from cms.toolbar.toolbar import CMSToolbar as RequestToolbar

from djangocms_history.models import PlaceholderOperation

from .base import HistoryTestCase


class UndoRedoToolbarTestCase(HistoryTestCase):

    def get_toolbar(self, user=None, edit_mode=True, path=None):
        """
        Builds a CMS toolbar bound to a request that shares the test
        client's session, so operations recorded through the endpoints
        are visible to the toolbar.
        """
        request = RequestFactory().get(path or self.page.get_absolute_url('en'))
        request.user = user or self.superuser
        request.session = self.client.session
        request.current_page = self.page
        request.LANGUAGE_CODE = 'en'
        request.toolbar = RequestToolbar(request)
        request.toolbar.edit_mode_active = edit_mode
        return request.toolbar

    def get_buttons(self, toolbar):
        # Accessing the items populates all registered CMSToolbar classes,
        # including UndoRedoToolbar.
        from cms.toolbar.items import ButtonList

        from djangocms_history.cms_toolbars import AjaxButton

        buttons = []
        for item in toolbar.get_right_items():
            if isinstance(item, ButtonList):
                buttons.extend(
                    button for button in item.buttons
                    if isinstance(button, AjaxButton)
                )
        return buttons

    def test_no_buttons_outside_edit_mode(self):
        with self.login_user_context(self.superuser):
            toolbar = self.get_toolbar(edit_mode=False)
            self.assertEqual(self.get_buttons(toolbar), [])

    def test_buttons_disabled_without_operations(self):
        with self.login_user_context(self.superuser):
            toolbar = self.get_toolbar()
            undo_button, redo_button = self.get_buttons(toolbar)

        self.assertEqual(undo_button.button_type, 'undo')
        self.assertEqual(redo_button.button_type, 'redo')
        self.assertTrue(undo_button.disabled)
        self.assertTrue(redo_button.disabled)

    def test_undo_enabled_after_operation(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
            toolbar = self.get_toolbar()
            undo_button, redo_button = self.get_buttons(toolbar)

        self.assertFalse(undo_button.disabled)
        self.assertTrue(redo_button.disabled)

    def test_redo_enabled_after_undo(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
            self.undo()
            toolbar = self.get_toolbar()
            undo_button, redo_button = self.get_buttons(toolbar)

        self.assertTrue(undo_button.disabled)
        self.assertFalse(redo_button.disabled)

    def test_buttons_carry_request_context(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
            toolbar = self.get_toolbar()
            undo_button, _ = self.get_buttons(toolbar)

        context = undo_button.get_context()
        self.assertIn('"language": "en"', context['data'])
        self.assertIn(self.page.get_absolute_url('en'), context['data'])

    def test_no_buttons_for_user_without_page_permission(self):
        staff = self._create_user('staffer', is_staff=True)

        with self.login_user_context(staff):
            toolbar = self.get_toolbar(user=staff)
            self.assertEqual(self.get_buttons(toolbar), [])

    def test_undo_disabled_when_operation_not_editable(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()

            with patch.object(PlaceholderOperation, 'is_editable', return_value=False):
                toolbar = self.get_toolbar()
                undo_button, redo_button = self.get_buttons(toolbar)

        self.assertTrue(undo_button.disabled)
        self.assertTrue(redo_button.disabled)
