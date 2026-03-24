"""
Neovim-style command palette dialog for Zen IDE.
"""

from gi.repository import Gdk, Gtk, Pango

from popups.nvim_popup import NvimPopup


class CommandPaletteDialog(NvimPopup):
    """Neovim-style command palette with fuzzy search."""

    def __init__(
        self,
        parent: Gtk.Window,
        commands: list = None,
        on_execute=None,
        placeholder: str = "Type a command...",
    ):
        """
        Args:
            parent: Parent window
            commands: List of commands. Each command:
                      {"name": str, "label": str, "hint": str, "icon": str, "action": callable}
            on_execute: Callback when command is executed
            placeholder: Placeholder text for search
        """
        self._commands = commands or []
        self._filtered_commands = list(self._commands)
        self._on_execute = on_execute
        self._placeholder = placeholder
        self._selected_index = 0
        super().__init__(parent, "", width=550)

    def _create_content(self):
        """Create the command palette UI."""
        # Search entry
        self._entry = self._create_search_entry(self._placeholder)
        self._entry.connect("changed", self._on_search_changed)
        self._entry.connect("activate", self._on_activate)
        self._content_box.append(self._entry)

        # Results scrolled window
        scrolled, self._listbox = self._create_scrolled_listbox(
            min_height=200,
            max_height=300,
        )
        scrolled.set_margin_top(8)
        self._listbox.connect("row-activated", self._on_row_activated)
        self._content_box.append(scrolled)

        # Populate with all commands initially
        self._update_results()

    def _on_search_changed(self, entry):
        """Handle search text change."""
        self._filter_commands(entry.get_text())

    def _filter_commands(self, query: str):
        """Filter commands based on query."""
        query = query.lower().strip()

        if not query:
            self._filtered_commands = list(self._commands)
        else:
            scored = []
            for cmd in self._commands:
                name = cmd.get("name", "").lower()
                label = cmd.get("label", "").lower()
                score = 0

                # Exact match in name
                if query in name:
                    score += 100
                # Exact match in label
                if query in label:
                    score += 50
                # Fuzzy match
                fuzzy_score = self._fuzzy_match(query, name + " " + label)
                score += fuzzy_score

                if score > 0:
                    scored.append((score, cmd))

            scored.sort(key=lambda x: -x[0])
            self._filtered_commands = [cmd for _, cmd in scored]

        self._update_results()

    def _fuzzy_match(self, query: str, text: str) -> int:
        """Simple fuzzy matching score."""
        score = 0
        query_idx = 0
        for char in text:
            if query_idx < len(query) and char == query[query_idx]:
                score += 10
                query_idx += 1
        return score if query_idx == len(query) else 0

    def _update_results(self):
        """Update the results list."""
        # Clear existing
        while True:
            row = self._listbox.get_first_child()
            if row:
                self._listbox.remove(row)
            else:
                break

        # Add filtered commands
        for i, cmd in enumerate(self._filtered_commands[:20]):  # Limit to 20
            row = self._create_command_row(cmd, i)
            self._listbox.append(row)

        # Select first
        self._selected_index = 0
        first_row = self._listbox.get_first_child()
        if first_row:
            self._listbox.select_row(first_row)

    def _create_command_row(self, cmd: dict, index: int) -> Gtk.ListBoxRow:
        """Create a row for a command."""
        row = Gtk.ListBoxRow()
        row.add_css_class("nvim-popup-list-item")
        row._command = cmd

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(2)
        box.set_margin_bottom(2)

        # Icon
        if cmd.get("icon"):
            icon_label = Gtk.Label(label=cmd["icon"])
            icon_label.add_css_class("nvim-popup-list-item-icon")
            box.append(icon_label)

        # Label
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        label = Gtk.Label(label=cmd.get("label", cmd.get("name", "")))
        label.set_halign(Gtk.Align.START)
        label.add_css_class("nvim-popup-list-item-text")
        label.set_ellipsize(Pango.EllipsizeMode.END)
        text_box.append(label)

        if cmd.get("hint"):
            hint = Gtk.Label(label=cmd["hint"])
            hint.set_halign(Gtk.Align.START)
            hint.add_css_class("nvim-popup-list-item-hint")
            hint.set_ellipsize(Pango.EllipsizeMode.END)
            text_box.append(hint)

        box.append(text_box)

        # Keybinding (if any)
        if cmd.get("keybind"):
            keybind = Gtk.Label(label=cmd["keybind"])
            keybind.add_css_class("nvim-popup-keybind")
            box.append(keybind)

        row.set_child(box)
        return row

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle key press."""
        if keyval == Gdk.KEY_Escape:
            self._result = None
            self.close()
            return True
        elif keyval == Gdk.KEY_Down or (keyval == Gdk.KEY_n and state & Gdk.ModifierType.CONTROL_MASK):
            self._move_selection(1)
            return True
        elif keyval == Gdk.KEY_Up or (keyval == Gdk.KEY_p and state & Gdk.ModifierType.CONTROL_MASK):
            self._move_selection(-1)
            return True
        return False

    def _move_selection(self, delta: int):
        """Move selection by delta."""
        rows = list(self._listbox)
        if not rows:
            return

        new_idx = (self._selected_index + delta) % len(rows)
        self._selected_index = new_idx
        self._listbox.select_row(rows[new_idx])

    def _on_activate(self, entry):
        """Handle Enter in entry."""
        self._execute_selected()

    def _on_row_activated(self, listbox, row):
        """Handle row activation."""
        if hasattr(row, "_command"):
            self._execute_command(row._command)

    def _execute_selected(self):
        """Execute the selected command."""
        row = self._listbox.get_selected_row()
        if row and hasattr(row, "_command"):
            self._execute_command(row._command)

    def _execute_command(self, cmd: dict):
        """Execute a command."""
        self._result = cmd
        action = cmd.get("action")
        callback = self._on_execute
        self.close()
        if action:
            action()
        if callback:
            callback(cmd)

    def present(self):
        """Show the dialog and focus the entry."""
        super().present()
        self._entry.grab_focus()


def show_command_palette(
    parent: Gtk.Window,
    commands: list = None,
    on_execute=None,
    placeholder: str = "Type a command...",
):
    """Show a command palette and return it."""
    from popups.nvim_popup import show_popup
    from popups.system_dialogs import SystemCommandPaletteDialog

    return show_popup(
        CommandPaletteDialog,
        SystemCommandPaletteDialog,
        parent,
        commands,
        on_execute,
        placeholder,
    )
