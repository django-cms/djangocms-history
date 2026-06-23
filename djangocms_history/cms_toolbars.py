import json

from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import gettext

from cms.constants import REFRESH_PAGE
from cms.toolbar.items import BaseButton, ButtonList
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.page_permissions import user_can_change_page

from .helpers import (
    get_active_operation,
    get_inactive_operation,
    get_operations_from_request,
)


class AjaxButton(BaseButton):
    template = 'djangocms_history/toolbar/ajax_button.html'

    def __init__(self, name, url, data, icon, active=False, disabled=False, button_type=""):
        self.name = name
        self.url = url
        self.active = active
        self.disabled = disabled
        self.data = data
        self.on_success = REFRESH_PAGE
        self.icon = icon
        self.button_type = button_type

    def get_context(self):
        return {
            'name': self.name,
            'icon': self.icon,
            'active': self.active,
            'disabled': self.disabled,
            'data': json.dumps(self.data),
            'url': self.url,
            'on_success': self.on_success,
            'button_type': self.button_type,
        }


@toolbar_pool.register
class UndoRedoToolbar(CMSToolbar):

    class Media:
        css = {
            'all': [static('djangocms_history/color_mode.css')]
        }

    def populate(self):
        if not self.toolbar.edit_mode_active:
            return

        page = self.request.current_page

        if page and not user_can_change_page(self.request.user, page):
            # On a page the user is not allowed to change, don't offer
            # undo/redo. On non-page content (current_page is None) the
            # buttons are shown; the undo/redo endpoint enforces
            # editability per affected placeholder.
            return

        self.active_operation = self.get_active_operation()
        self.add_buttons()

    def get_operations(self):
        operations = get_operations_from_request(
            self.request,
            path=self.toolbar.request_path,
            language=self.toolbar.toolbar_language,
        )
        return operations

    def get_active_operation(self):
        operations = self.get_operations()
        return get_active_operation(operations)

    def get_inactive_operation(self):
        operations = self.get_operations()
        operation = get_inactive_operation(
            operations,
            active_operation=self.active_operation,
        )
        return operation

    def add_buttons(self):
        container = ButtonList(side=self.toolbar.RIGHT)
        container.buttons.append(self.get_undo_button())
        container.buttons.append(self.get_redo_button())
        self.toolbar.add_item(container)

    def _get_ajax_button(self, name, url, icon, button_type, disabled=True):
        data = {
            'language': self.toolbar.toolbar_language,
            'cms_path': self.toolbar.request_path,
            'csrfmiddlewaretoken': self.toolbar.csrf_token,
        }
        button = AjaxButton(
            name=name,
            url=url,
            data=data,
            icon='',
            active=False,
            disabled=disabled,
            button_type=button_type
        )
        return button

    def _operation_is_applicable(self, operation):
        return bool(operation) and operation.is_editable(self.request.user)

    def get_undo_button(self):
        url = reverse('admin:djangocms_history_undo')
        disabled = not self._operation_is_applicable(self.active_operation)
        button = self._get_ajax_button(
            name=gettext('Undo'),
            url=url,
            icon='',
            disabled=disabled,
            button_type="undo"
        )
        return button

    def get_redo_button(self):
        operation = self.get_inactive_operation()
        url = reverse('admin:djangocms_history_redo')
        disabled = not self._operation_is_applicable(operation)
        button = self._get_ajax_button(
            name=gettext('Redo'),
            url=url,
            icon='',
            disabled=disabled,
            button_type="redo",
        )
        return button
