# -*- coding: utf-8 -*-
import json

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext

from cms.constants import REFRESH_PAGE
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.toolbar.items import BaseButton, ButtonList

from sekizai.helpers import get_varname

from .helpers import (
    get_active_operation,
    get_inactive_operation,
    get_operations_from_request,
)


class AjaxButton(BaseButton):
    template = 'djangocms_history/toolbar/ajax_button.html'

    def __init__(self, name, url, data, icon, active=False, disabled=False):
        self.name = name
        self.url = url
        self.active = active
        self.disabled = disabled
        self.data = data
        self.on_success = REFRESH_PAGE
        self.icon = icon

    def get_context(self):
        return {
            'name': self.name,
            'icon': self.icon,
            'active': self.active,
            'disabled': self.disabled,
            'data': json.dumps(self.data),
            'url': self.url,
            'on_success': self.on_success
        }


@toolbar_pool.register
class UndoRedoToolbar(CMSToolbar):
    undo_icon = (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABOklEQVR4A'
        'e3WNVZDQRhAYdyhimcBeMsG6CI1C8Dd9pK0rACXCm+QDoeaFnfnFlNNns4bnHvO10T/55Plsv/+i6ITM'
        'zjCtXCAOfFeBJ5axCb80h+n8YA3G49IIwSl3oRtBBDHKd5cukBSeQDhGC94U/SCXvUBjO2gF9UoFWoxi'
        'F2TIZI6BrhHF3JgVq4Y7sHgcIS8DnCEAJzUaDBESsch2IYfTuo1uDoiOs6BdTgp1+Cc6IBtqzYDLMBpg9J3p'
        '/Gp1UoDHOBTK5MGuMKnViFfjn/uEAx95UmofBnKFaAKbuszuBGFVf58Ag9IgLzfip2WjzHpYTSIXIWH0TmCcF'
        'UDXk0ex8OoRwXKUIchi8dxAkq1fMWCRK5JcUl2jgS0FMAInh0uSlPyMdc5SBdmsItLXGEfM+hwe6n99987pVTyg'
        'pWk5ykAAAAASUVORK5CYII='
    )
    redo_icon = (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABP0lEQVR42u'
        '3WP0vDQBiAcSXoYMWtpcYPoFjd3R01rn4Alx40Q9vv0q5+AxGsbiKOuoharM7OQv8MVqzng3Q6Ei5vLmQ'
        'xD/zGcC9ckruFoiJhPhSuMMBk7g0XUNhA5q2jiy9oiyk6xiBl3OMG4gKMoIU+cIAKnqABWSFm0CnN8A4NQ'
        'NBRzOJ9NFFDCSvYRB0PtqEkez6M2NsGPMS1CIVP1wG6EYvvI0llDFwG8CPe9oZg8UfXLVARe+4hSXdZvAOX'
        'xgNNJO3asvgtrL0aD20j18bGAKv/bgBzC2rILflLKM/9M3RP/iMKIW0Ly7Am/xXbCzDFedohqjGHUWjZDg8t'
        '4zA6wxLEBYg7jlvYQQlr2EUbz9CGH+xhXv4XkhM4dYhhyivZMTKpKriUfuMUFWSejzp6eMEYI/TRg/pbuKhI0'
        'C8BZPKBEtpCEgAAAABJRU5ErkJggg=='
    )
    icon_css = '<style>.cms-btn-disabled img {opacity: 0.2;}</style>'

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

    def _get_ajax_button(self, name, url, icon, disabled=True):
        data = {
            'language': self.toolbar.language,
            'cms_path': self.request.path,
            'csrfmiddlewaretoken': self.toolbar.csrf_token,
        }
        button = AjaxButton(
            name=name,
            url=url,
            data=data,
            icon=icon,
            active=False,
            disabled=disabled,
        )
        return button

    def get_undo_button(self):
        url = reverse('admin:djangocms_history_undo')
        disabled = not bool(self.active_operation)
        button = self._get_ajax_button(
            name=ugettext('Undo'),
            url=url,
            icon=self.undo_icon,
            disabled=disabled,
        )
        return button

    def get_redo_button(self):
        operation = self.get_inactive_operation()
        url = reverse('admin:djangocms_history_redo')
        disabled = not bool(operation)
        button = self._get_ajax_button(
            name=ugettext('Redo'),
            url=url,
            icon=self.redo_icon,
            disabled=disabled,
        )
        return button

    def render_addons(self, context):
        # TODO: This is a workaround to add our css to sekizai
        # Should be fixed on the cms core by exposing the context
        # to the toolbar populate methods.
        context[get_varname()]['css'].append(self.icon_css)
        return []
