from cms.api import add_plugin
from cms.test_utils.project.pluginapp.plugins.manytomany_rel.models import (
    ArticlePluginModel,
    Section,
)

from djangocms_history.models import PlaceholderOperation
from djangocms_history.utils import plugin_has_m2m

from .base import HistoryTestCase


class PluginHasM2MTestCase(HistoryTestCase):

    def test_detects_m2m_plugin(self):
        self.assertTrue(plugin_has_m2m('ArticlePlugin'))

    def test_plain_plugin_has_no_m2m(self):
        self.assertFalse(plugin_has_m2m('LinkPlugin'))


class M2MChangeTestCase(HistoryTestCase):
    """
    A change to a plugin with a many-to-many relation cannot be undone (the
    snapshot is restored with queryset.update(), which rejects M2M fields), so
    such a change clears the undo history instead of recording an operation
    that would crash on undo.
    """

    def setUp(self):
        super().setUp()
        self.section = Section.objects.create(name='Section')

    def _add_article(self, title='before'):
        plugin = add_plugin(self.placeholder, 'ArticlePlugin', 'en', title=title)
        plugin.sections.add(self.section)
        return plugin

    def _change_article(self, plugin, title='after'):
        # sections is required (not blank), so a valid change must include it.
        endpoint = self.get_change_plugin_uri(plugin, language='en')
        response = self.client.post(endpoint, {
            'title': title,
            'sections': [self.section.pk],
        })
        self.assertEqual(response.status_code, 200)
        # Confirm the change really applied (the form was valid and the
        # operation signal fired) rather than re-rendering an invalid form.
        self.assertEqual(ArticlePluginModel.objects.get(pk=plugin.pk).title, title)

    def test_m2m_change_is_not_recorded(self):
        with self.login_user_context(self.superuser):
            plugin = self._add_article()
            self._change_article(plugin)

        self.assertEqual(PlaceholderOperation.objects.count(), 0)

    def test_m2m_change_clears_existing_history(self):
        with self.login_user_context(self.superuser):
            # An ordinary, undoable operation is recorded first.
            self.add_plugin_via_endpoint(name='a link')
            self.assertEqual(PlaceholderOperation.objects.count(), 1)

            plugin = self._add_article()
            self._change_article(plugin)

        # The M2M change wiped the whole undo history.
        self.assertEqual(PlaceholderOperation.objects.count(), 0)

    def test_undo_after_m2m_change_finds_nothing(self):
        with self.login_user_context(self.superuser):
            self.add_plugin_via_endpoint(name='a link')
            plugin = self._add_article()
            self._change_article(plugin)

            # No crash (previously raised FieldError on the M2M field);
            # there is simply nothing left to undo.
            response = self.post_undo()

        self.assertEqual(response.status_code, 400)

    def test_plain_change_is_still_recorded(self):
        plugin = self.add_plugin(name='before')

        with self.login_user_context(self.superuser):
            self.change_plugin_via_endpoint(
                plugin,
                name='after',
                external_link='https://www.django-cms.org',
            )

        operation = self.latest_operation()
        self.assertEqual(operation.operation_type, 'change_plugin')
