from django import forms
from django.conf import settings


class UndoRedoForm(forms.Form):
    language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        required=True,
    )
    cms_path = forms.CharField(required=True)
