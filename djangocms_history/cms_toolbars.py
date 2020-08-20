import json

from django.urls import reverse
from django.utils.translation import gettext

from cms.api import get_page_draft
from cms.constants import REFRESH_PAGE
from cms.toolbar.items import BaseButton, ButtonList
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.page_permissions import user_can_change_page

from sekizai.helpers import get_varname

from .compat import CMS_GTE_36
from .helpers import (
    get_active_operation, get_inactive_operation, get_operations_from_request,
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

    # django CMS 3.4 compatibility
    icon_css = '<style>.cms-btn-disabled img {opacity: 0.2;}</style>'

    @property
    def request_path(self):
        try:
            origin = self.toolbar.request_path
        except AttributeError:
            # django CMS < 3.5 compatibility
            origin = self.request.path
        return origin

    def populate(self):
        # django CMS >= 3.6
        if CMS_GTE_36 and not self.toolbar.edit_mode_active:
            return
        # django CMS <= 3.5
        if not CMS_GTE_36 and not self.toolbar.edit_mode:
            return

        cms_page = get_page_draft(self.request.current_page)

        if not cms_page or user_can_change_page(self.request.user, cms_page):
            self.active_operation = self.get_active_operation()
            self.add_buttons()

    def get_operations(self):
        if CMS_GTE_36:
            toolbar_language = self.toolbar.toolbar_language
        else:
            toolbar_language = self.toolbar.language

        operations = get_operations_from_request(
            self.request,
            path=self.request_path,
            language=toolbar_language,
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
        if CMS_GTE_36:
            toolbar_language = self.toolbar.toolbar_language
        else:
            toolbar_language = self.toolbar.language

        data = {
            'language': toolbar_language,
            'cms_path': self.request_path,
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
            name=gettext('Undo'),
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
            name=gettext('Redo'),
            url=url,
            icon=self.redo_icon,
            disabled=disabled,
        )
        return button

    def render_addons(self, context):
        # django CMS 3.4 compatibility
        context[get_varname()]['css'].append(self.icon_css)
        return []
