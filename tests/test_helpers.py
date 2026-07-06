from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory

from cms.models import CMSPlugin

from djangocms_history.helpers import (
    OBJECT_ENDPOINT_URL_NAMES,
    delete_plugins,
    get_bound_plugins,
    get_operation_origin,
    get_operations_from_request,
)

from .base import HistoryTestCase


class OperationOriginHelperTestCase(HistoryTestCase):

    @patch('djangocms_history.helpers.resolve')
    def test_object_endpoint_supports_named_url_arguments(self, resolve):
        resolve.return_value = SimpleNamespace(
            url_name=next(iter(OBJECT_ENDPOINT_URL_NAMES)),
            args=(),
            kwargs={'content_type_id': 12, 'object_id': 34},
        )

        self.assertEqual(get_operation_origin('/object/?toolbar=1'), '12:34')

    @patch('djangocms_history.helpers.resolve')
    def test_object_endpoint_without_identifiers_falls_back_to_path(self, resolve):
        resolve.return_value = SimpleNamespace(
            url_name=next(iter(OBJECT_ENDPOINT_URL_NAMES)),
            args=(),
            kwargs={},
        )

        self.assertEqual(get_operation_origin('/object/?toolbar=1'), '/object/')


class PluginHelperTestCase(HistoryTestCase):

    def test_get_bound_plugins_downcasts_and_preserves_missing_plugins(self):
        plugin = self.add_plugin(name='bound')
        base_plugin = CMSPlugin.objects.get(pk=plugin.pk)
        missing_plugin = SimpleNamespace(
            pk=plugin.pk + 999,
            plugin_type=base_plugin.plugin_type,
        )

        bound_plugin, fallback = get_bound_plugins([base_plugin, missing_plugin])

        self.assertEqual(bound_plugin.pk, plugin.pk)
        self.assertEqual(bound_plugin.name, 'bound')
        self.assertIs(fallback, missing_plugin)

    def test_delete_plugins_uses_legacy_per_plugin_fallback(self):
        plugins = [Mock(name='second'), Mock(name='first')]
        manager = Mock()
        manager.filter.return_value.order_by.return_value = plugins
        placeholder = SimpleNamespace(
            cmsplugin_set=manager,
            delete_plugin=Mock(),
        )

        delete_plugins(placeholder, plugin_ids=[1, 2])

        manager.filter.assert_called_once_with(pk__in=[1, 2])
        manager.filter.return_value.order_by.assert_called_once_with('-position')
        self.assertEqual(
            placeholder.delete_plugin.call_args_list,
            [((plugins[0],),), ((plugins[1],),)],
        )


class OperationQueryHelperTestCase(HistoryTestCase):

    def test_request_language_is_used_when_language_is_omitted(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint()
            request = RequestFactory().get(self.page.get_absolute_url('en'))
            request.user = self.superuser
            request.session = self.client.session

            with patch(
                'djangocms_history.helpers.get_language_from_request',
                return_value='en',
            ) as get_language:
                operations = list(get_operations_from_request(request))

        get_language.assert_called_once_with(request)
        self.assertEqual(len(operations), 1)
