"""
Tree View (File Explorer) for Zen IDE.
Minimalist custom-drawn treeview using GtkSnapshot for full control.
"""

import os
import threading
from pathlib import Path
from typing import Callable, List, Optional, Set

from gi.repository import GLib, Gtk, Pango

from constants import PANEL_HEADER_FONT_SIZE
from fonts import get_font_settings
from shared.focus_border_mixin import FocusBorderMixin
from shared.focus_manager import get_component_focus_manager
from shared.git_manager import get_git_manager
from shared.main_thread import main_thread_call
from themes import get_theme, subscribe_theme_change
from treeview.tree_panel import CustomTreePanel
from treeview.tree_view_actions import TreeViewActionsMixin


class TreeView(TreeViewActionsMixin, FocusBorderMixin, Gtk.Box):
    """File tree explorer panel with neovim-style indent guides."""

    COMPONENT_ID = "treeview"
    HEADER_HEIGHT = 45

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        # Initialize focus border
        self._init_focus_border()

        # Register with focus manager
        focus_mgr = get_component_focus_manager()
        focus_mgr.register(
            self.COMPONENT_ID,
            on_focus_in=self._on_focus_in,
            on_focus_out=self._on_focus_out,
        )

        self.on_file_selected: Optional[Callable[[str], None]] = None
        self._workspace_loaded = False
        self._workspace_name: Optional[str] = None

        # Callbacks for context menu actions
        self.write_to_terminal: Optional[Callable[[str], None]] = None
        self.on_show_diff: Optional[Callable[[str], None]] = None
        self.on_git_refresh: Optional[Callable[[], None]] = None

        # Git modified files tracking
        self._git_modified_files: Set[str] = set()

        # Git status debounce timer
        self._git_status_timer: Optional[int] = None

        # Suppress file-watcher-triggered refresh until this timestamp
        self._suppress_watcher_until = 0

        self._create_ui()

        # Subscribe to theme changes
        subscribe_theme_change(self._on_theme_change)

        # Add click controller to gain focus
        click_ctrl = Gtk.GestureClick.new()
        click_ctrl.connect("pressed", self._on_panel_click)
        self.add_controller(click_ctrl)

    def _on_theme_change(self, theme):
        """Handle theme change."""
        self.apply_theme(theme)

    def apply_theme(self, theme=None):
        """Apply theme colors."""
        if theme is None:
            theme = get_theme()

        # Update header
        if hasattr(self, "header"):
            css = f"""
                label {{
                    color: {theme.fg_color};
                    background-color: {theme.tree_bg};
                }}
            """
            provider = Gtk.CssProvider()
            provider.load_from_string(css)
            self.header.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Update background
        css = f"""
            box {{
                background-color: {theme.tree_bg};
            }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        self.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _create_ui(self):
        """Create the tree control."""
        theme = get_theme()

        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header_box.set_size_request(-1, self.HEADER_HEIGHT)

        # Get font from settings
        font_settings = get_font_settings("explorer")
        font_family = font_settings["family"]

        self.header = Gtk.Label(label="EXPLORER")
        self.header.set_xalign(0)
        self.header.set_hexpand(True)
        self.header.set_ellipsize(Pango.EllipsizeMode.END)
        self.header.set_margin_start(8)
        self.header.set_margin_end(8)
        self.header.set_margin_top(8)

        css = f"""
            label {{
                font-family: "{font_family}";
                font-size: {PANEL_HEADER_FONT_SIZE}pt;
                font-weight: 500;

                color: {theme.fg_color};
            }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        self.header.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        header_box.append(self.header)
        self.append(header_box)

        # Custom tree panel
        self.tree = CustomTreePanel(self)
        self.tree.set_vexpand(True)
        self.tree.set_hexpand(True)
        self.append(self.tree)

        # Apply theme
        self.apply_theme(theme)

    def _update_header(self):
        """Update header to show workspace name."""
        if self._workspace_name:
            label = f"EXPLORER ({self._workspace_name})"
            self.header.set_label(label)
            self.header.set_tooltip_text(self._workspace_name)
        elif self.tree.roots:
            name = self.tree.roots[0].path.name
            label = f"EXPLORER ({name})"
            self.header.set_label(label)
            self.header.set_tooltip_text(str(self.tree.roots[0].path))
        else:
            self.header.set_label("EXPLORER")
            self.header.set_tooltip_text(None)

    def _load_workspace(self):
        """Load the current working directory into the tree."""
        cwd = Path.cwd()
        self.tree.load_directory(cwd)
        self._update_header()

    def refresh(self):
        """Refresh the tree view while preserving state."""
        import time

        if time.monotonic() < self._suppress_watcher_until:
            return

        # Save current state
        expanded_paths = self._get_expanded_paths()
        selected_paths = [str(item.path) for item in self.tree.get_selected_items()]
        primary_selected_path = str(self.tree.selected_item.path) if self.tree.selected_item else None

        # Save scroll position before rebuild
        vadj = self.tree.get_vadjustment()
        saved_scroll = vadj.get_value() if vadj else 0

        # Save workspace folder paths
        workspace_paths = [root.path for root in self.tree.roots]

        # Clear and reload
        self.tree.clear()

        if workspace_paths:
            for folder_path in workspace_paths:
                if folder_path.exists() and folder_path.is_dir():
                    self.tree.load_directory(folder_path)
        else:
            self._load_workspace()

        # Update header with workspace name
        self._update_header()

        # Restore expanded folders
        self._restore_expanded_paths(expanded_paths)

        # Restore selection
        if selected_paths:
            self._restore_selection(selected_paths, primary_selected_path)

        # Restore scroll position after rebuild
        if vadj and saved_scroll > 0:
            total_height = len(self.tree.items) * self.tree.row_height
            if total_height > 0:
                vadj.set_upper(total_height)
            vadj.set_value(saved_scroll)
            GLib.idle_add(lambda: vadj.set_value(saved_scroll) or False)

    def _get_expanded_paths(self) -> Set[str]:
        """Get set of all expanded folder paths."""
        expanded = set()

        def collect_expanded(item):
            if item.is_dir and item.expanded:
                expanded.add(str(item.path))
                for child in item.children:
                    collect_expanded(child)

        for root in self.tree.roots:
            collect_expanded(root)

        return expanded

    def _restore_expanded_paths(self, expanded_paths: Set[str]):
        """Restore expanded state for folders."""

        def restore_item(item):
            if item.is_dir and str(item.path) in expanded_paths:
                if not item.expanded:
                    item.expanded = True
                    if not item.children:
                        self.tree._load_children(item)
                for child in item.children:
                    restore_item(child)

        for root in self.tree.roots:
            restore_item(root)

        self.tree._flatten_items()

    def _restore_selection(self, selected_paths: List[str], primary_path: str | None = None):
        """Restore selection to a set of specific paths."""
        if not selected_paths:
            return

        path_set = set(selected_paths)
        matched_items = [item for item in self.tree.items if str(item.path) in path_set]
        if not matched_items:
            self.tree._clear_selection()
            return

        primary_item = next((item for item in matched_items if str(item.path) == primary_path), matched_items[-1])
        anchor_item = next((item for item in matched_items if str(item.path) == primary_path), matched_items[0])
        self.tree._set_selection(matched_items, primary_item=primary_item, anchor_item=anchor_item)

    def load_workspace(self, folders: List[str], workspace_name: str = None):
        """Load workspace by clearing tree and loading multiple folders."""
        self._workspace_name = workspace_name
        self.tree.clear()
        for folder_path in folders:
            workspace = Path(folder_path)
            if workspace.exists() and workspace.is_dir():
                self.tree.load_directory(workspace)
        self._update_header()

    def refresh_git_status(self):
        """Refresh git status with debounce to prevent concurrent git processes."""
        if self._git_status_timer is not None:
            GLib.source_remove(self._git_status_timer)

        self._git_status_timer = GLib.timeout_add(300, self._do_refresh_git_status)

    def _do_refresh_git_status(self):
        """Execute the debounced git status refresh in a background thread."""
        self._git_status_timer = None
        workspace_folders = self.get_workspace_folders()

        def _run_git_status():
            git = get_git_manager()
            status_map = git.get_all_detailed_status(workspace_folders)
            modified_files = set(status_map.keys())
            main_thread_call(self.set_git_modified_files, modified_files, status_map)

        thread = threading.Thread(target=_run_git_status, daemon=True)
        thread.start()
        return False  # Don't repeat timer

    def set_git_modified_files(self, modified_files: set, status_map: dict = None):
        """Set git modified files and update tree display."""
        self._git_modified_files = modified_files
        self.tree.set_git_modified_files(modified_files, status_map)

    def get_workspace_folders(self) -> List[str]:
        """Get list of workspace folder paths."""
        return [str(root.path) for root in self.tree.roots]

    def reveal_file(self, file_path: str, animate: bool = True):
        """Reveal and select a file in the tree with optional animation."""
        file_path = os.path.normpath(str(file_path).strip())

        # Check if already visible
        for item in self.tree.items:
            if os.path.normpath(str(item.path)) == file_path:
                self.tree._select_single_item(item)
                self.tree._ensure_visible(item, animate=animate)
                self.tree._request_redraw()
                return

        # Find root containing this file
        target_root = None
        for root in self.tree.roots:
            root_path = os.path.normpath(str(root.path))
            if file_path.startswith(root_path + os.sep) or file_path == root_path:
                target_root = root
                break

        if not target_root:
            return

        # Expand path components
        root_path = os.path.normpath(str(target_root.path))
        relative_path = file_path[len(root_path) :].lstrip(os.sep)
        path_parts = relative_path.split(os.sep)

        current_item = target_root
        if not current_item.expanded:
            current_item.expanded = True
            if not current_item.children:
                self.tree._load_children(current_item)

        for i, part in enumerate(path_parts):
            found_child = None
            for child in current_item.children:
                if child.name == part:
                    found_child = child
                    break

            if not found_child:
                break

            if found_child.is_dir and i < len(path_parts) - 1:
                if not found_child.expanded:
                    found_child.expanded = True
                    if not found_child.children:
                        self.tree._load_children(found_child)

            current_item = found_child

        self.tree._flatten_and_redraw()

        # Select the item and defer scroll to let GTK settle after tree changes
        for item in self.tree.items:
            if os.path.normpath(str(item.path)) == file_path:
                self.tree._select_single_item(item)
                self.tree._request_redraw()
                self.tree._ensure_visible_gen += 1
                gen = self.tree._ensure_visible_gen
                GLib.idle_add(self.tree._ensure_visible, item, animate, 0, gen)
                return

    def _on_panel_click(self, gesture, n_press, x, y):
        """Handle click on panel to gain focus."""
        self._handle_panel_click_focus()

    def _on_focus_in(self):
        """Called when this panel gains focus."""
        self._handle_panel_focus_in()

    def _on_focus_out(self):
        """Called when this panel loses focus."""
        self._handle_panel_focus_out()

    def focus_tree(self):
        """Focus the tree and notify focus manager."""
        get_component_focus_manager().set_focus(self.COMPONENT_ID)
        if hasattr(self, "tree") and hasattr(self.tree, "drawing_area"):
            self.tree.drawing_area.grab_focus()
