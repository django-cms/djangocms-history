from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import DetailView

from .forms import UndoRedoForm
from .helpers import (
    get_active_operation,
    get_inactive_operation,
    get_operations_from_request,
)
from .models import PlaceholderOperation


class UndoRedoView(DetailView):
    action = None
    model = PlaceholderOperation
    http_method_names = ['post']
    form_class = UndoRedoForm

    def post(self, request, *args, **kwargs):
        user = request.user

        if not (user.is_active and user.is_staff):
            raise PermissionDenied

        self.form = self.form_class(request.POST)

        if not self.form.is_valid():
            return HttpResponseBadRequest('No operation found')

        self.object = self.get_object()

        if not self.object:
            return HttpResponseBadRequest('No operation found')

        if self.action == 'undo':
            self.object.undo()
        else:
            self.object.redo()
        return HttpResponse(status=204)

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()

        if self.action == 'undo':
            operation = get_active_operation(queryset)
        else:
            operation = get_inactive_operation(queryset)
        return operation

    def get_queryset(self):
        data = self.form.cleaned_data
        queryset = get_operations_from_request(
            self.request,
            path=data['cms_path'],
            language=data['language'],
        )
        return queryset


undo = UndoRedoView.as_view(action='undo')
redo = UndoRedoView.as_view(action='redo')
