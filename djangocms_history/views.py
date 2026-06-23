import json

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.views.generic import DetailView

from cms.models import CMSPlugin

try:
    from cms.toolbar.utils import (
        create_child_plugin_references,
        get_plugin_content,
        get_plugin_tree,
    )
    from cms.utils.plugins import downcast_plugins

    # django CMS 5.1+ applies the data bridge returned by undo/redo to update
    # the structure board in place. Earlier versions lack these helpers (and
    # the frontend support), so undo/redo falls back to a full page reload.
    SUPPORTS_DATA_BRIDGE = True
except ImportError:
    SUPPORTS_DATA_BRIDGE = False

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

        if not self.object.is_editable(request.user):
            return HttpResponseForbidden(
                'The operation cannot be applied because '
                'the content is not editable'
            )

        # For a move, the plugin's previous parent (the subtree it is leaving)
        # also needs its content refreshed. Capture it before the replay moves
        # the plugin away.
        self._move_old_parent_id = self._capture_move_old_parent_id()

        if self.action == 'undo':
            self.object.undo()
        else:
            self.object.redo()

        # Reflect the result to the frontend so it can update the structure
        # board in place. Add/edit operations return the plugin's close frame
        # (data bridge); move operations return the move JSON the structure
        # board expects. Anything else (or any django CMS older than 5.1)
        # falls back to an empty response and the frontend reloads the page.
        if SUPPORTS_DATA_BRIDGE:
            response = (
                self.get_close_frame_response(request)
                or self.get_move_response(request)
            )
            if response is not None:
                return response

        return HttpResponse(status=204)

    def get_close_frame_response(self, request):
        target = self.object.get_close_frame_target()

        if target is None:
            return None

        action, plugin_id, plugin_type, parent_id = target
        plugin = CMSPlugin.objects.filter(pk=plugin_id).first()

        if plugin is None:
            # The plugin no longer exists: the net effect of the undo/redo is a
            # deletion (an undone "add", a redone "delete"/"paste"). Emit a
            # "delete" frame so the frontend removes it in place.
            return self.get_delete_frame_response(request, plugin_id, plugin_type, parent_id)

        instance, plugin_admin = plugin.get_plugin_instance(admin=admin.site)

        if instance is None:
            return None

        return plugin_admin.render_close_frame(request, instance, action=action)

    def get_delete_frame_response(self, request, plugin_id, plugin_type, parent_id):
        from cms.plugin_pool import plugin_pool

        try:
            plugin_class = plugin_pool.get_plugin(plugin_type)
        except KeyError:
            return None

        plugin_admin = plugin_class(plugin_class.model, admin.site)

        # Render the (surviving) parent's subtree so the structure board
        # refreshes around the removed plugin; for a top-level plugin there is
        # no parent and the frontend just removes the node by id.
        parent = None
        if parent_id:
            db_parent = CMSPlugin.objects.filter(pk=parent_id).first()
            if db_parent is not None:
                parent = db_parent.get_bound_plugin()

        return plugin_admin.render_close_frame(
            request,
            parent,
            action='delete',
            extra_data={'deleted': True, 'plugin_id': plugin_id},
        )

    def get_move_response(self, request):
        """
        Builds the move data bridge for an undone/redone move.

        Unlike the add/edit close frame, the move bridge is normally
        co-constructed by the browser (which performed the drag) and the
        server. There is no drag during undo/redo, so we synthesise both
        halves here: the rendered tree/content from ``get_plugin_tree`` plus
        the move geometry (parent, position, source/target placeholders) the
        browser would otherwise supply.
        """
        plugin_id = self.object.get_move_plugin_id()

        if plugin_id is None:
            return None

        plugin = (
            CMSPlugin.objects
            .filter(pk=plugin_id)
            .select_related('parent', 'placeholder')
            .first()
        )

        if plugin is None:
            return None

        target_placeholder = plugin.placeholder

        # Mirror the core move view: when the plugin is nested, the whole
        # parent subtree is re-rendered; otherwise just the plugin's subtree.
        root = plugin.parent or plugin
        moved_plugins = [root] + list(root.get_descendants())
        moved_ids = {moved.pk for moved in moved_plugins}

        data = get_plugin_tree(request, moved_plugins, target_plugin=moved_plugins[0])

        # The plugin's previous parent (captured before the replay) lost a
        # child, so re-render its content too. This is what refreshes the
        # source location on cross-placeholder / un-nesting moves.
        old_parent_id = getattr(self, '_move_old_parent_id', None)
        if old_parent_id and old_parent_id not in moved_ids and data.get('content'):
            old_parent = CMSPlugin.objects.filter(pk=old_parent_id).first()
            if old_parent is not None:
                old_parent_plugins = list(downcast_plugins(
                    [old_parent] + list(old_parent.get_descendants()),
                    select_placeholder=True,
                ))
                create_child_plugin_references(old_parent_plugins)
                data['content'] += get_plugin_content(request, old_parent_plugins[0])

        if data.get('content'):
            # The first content entry is the moved subtree; flag whether it is
            # the plugin itself being inserted (top-level move) versus just its
            # parent being updated (nested move).
            data['content'][0]['insert'] = moved_plugins[0].pk == plugin.pk

        # The frontend only treats a JSON response as a data bridge if it
        # carries an ``action`` (see ``_evaluateDataBridge`` / ``onPluginSave``
        # in django CMS); without it the move is ignored and the page reloads.
        data['action'] = 'move'

        # Fields the browser normally contributes from the drag operation.
        data['plugin_id'] = plugin.pk
        data['plugin_parent'] = plugin.parent_id or ''
        data['placeholder_id'] = target_placeholder.pk
        data['target_position'] = plugin.position
        data['source_placeholder_id'] = self._get_move_source_placeholder_id(
            target_placeholder,
        )
        # Unlike a drag (where the browser has already positioned the element),
        # the structure board DOM is still in the pre-undo/redo order. The
        # frontend re-orders the moved plugin among its siblings using
        # ``plugin_order``, so it must reflect the restored order.
        data['plugin_order'] = target_placeholder.get_plugin_tree_order(
            self.object.language,
            parent_id=plugin.parent_id,
        )
        data['move_a_copy'] = False

        return HttpResponse(
            json.dumps(data),
            content_type='application/json',
        )

    def _capture_move_old_parent_id(self):
        plugin_id = self.object.get_move_plugin_id()

        if plugin_id is None:
            return None

        return (
            CMSPlugin.objects
            .filter(pk=plugin_id)
            .values_list('parent_id', flat=True)
            .first()
        )

    def _get_move_source_placeholder_id(self, target_placeholder):
        # The operation touches one placeholder (same-placeholder move) or two
        # (cross-placeholder move, recorded as MOVE_OUT + MOVE_IN actions).
        # The source is the placeholder the plugin is no longer in.
        placeholder_ids = set(
            self.object.actions.values_list('placeholder_id', flat=True)
        )
        placeholder_ids.discard(target_placeholder.pk)

        if not placeholder_ids:
            return target_placeholder.pk
        return placeholder_ids.pop()

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
