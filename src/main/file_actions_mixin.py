"""File actions mixin — file-related action handlers for the main window."""

import os

from gi.repository import Gio, GLib, Gtk


class FileActionsMixin:
    """Mixin: action handlers for file menu items (new, open, save, close, workspace)."""

    # --- File actions ---

    def _on_new(self, action, param):
        """Create a new file."""
        self.editor_view.new_file()

    def _on_new_sketch_pad(self, action, param):
        """Create a new untitled sketch pad."""
        self.editor_view.new_sketch_file()

    def _on_open(self, action, param):
        """Open a file."""
        dialog = Gtk.FileDialog()
        dialog.open(self, None, self._on_open_response)

    def _on_open_response(self, dialog, result):
        """Handle file dialog response."""
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                self.editor_view.open_file(path)
        except GLib.Error:
            pass  # Cancelled

    def _on_open_folder(self, action, param):
        """Open a folder as workspace."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Open Folder")
        dialog.select_folder(self, None, self._on_open_folder_response)

    def _on_open_folder_response(self, dialog, result):
        """Handle folder dialog response."""
        try:
            file = dialog.select_folder_finish(result)
            if file:
                path = file.get_path()
                from shared.git_ignore_utils import collect_global_patterns
                from shared.settings import set_setting

                collect_global_patterns([path])
                self.tree_view.load_workspace([path])
                self.set_title(f"Zen IDE — {os.path.basename(path)}")
                set_setting("workspace.workspace_file", "")
                set_setting("workspace.folders", [path])
                # Show all panels in case we were in single-file mode
                self._show_all_panels()
        except GLib.Error:
            pass  # Cancelled

    def _on_new_workspace(self, action, param):
        """Create a new .zen-workspace file with a template and prompt to save."""
        import json as json_module

        # Start with a blank template — the user will fill in the folders
        template = {
            "folders": [
                {
                    "name": "my-project",
                    "path": ".",
                }
            ],
        }
        content = json_module.dumps(template, indent=2) + "\n"

        # Show a Save dialog so the user picks where to store the workspace file
        dialog = Gtk.FileDialog()
        dialog.set_title("Save New Workspace As")

        # Default file name
        dialog.set_initial_name("my-project.zen-workspace")

        # Filter for workspace files
        filter_ws = Gtk.FileFilter()
        filter_ws.set_name("Zen Workspace Files")
        filter_ws.add_pattern("*.zen-workspace")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_ws)
        dialog.set_filters(filters)

        dialog.save(
            self,
            None,
            lambda d, r: self._on_new_workspace_save_response(d, r, content),
        )

    def _on_new_workspace_save_response(self, dialog, result, content):
        """Handle the Save dialog response for a new workspace file."""
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            path = file.get_path()

            # Ensure .zen-workspace extension
            if not path.endswith(".zen-workspace"):
                path += ".zen-workspace"

            # Write the template to disk
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            # Open the newly created file in the editor for further editing
            self.editor_view.open_file(path)

            # Ask whether to load this workspace now
            from popups.confirm_dialog import show_confirm

            show_confirm(
                self,
                title="Load Workspace",
                message=f'Workspace "{os.path.basename(path)}" saved.\n\nDo you want to load it now?',
                confirm_text="Load",
                cancel_text="Not Now",
                on_confirm=lambda: self._load_workspace_file(path),
            )
        except GLib.Error:
            pass  # User cancelled

    def _on_open_workspace(self, action, param):
        """Open a .zen-workspace or .code-workspace file."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Open Workspace")
        # Filter for workspace files
        filter_ws = Gtk.FileFilter()
        filter_ws.set_name("Workspace Files")
        filter_ws.add_pattern("*.zen-workspace")
        filter_ws.add_pattern("*.code-workspace")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_ws)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_open_workspace_response)

    def _on_open_workspace_response(self, dialog, result):
        """Handle workspace dialog response."""
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                self._load_workspace_file(path)
        except GLib.Error:
            pass  # Cancelled

    def _on_edit_workspace(self, action, param):
        """Open the current workspace file in the editor for manual editing."""
        from shared.settings import get_setting

        ws_file = get_setting("workspace.workspace_file", "")
        if ws_file and os.path.isfile(ws_file):
            self.editor_view.open_file(ws_file)

    def _load_workspace_file(self, workspace_path: str):
        """Load a .zen-workspace or .code-workspace file and open its folders."""
        import json as json_module
        import re

        from shared.git_ignore_utils import collect_global_patterns
        from shared.settings import set_setting

        try:
            with open(workspace_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Workspace files may have trailing commas and comments
            # Remove single-line comments (// ...)
            content = re.sub(r"//[^\n]*", "", content)
            # Remove trailing commas before } or ]
            content = re.sub(r",(\s*[}\]])", r"\1", content)

            workspace_data = json_module.loads(content)

            folders = workspace_data.get("folders", [])
            if not folders:
                return

            # Resolve folder paths relative to workspace file
            ws_dir = os.path.dirname(workspace_path)
            resolved_folders = []
            for folder in folders:
                folder_path = folder.get("path", "")
                if folder_path:
                    if not os.path.isabs(folder_path):
                        folder_path = os.path.normpath(os.path.join(ws_dir, folder_path))
                    if os.path.isdir(folder_path):
                        resolved_folders.append(folder_path)
                    else:
                        pass

            if resolved_folders:
                # Collect gitignore patterns BEFORE loading tree
                collect_global_patterns(resolved_folders)
                # Load multiple workspace folders
                ws_name = os.path.basename(workspace_path)
                self.tree_view.load_workspace(resolved_folders, workspace_name=ws_name)
                self.set_title(f"Zen IDE — {ws_name}")
                set_setting("workspace.workspace_file", workspace_path)
                set_setting("workspace.folders", [])
                # Show all panels in case we were in single-file mode
                self._show_all_panels()
        except Exception:
            pass

    # --- Save / Close ---

    def _on_save(self, action, param):
        """Save current file."""
        if self.editor_view.save_current():
            from shared.settings import SETTINGS_FILE, load_settings

            # Reload settings if the user just saved settings.json
            current_path = self.editor_view.get_current_file_path()
            if current_path and SETTINGS_FILE == current_path:
                try:
                    load_settings()
                except Exception:
                    pass

    def _on_close_tab(self, action, param):
        """Close current tab."""
        # Hide diff view before closing so the next tab doesn't open in diff mode
        if self.split_panels.is_visible("diff"):
            self.split_panels.hide("diff")
        self.editor_view.close_current_tab()
        if not self._has_open_files():
            self.status_bar_widget.set_file(None)
