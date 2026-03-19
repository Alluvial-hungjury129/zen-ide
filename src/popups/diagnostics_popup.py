"""
Diagnostics popup - shows linting errors/warnings for the current file or workspace.

Displays a scrollable list of diagnostics with vim-style navigation (j/k).
Press Enter to jump to the selected diagnostic line in the editor.
"""

import os

from gi.repository import Gdk, Gtk

from icons import ICON_FONT_FAMILY, Icons
from popups.nvim_popup import NvimPopup
from shared.diagnostics_manager import Diagnostic, get_diagnostics_manager
from themes import get_theme


class DiagnosticsPopup(NvimPopup):
    """Popup showing diagnostics (errors/warnings) for the current file."""

    def __init__(self, parent: Gtk.Window, file_path: str, on_jump_to_line=None):
        self._file_path = file_path
        self._on_jump_to_line = on_jump_to_line
        self._diagnostics: list[Diagnostic] = []
        self._selected_index = 0
        self._rows: list[Gtk.Box] = []
        super().__init__(parent, title=f"Diagnostics — {os.path.basename(file_path)}", width=600)

    def _create_content(self):
        """Create the diagnostics list content."""
        mgr = get_diagnostics_manager()
        self._diagnostics = mgr.get_diagnostics(self._file_path)

        if not self._diagnostics:
            label = self._create_message_label("  No diagnostics for this file.")
            self._content_box.append(label)
            hint_bar = self._create_hint_bar([("Esc", "close")])
            self._content_box.append(hint_bar)
            return

        theme = get_theme()
        err_color = theme.term_red
        warn_color = theme.term_yellow

        # Scrolled list
        scrolled, self._listbox = self._create_scrolled_listbox(min_height=150, max_height=400)

        for diag in self._diagnostics:
            row = Gtk.ListBoxRow()
            row.add_css_class("nvim-popup-list-item")

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vbox.set_margin_start(4)
            vbox.set_margin_end(4)
            vbox.set_margin_top(2)
            vbox.set_margin_bottom(2)

            # Header row: icon, line, code
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

            # Severity icon
            if diag.severity == "error":
                icon_markup = f'<span font_family="{ICON_FONT_FAMILY}" foreground="{err_color}">{Icons.ERROR_X}</span>'
            else:
                icon_markup = f'<span font_family="{ICON_FONT_FAMILY}" foreground="{warn_color}">{Icons.WARNING}</span>'
            icon_label = Gtk.Label()
            icon_label.set_use_markup(True)
            icon_label.set_markup(icon_markup)
            icon_label.set_size_request(20, -1)
            hbox.append(icon_label)

            # Line number
            line_label = Gtk.Label(label=f"L{diag.line}")
            line_label.add_css_class("nvim-popup-keybind")
            line_label.set_size_request(50, -1)
            hbox.append(line_label)

            # Code (e.g. E501)
            if diag.code:
                code_label = Gtk.Label(label=diag.code)
                code_label.add_css_class("nvim-popup-hint")
                code_label.set_size_request(60, -1)
                hbox.append(code_label)

            vbox.append(hbox)

            # Message on its own line, wrapping
            msg_label = Gtk.Label(label=diag.message)
            msg_label.set_halign(Gtk.Align.START)
            msg_label.set_hexpand(True)
            msg_label.set_wrap(True)
            msg_label.set_margin_start(28)
            msg_label.add_css_class("nvim-popup-list-item-text")
            vbox.append(msg_label)

            row.set_child(vbox)
            self._listbox.append(row)

        # Select first row
        first_row = self._listbox.get_row_at_index(0)
        if first_row:
            self._listbox.select_row(first_row)

        # Click to jump
        self._listbox.connect("row-activated", self._on_row_activated)

        self._content_box.append(scrolled)

        # Status + hints
        errors = sum(1 for d in self._diagnostics if d.severity == "error")
        warnings = len(self._diagnostics) - errors
        status = self._create_status_label(
            f"{errors} error{'s' if errors != 1 else ''}, {warnings} warning{'s' if warnings != 1 else ''}"
        )
        self._content_box.append(status)

        hint_bar = self._create_hint_bar(
            [
                ("j/k", "navigate"),
                ("Enter", "jump to line"),
                ("Esc", "close"),
            ]
        )
        self._content_box.append(hint_bar)

    def _on_row_activated(self, listbox, row):
        """Handle row click/activation — jump to that line."""
        index = row.get_index()
        if 0 <= index < len(self._diagnostics):
            diag = self._diagnostics[index]
            if self._on_jump_to_line:
                self._on_jump_to_line(diag.line)
            self.close()

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle vim-style navigation."""
        if keyval == Gdk.KEY_j:
            self._move_selection(1)
            return True
        if keyval == Gdk.KEY_k:
            self._move_selection(-1)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            row = self._listbox.get_selected_row()
            if row:
                self._on_row_activated(self._listbox, row)
            return True
        if keyval == Gdk.KEY_q:
            self.close()
            return True
        return super()._on_key_pressed(controller, keyval, keycode, state)

    def _move_selection(self, delta: int):
        """Move listbox selection by delta rows."""
        if not self._diagnostics:
            return
        row = self._listbox.get_selected_row()
        current = row.get_index() if row else 0
        new_index = max(0, min(current + delta, len(self._diagnostics) - 1))
        new_row = self._listbox.get_row_at_index(new_index)
        if new_row:
            self._listbox.select_row(new_row)
            # Scroll into view
            new_row.grab_focus()


def show_diagnostics(parent: Gtk.Window, file_path: str, on_jump_to_line=None):
    """Show the diagnostics popup for the given file."""
    popup = DiagnosticsPopup(parent, file_path, on_jump_to_line)
    popup.present()
    return popup


class WorkspaceDiagnosticsPopup(NvimPopup):
    """Popup showing diagnostics across all workspace files."""

    def __init__(self, parent: Gtk.Window, on_jump_to_file=None):
        self._on_jump_to_file = on_jump_to_file
        self._items: list[tuple[str, Diagnostic]] = []  # (file_path, diag)
        super().__init__(parent, title="Workspace Diagnostics", width=700)

    def _create_content(self):
        mgr = get_diagnostics_manager()
        all_diags = mgr.get_all_diagnostics()

        # Flatten into (file_path, diag) pairs sorted by file then line
        for fp in sorted(all_diags):
            for diag in sorted(all_diags[fp], key=lambda d: d.line):
                self._items.append((fp, diag))

        if not self._items:
            label = self._create_message_label("  No diagnostics in workspace.")
            self._content_box.append(label)
            hint_bar = self._create_hint_bar([("Esc", "close")])
            self._content_box.append(hint_bar)
            return

        theme = get_theme()
        err_color = theme.term_red
        warn_color = theme.term_yellow

        scrolled, self._listbox = self._create_scrolled_listbox(min_height=300, max_height=600)

        for file_path, diag in self._items:
            row = Gtk.ListBoxRow()
            row.add_css_class("nvim-popup-list-item")

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vbox.set_margin_start(4)
            vbox.set_margin_end(4)
            vbox.set_margin_top(2)
            vbox.set_margin_bottom(2)

            # Header row: icon, file, line, code
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

            # Severity icon
            if diag.severity == "error":
                icon_markup = f'<span font_family="{ICON_FONT_FAMILY}" foreground="{err_color}">{Icons.ERROR_X}</span>'
            else:
                icon_markup = f'<span font_family="{ICON_FONT_FAMILY}" foreground="{warn_color}">{Icons.WARNING}</span>'
            icon_label = Gtk.Label()
            icon_label.set_use_markup(True)
            icon_label.set_markup(icon_markup)
            icon_label.set_size_request(20, -1)
            hbox.append(icon_label)

            # File basename
            fname_label = Gtk.Label(label=os.path.basename(file_path))
            fname_label.add_css_class("nvim-popup-hint")
            fname_label.set_size_request(120, -1)
            fname_label.set_halign(Gtk.Align.START)
            fname_label.set_ellipsize(2)
            hbox.append(fname_label)

            # Line number
            line_label = Gtk.Label(label=f"L{diag.line}")
            line_label.add_css_class("nvim-popup-keybind")
            line_label.set_size_request(50, -1)
            hbox.append(line_label)

            # Code
            if diag.code:
                code_label = Gtk.Label(label=diag.code)
                code_label.add_css_class("nvim-popup-hint")
                code_label.set_size_request(60, -1)
                hbox.append(code_label)

            vbox.append(hbox)

            # Message on its own line, wrapping
            msg_label = Gtk.Label(label=diag.message)
            msg_label.set_halign(Gtk.Align.START)
            msg_label.set_hexpand(True)
            msg_label.set_wrap(True)
            msg_label.set_margin_start(28)
            msg_label.add_css_class("nvim-popup-list-item-text")
            vbox.append(msg_label)

            row.set_child(vbox)
            self._listbox.append(row)

        first_row = self._listbox.get_row_at_index(0)
        if first_row:
            self._listbox.select_row(first_row)

        self._listbox.connect("row-activated", self._on_row_activated)
        self._content_box.append(scrolled)

        errors = sum(1 for _, d in self._items if d.severity == "error")
        warnings = len(self._items) - errors
        files_count = len(all_diags)
        status = self._create_status_label(
            f"{files_count} file{'s' if files_count != 1 else ''} — "
            f"{errors} error{'s' if errors != 1 else ''}, "
            f"{warnings} warning{'s' if warnings != 1 else ''}"
        )
        self._content_box.append(status)

        hint_bar = self._create_hint_bar([("j/k", "navigate"), ("Enter", "jump to file"), ("Esc", "close")])
        self._content_box.append(hint_bar)

    def _on_row_activated(self, listbox, row):
        index = row.get_index()
        if 0 <= index < len(self._items):
            file_path, diag = self._items[index]
            if self._on_jump_to_file:
                self._on_jump_to_file(file_path, diag.line)
            self.close()

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        if keyval == Gdk.KEY_j:
            self._move_selection(1)
            return True
        if keyval == Gdk.KEY_k:
            self._move_selection(-1)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            row = self._listbox.get_selected_row()
            if row:
                self._on_row_activated(self._listbox, row)
            return True
        if keyval == Gdk.KEY_q:
            self.close()
            return True
        return super()._on_key_pressed(controller, keyval, keycode, state)

    def _move_selection(self, delta: int):
        if not self._items:
            return
        row = self._listbox.get_selected_row()
        current = row.get_index() if row else 0
        new_index = max(0, min(current + delta, len(self._items) - 1))
        new_row = self._listbox.get_row_at_index(new_index)
        if new_row:
            self._listbox.select_row(new_row)
            new_row.grab_focus()


def show_workspace_diagnostics(parent: Gtk.Window, on_jump_to_file=None):
    """Show workspace-wide diagnostics popup."""
    popup = WorkspaceDiagnosticsPopup(parent, on_jump_to_file)
    popup.present()
    return popup
