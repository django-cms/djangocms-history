import json

from django.templatetags.static import static
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

    def __init__(self, name, url, data, icon, active=False, disabled=False, classes=""):
        self.name = name
        self.url = url
        self.active = active
        self.disabled = disabled
        self.data = data
        self.on_success = REFRESH_PAGE
        self.icon = icon
        self.classes = classes

    def get_context(self):
        return {
            'name': self.name,
            'icon': self.icon,
            'active': self.active,
            'disabled': self.disabled,
            'data': json.dumps(self.data),
            'url': self.url,
            'on_success': self.on_success,
            'classes': self.classes,
        }


@toolbar_pool.register
class UndoRedoToolbar(CMSToolbar):
    # django CMS 3.4 compatibility
    icon_css = '<style>.cms-btn-disabled img {opacity: 0.2;}</style>'

    class Media:
        css = {
            'all': [static('djangocms_history/color_mode.css')]
        }

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

    def _get_ajax_button(self, name, url, icon, classes, disabled=True):
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
            icon='',
            active=False,
            disabled=disabled,
            classes=classes
        )
        return button

    def get_undo_button(self):
        url = reverse('admin:djangocms_history_undo')
        disabled = not bool(self.active_operation)
        button = self._get_ajax_button(
            name=gettext('Undo'),
            url=url,
            icon='',
            disabled=disabled,
            classes="undo"
        )
        return button

    def get_redo_button(self):
        operation = self.get_inactive_operation()
        url = reverse('admin:djangocms_history_redo')
        disabled = not bool(operation)
        button = self._get_ajax_button(
            name=gettext('Redo'),
            url=url,
            icon='',
            disabled=disabled,
            classes="redo",
        )
        return button

    def render_addons(self, context):
        # django CMS 3.4 compatibility
        context[get_varname()]['css'].append(self.icon_css)
        return []
