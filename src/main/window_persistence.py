"""Window persistence mixin — state save/restore, paned positions, close handling."""

import os

from gi.repository import Gtk


class WindowPersistenceMixin:
    """Mixin: save/restore window state, paned positions, close handling."""

    def _reapply_saved_positions(self):
        """Re-apply saved paned positions after child swaps."""
        saved = getattr(self, "_saved_layout", None)
        if not saved:
            return
        self.main_paned.set_position(saved["main"])
        # Respect editor collapse — don't restore right position if editor is collapsed
        # Also keep editor visible when welcome screen or dev pad is showing
        if getattr(self, "_editor_collapsed", False) and not self._has_welcome_screen() and not self._has_dev_pad_tab():
            self.right_paned.set_position(0)
        else:
            self.right_paned.set_position(saved["right"])
        # bottom_paned is a placeholder Box until _create_bottom_panels —
        # only set position when it's a real Paned.
        if self._bottom_panels_created:
            if not getattr(self, "_ai_enabled", True):
                self.bottom_paned.set_position(0)
            elif saved["bottom"]:
                # Only restore saved bottom position if auto_expand_terminals is enabled
                from shared.settings import get_setting

                if get_setting("behavior.auto_expand_terminals", True):
                    self.bottom_paned.set_position(saved["bottom"])
                # If auto_expand_terminals is False, don't restore saved position
                # (keep whatever position the panel currently has)

    def _unlock_paned_positions(self):
        """Release position locks after initialization is complete."""
        for paned, handler_id in getattr(self, "_locked_position_handlers", []):
            paned.disconnect(handler_id)
        self._locked_position_handlers = []

    def _save_state(self):
        """Save layout, workspace, and settings."""
        from shared.settings import save_layout, save_workspace, set_setting
        from themes import get_theme

        # Don't save layout/workspace in single-file mode to avoid corrupting normal workspace state
        if self._cli_file:
            return
        # Don't save layout during benchmark or before layout is fully initialized
        if os.environ.get("ZEN_STARTUP_BENCH") or not self._layout_ready:
            return

        # When a panel is maximized or hidden, save the pre-maximize/hide positions
        # instead of the current (distorted) paned positions.
        if self._maximized_panel and self._saved_positions:
            main_pos = self._saved_positions.get("main", self.main_paned.get_position())
            right_pos = self._saved_positions.get("right", self.right_paned.get_position())
            bottom_pos = self._saved_positions.get(
                "bottom", self.bottom_paned.get_position() if isinstance(self.bottom_paned, Gtk.Paned) else 0
            )
        elif getattr(self, "_editor_collapsed", False):
            # Editor is collapsed — save the pre-collapse right position
            from constants import DEFAULT_EDITOR_SPLIT

            main_pos = self.main_paned.get_position()
            right_pos = getattr(self, "_pre_collapse_right_pos", None) or DEFAULT_EDITOR_SPLIT
            bottom_pos = self.bottom_paned.get_position() if isinstance(self.bottom_paned, Gtk.Paned) else 0
        else:
            main_pos = self.main_paned.get_position()
            right_pos = self.right_paned.get_position()
            bottom_pos = self.bottom_paned.get_position() if isinstance(self.bottom_paned, Gtk.Paned) else 0

        layout_vals = {
            "main_splitter": main_pos,
            "right_splitter": right_pos,
            "bottom_splitter": bottom_pos,
            "window_width": self.get_width(),
            "window_height": self.get_height(),
        }
        save_layout(layout_vals)

        # Only save folders when NOT using a workspace file (folders come from the file itself)
        from shared.settings import get_setting

        ws_file = get_setting("workspace.workspace_file", "")
        if not ws_file:
            folders = self.tree_view.get_workspace_folders()
            save_workspace(folders)
        open_files = []
        for page_num, tab in self.editor_view.tabs.items():
            if tab.file_path:
                open_files.append(tab.file_path)
        last_file = self.editor_view.get_current_file_path()
        set_setting("workspace.dev_pad_open", self.editor_view._has_dev_pad_tab(), persist=False)

        # Persist AI chat tabs before save_workspace's atomic write
        if self._ai_enabled and hasattr(self, "ai_chat") and hasattr(self.ai_chat, "save_state"):
            ai_tabs = self.ai_chat.save_state()
            set_setting("workspace.ai_tabs", ai_tabs, persist=False)

        save_workspace(open_files=open_files, last_file=last_file)

        set_setting("theme", get_theme().name)
        from fonts import set_font_settings

        set_font_settings("editor", size=self._font_size)

    def _on_close_request(self, window):
        """Save state before closing, prompt for unsaved changes."""
        from shared.file_watcher import stop_file_watcher
        from shared.utils import persist_clipboard

        if self.editor_view.has_unsaved_changes():
            from popups.save_all_confirm_popup import show_save_all_confirm

            unsaved = self.editor_view.get_unsaved_tabs()
            names = [os.path.basename(t.file_path) if t.file_path else "Untitled" for _, t in unsaved]

            def on_save_all():
                for tab_id, tab in self.editor_view.tabs.items():
                    if tab.modified and tab.file_path:
                        tab.save_file()
                self._save_state()
                stop_file_watcher()
                if hasattr(self, "ai_chat") and hasattr(self.ai_chat, "cleanup"):
                    self.ai_chat.cleanup()
                if hasattr(self.terminal_view, "cleanup"):
                    self.terminal_view.cleanup()
                persist_clipboard()
                os._exit(0)

            def on_discard_all():
                self._save_state()
                stop_file_watcher()
                if hasattr(self, "ai_chat") and hasattr(self.ai_chat, "cleanup"):
                    self.ai_chat.cleanup()
                if hasattr(self.terminal_view, "cleanup"):
                    self.terminal_view.cleanup()
                persist_clipboard()
                os._exit(0)

            show_save_all_confirm(
                self,
                filenames=names,
                on_save_all=on_save_all,
                on_discard_all=on_discard_all,
                on_cancel=None,  # Cancel just closes popup
            )
            return True  # Prevent close for now

        self._save_state()
        stop_file_watcher()
        if hasattr(self, "ai_chat") and hasattr(self.ai_chat, "cleanup"):
            self.ai_chat.cleanup()
        if hasattr(self.terminal_view, "cleanup"):
            self.terminal_view.cleanup()
        persist_clipboard()
        os._exit(0)
