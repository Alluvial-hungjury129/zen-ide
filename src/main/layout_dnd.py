"""Layout drag-and-drop mixin — file/folder drop handling for the IDE window."""

import os

from gi.repository import Gdk, Gtk


class LayoutDndMixin:
    """Mixin: drag-and-drop file/folder handling for the IDE window."""

    def _setup_file_drop_target(self, widget):
        """Set up drag-and-drop target to open external files dragged into the IDE."""
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
        drop_target.connect("drop", self._on_file_drop)
        widget.add_controller(drop_target)

    def _on_file_drop(self, drop_target, value, x, y):
        """Handle files/folders dropped from external file managers."""
        from shared.git_ignore_utils import collect_global_patterns
        from shared.settings import set_setting

        if not isinstance(value, Gdk.FileList):
            return False
        files = value.get_files()
        opened = False
        for gfile in files:
            path = gfile.get_path()
            if not path:
                continue
            path = os.path.abspath(path)
            if os.path.isdir(path):
                # Dropped a folder — open it as workspace
                collect_global_patterns([path])
                self.tree_view.load_workspace([path])
                self.set_title(f"Zen IDE — {os.path.basename(path)}")
                set_setting("workspace.workspace_file", "")
                set_setting("workspace.folders", [path])
                self._show_all_panels()
                opened = True
            elif path.endswith((".zen-workspace", ".code-workspace")) and os.path.isfile(path):
                # Dropped a workspace file — load it
                self._load_workspace_file(path)
                opened = True
            elif os.path.isfile(path):
                self.editor_view.open_file(path)
                opened = True
        return opened
