"""View actions mixin — view and navigation action handlers for the main window."""

import os

from gi.repository import GLib


class ViewActionsMixin:
    """Mixin: action handlers for view/navigation menu items."""

    # --- View / Navigation actions ---

    def _on_focus_explorer(self, action, param):
        """Focus the tree view."""
        self._focused_panel = "tree"
        if not self.tree_view.get_visible():
            self.tree_view.set_visible(True)
        self.tree_view.focus_tree()

    def _on_clear_terminal(self, action, param):
        """Clear the terminal."""
        self.terminal_view.clear()

    def _on_global_search(self, action, param):
        """Open global search dialog."""
        from popups.global_search_dialog import GlobalSearchDialog

        folders = self.tree_view.get_workspace_folders()
        dialog = GlobalSearchDialog(
            self,
            workspace_folders=folders,
            on_result_selected=lambda path, line: self.editor_view.open_file(path, line),
        )
        dialog.present()

    def _on_quick_open(self, action, param):
        """Open quick open dialog."""
        from popups.quick_open_dialog import QuickOpenDialog

        folders = self.tree_view.get_workspace_folders()
        dialog = QuickOpenDialog(
            self,
            workspace_folders=folders,
            on_file_selected=lambda path: self.editor_view.open_file(path),
        )
        dialog.present()

    def _on_show_diff(self, action, param):
        """Toggle diff view in split pane for current file."""
        if self.split_panels.is_visible("diff"):
            self.split_panels.hide("diff")
            return
        file_path = self.editor_view.get_current_file_path()
        if file_path:
            self.split_panels.show("diff", file_path=file_path, content=self.editor_view.get_current_content())

    def _on_show_dev_pad(self, action, param):
        """Toggle the Dev Pad tab."""
        self.editor_view.toggle_dev_pad(self.dev_pad)

    def _on_open_sketch_pad(self, action, param):
        """Open the workspace .zen_sketch file, or create a new in-memory sketch."""
        import glob as glob_mod

        folders = self.tree_view.get_workspace_folders()

        # Look for existing .zen_sketch file in workspace roots
        for folder in folders:
            matches = glob_mod.glob(os.path.join(folder, "*.zen_sketch"))
            if matches:
                self.editor_view.open_file(matches[0])
                return

        # No existing file — open an in-memory sketch tab (no file created)
        self.editor_view.new_sketch_file()

    def _on_focus_terminal(self, action, param):
        """Focus the terminal."""
        self._focused_panel = "terminal"
        self.terminal_view.grab_focus()

    def _on_focus_ai_chat(self, action, param):
        """Focus the AI chat input."""
        self._focused_panel = "ai_chat"
        self.ai_chat.focus_input()

    def _on_open_ai_chat(self, session_id: str):
        """Focus or restore an AI session from Dev Pad."""
        # Ensure AI panel is visible
        self.ai_chat.set_visible(True)
        self.ai_chat.focus_session(session_id)

    def _on_stop_ai(self, action, param):
        """Stop AI generation if processing, or close diff view."""
        if self.ai_chat.is_processing():
            self.ai_chat.stop_ai()
        elif self.split_panels.is_visible("diff"):
            self.split_panels.hide("diff")

    def _on_next_tab(self, action, param):
        """Switch to next editor tab."""
        n = self.editor_view.notebook.get_n_pages()
        if n > 1:
            current = self.editor_view.notebook.get_current_page()
            self.editor_view.notebook.set_current_page((current + 1) % n)

    def _on_prev_tab(self, action, param):
        """Switch to previous editor tab."""
        n = self.editor_view.notebook.get_n_pages()
        if n > 1:
            current = self.editor_view.notebook.get_current_page()
            self.editor_view.notebook.set_current_page((current - 1) % n)

    def _on_zoom_in(self, action, param):
        """Increase font size (or sketch zoom if sketch tab is active)."""
        tab = self.editor_view._get_current_tab()
        if getattr(tab, "_is_sketch", False):
            tab.widget._canvas_widget.zoom(0.1)
            return

        from constants import MAX_FONT_SIZE

        self._font_size = min(self._font_size + 1, MAX_FONT_SIZE)
        self._apply_font_size()
        self._zoom_markdown_previews("in")

    def _on_zoom_out(self, action, param):
        """Decrease font size (or sketch zoom if sketch tab is active)."""
        tab = self.editor_view._get_current_tab()
        if getattr(tab, "_is_sketch", False):
            tab.widget._canvas_widget.zoom(-0.1)
            return

        from constants import MIN_FONT_SIZE

        self._font_size = max(self._font_size - 1, MIN_FONT_SIZE)
        self._apply_font_size()
        self._zoom_markdown_previews("out")

    def _on_maximize_focused(self, action, param):
        """Maximize the currently focused panel, or restore if already maximized."""
        # If any panel is already maximized, restore it first
        if self._maximized_panel:
            self._maximize_panel(self._maximized_panel)
            return

        # Use FocusManager as source of truth since it's updated by panel clicks
        from shared.focus_manager import get_focus_manager

        focus_mgr = get_focus_manager()
        focused = focus_mgr.get_current_focus()
        # Map component IDs to panel names (they're the same in our case)
        panel = focused if focused in ("editor", "terminal", "ai_chat", "tree", "treeview") else self._focused_panel
        # Normalize "treeview" to "tree"
        if panel == "treeview":
            panel = "tree"
        self._maximize_panel(panel)

    def _on_maximize_window(self, action, param):
        """Maximize window and reset layout to defaults (Cmd+Shift+0)."""
        # Reset layout to defaults
        self._maximized_panel = None
        self._sync_maximize_buttons()
        self._saved_positions = {}
        if not self.is_maximized():
            self.maximize()
            # Window maximize is async; delay layout until resize completes
            GLib.timeout_add(150, self._apply_default_layout)
        else:
            GLib.idle_add(self._apply_default_layout)

    def _on_reset_layout(self, action, param):
        """Reset all splitter positions to default layout."""
        # Restore any maximized panel
        if self._maximized_panel:
            self._maximized_panel = None
            self._sync_maximize_buttons()

        # Clear saved positions
        self._saved_positions = {}

        # If panels were hidden in single-file mode, create and show them
        if not self._bottom_panels_created:
            self._create_bottom_panels()
            if getattr(self, "_ai_enabled", True):
                self.ai_chat.on_maximize = lambda name: self._maximize_panel(name)
            self.terminal_view.on_maximize = lambda name: self._maximize_panel(name)
        self.tree_view.set_visible(True)
        self.bottom_paned.set_visible(True)

        # Use idle_add to ensure window size is available after any pending operations
        GLib.idle_add(self._apply_default_layout)
