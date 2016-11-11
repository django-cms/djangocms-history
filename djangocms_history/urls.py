from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^undo/$', views.undo, name='djangocms_history_undo'),
    url(r'^redo/$', views.redo, name='djangocms_history_redo'),
]
