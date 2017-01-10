# -*- coding: utf-8 -*-
import json

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext

from cms.constants import REFRESH_PAGE
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.toolbar.items import BaseButton, ButtonList

from .helpers import (
    get_active_operation,
    get_inactive_operation,
    get_operations_from_request,
)


class AjaxButton(BaseButton):
    template = 'djangocms_history/toolbar/ajax_button.html'

    def __init__(self, name, url, data, active=False, disabled=False):
        self.name = name
        self.url = url
        self.active = active
        self.disabled = disabled
        self.data = data
        self.on_success = REFRESH_PAGE

    def get_context(self):
        return {
            'name': self.name,
            'active': self.active,
            'disabled': self.disabled,
            'data': json.dumps(self.data),
            'url': self.url,
            'on_success': self.on_success
        }


@toolbar_pool.register
class UndoRedoToolbar(CMSToolbar):

    def populate(self):
        self.active_operation = self.get_active_operation()

        if self.toolbar.edit_mode:
            self.add_buttons()

    def get_operations(self):
        operations = get_operations_from_request(
            self.request,
            language=self.toolbar.language,
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

    def _get_ajax_button(self, name, url, disabled=True):
        data = {
            'language': self.toolbar.language,
            'cms_path': self.request.path,
            'csrfmiddlewaretoken': self.toolbar.csrf_token,
        }
        button = AjaxButton(
            name,
            url,
            data=data,
            active=False,
            disabled=disabled,
        )
        return button

    def get_undo_button(self):
        url = reverse('admin:djangocms_history_undo')
        disabled = not bool(self.active_operation)
        # TODO: Replace with icon to save space
        return self._get_ajax_button(ugettext('Undo'), url, disabled=disabled)

    def get_redo_button(self):
        operation = self.get_inactive_operation()
        url = reverse('admin:djangocms_history_redo')
        disabled = not bool(operation)
        # TODO: Replace with icon to save space
        return self._get_ajax_button(ugettext('Redo'), url, disabled=disabled)
