from djangocms_history.forms import UndoRedoForm

from .base import HistoryTestCase


class UndoRedoFormTestCase(HistoryTestCase):

    def test_valid_form(self):
        form = UndoRedoForm(data={'language': 'en', 'cms_path': '/en/home/'})
        self.assertTrue(form.is_valid())

    def test_language_must_be_configured(self):
        form = UndoRedoForm(data={'language': 'xx', 'cms_path': '/en/home/'})
        self.assertFalse(form.is_valid())
        self.assertIn('language', form.errors)

    def test_fields_are_required(self):
        form = UndoRedoForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('language', form.errors)
        self.assertIn('cms_path', form.errors)
