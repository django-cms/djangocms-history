from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from django.urls import URLPattern, path

from . import views
from .models import PlaceholderOperation


@admin.register(PlaceholderOperation)
class PlaceholderOperationAdmin(admin.ModelAdmin):

    def get_model_perms(self, request: HttpRequest) -> dict[str, bool]:
        return {}

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return True  # Allow cascading deletes

    def get_urls(self) -> list[URLPattern]:
        # This sucks but its our only way to register the internal
        # undo/redo urls without asking users to configure them
        urlpatterns = [
            path('undo/', views.undo, name='djangocms_history_undo'),
            path('redo/', views.redo, name='djangocms_history_redo'),
        ]
        return urlpatterns
