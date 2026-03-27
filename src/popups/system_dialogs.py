"""
System-style dialog implementations for when nvim emulation is disabled.

Uses Gtk.Popover for context-aware positioning instead of centered windows.
When behavior.is_nvim_emulation_enabled is False, the show_* helper functions
in each popup module delegate to these system-style alternatives.
"""

from gi.repository import Gdk, Gtk, Pango

from shared.settings import get_setting
from shared.ui import ZenButton
from shared.ui.zen_entry import ZenEntry, ZenSearchEntry


def is_nvim_mode() -> bool:
    """Check if nvim emulation is enabled."""
    return get_setting("behavior.is_nvim_emulation_enabled", True)


def _get_popover_parent(parent):
    """Get widget for popover anchoring — prefers focused widget for context-aware positioning."""
    if isinstance(parent, Gtk.Window):
        focus = parent.get_focus()
        if focus and focus.get_realized():
            return focus
        child = parent.get_child()
        if child and child.get_realized():
            return child
    return parent


def _apply_popover_theme(popover: Gtk.Popover):
    """Apply themed border and background to a system-style popover."""
    from shared.utils import hex_to_rgba_css
    from themes import get_theme

    theme = get_theme()
    bg = hex_to_rgba_css(theme.panel_bg, 0.92)
    css = f"""
        popover.background > contents {{
            background-color: {bg};
            border: 1px solid {theme.border_focus};
        }}
        popover.background > contents > * listbox {{
            background-color: transparent;
        }}
        popover.background > contents > * listbox > row {{
            background-color: transparent;
            outline: none;
        }}
        popover.background > contents > * listbox > row:focus,
        popover.background > contents > * listbox > row:focus-visible {{
            outline: none;
        }}
        popover.background > contents > * listbox > row:selected {{
            background-color: {theme.selection_bg};
            outline: none;
        }}
        popover.background > contents > * listbox > row:hover {{
            background-color: {theme.hover_bg};
        }}
        popover.background > contents entry {{
            border: 1px solid {theme.border_color};
            outline: none;
            outline-width: 0;
        }}
        popover.background > contents entry:focus-within {{
            border-color: {theme.accent_color};
            outline: none;
            outline-width: 0;
        }}
        popover.background > contents entry > text {{
            outline: none;
            outline-width: 0;
        }}
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_USER,
    )


# ---------------------------------------------------------------------------
# Gtk.AlertDialog-based system dialogs (confirm, save)
# ---------------------------------------------------------------------------


def system_confirm(parent, title, message, confirm_text, cancel_text, danger, on_confirm, on_cancel):
    """Show a system-style confirm dialog using Gtk.AlertDialog."""
    dialog = Gtk.AlertDialog()
    dialog.set_message(title)
    dialog.set_detail(message)
    dialog.set_buttons([cancel_text, confirm_text])
    dialog.set_cancel_button(0)
    dialog.set_default_button(1)

    def on_response(source, result):
        try:
            response = source.choose_finish(result)
            if response == 1:
                if on_confirm:
                    on_confirm()
            else:
                if on_cancel:
                    on_cancel()
        except Exception:
            if on_cancel:
                on_cancel()

    dialog.choose(parent, None, on_response)


def system_save_confirm(parent, filename, on_save, on_discard, on_cancel):
    """Show a system-style save confirmation dialog."""
    dialog = Gtk.AlertDialog()
    dialog.set_message("Unsaved Changes")
    dialog.set_detail(f'Save changes to "{filename}"?\nYour changes will be lost if you don\'t save them.')
    dialog.set_buttons(["Cancel", "Save"])
    dialog.set_cancel_button(0)
    dialog.set_default_button(1)

    def on_response(source, result):
        try:
            response = source.choose_finish(result)
            if response == 1:
                if on_save:
                    on_save()
            else:
                if on_cancel:
                    on_cancel()
        except Exception:
            if on_cancel:
                on_cancel()

    dialog.choose(parent, None, on_response)


def system_save_all_confirm(parent, filenames, on_save_all, on_discard_all, on_cancel):
    """Show a system-style save-all confirmation dialog."""
    files_text = "\n".join(f"• {f}" for f in filenames[:5])
    if len(filenames) > 5:
        files_text += f"\n... and {len(filenames) - 5} more"

    dialog = Gtk.AlertDialog()
    dialog.set_message("Save changes before closing?")
    dialog.set_detail(files_text)
    dialog.set_buttons(["Cancel", "Discard All", "Save All"])
    dialog.set_cancel_button(0)
    dialog.set_default_button(2)

    def on_response(source, result):
        try:
            response = source.choose_finish(result)
            if response == 2:
                if on_save_all:
                    on_save_all()
            elif response == 1:
                if on_discard_all:
                    on_discard_all()
            else:
                if on_cancel:
                    on_cancel()
        except Exception:
            if on_cancel:
                on_cancel()

    dialog.choose(parent, None, on_response)


# ---------------------------------------------------------------------------
# Gtk.Popover-based system dialogs (positioned near trigger context)
# ---------------------------------------------------------------------------


class SystemInputDialog(Gtk.Popover):
    """System-style input dialog using Gtk.Popover for context-aware positioning."""

    def __init__(self, parent, title, message, placeholder, initial_value, on_submit, validate):
        super().__init__()

        target = _get_popover_parent(parent)
        self.set_parent(target)
        self.set_has_arrow(False)
        self.set_autohide(True)
        _apply_popover_theme(self)

        self._on_submit = on_submit
        self._validate = validate

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_size_request(400, -1)

        if title:
            title_label = Gtk.Label(label=title)
            title_label.set_halign(Gtk.Align.START)
            title_label.add_css_class("title-3")
            content.append(title_label)

        if message:
            msg_label = Gtk.Label(label=message)
            msg_label.set_halign(Gtk.Align.START)
            msg_label.set_wrap(True)
            content.append(msg_label)

        self._entry = ZenEntry(placeholder=placeholder, initial_value=initial_value or "")
        self._entry.connect("activate", lambda e: self._submit())
        self._entry.connect("changed", self._on_changed)
        content.append(self._entry)

        self._error_label = Gtk.Label()
        self._error_label.add_css_class("error")
        self._error_label.set_halign(Gtk.Align.START)
        self._error_label.set_visible(False)
        content.append(self._error_label)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)

        cancel_btn = ZenButton(label="Cancel")
        cancel_btn.connect("clicked", lambda b: self.popdown())
        button_box.append(cancel_btn)

        ok_btn = ZenButton(label="OK", variant="primary")
        ok_btn.connect("clicked", lambda b: self._submit())
        button_box.append(ok_btn)

        content.append(button_box)
        self.set_child(content)

        self.connect("closed", self._on_closed)

    def _on_closed(self, popover):
        if self.get_parent():
            self.unparent()

    def _on_changed(self, entry):
        if self._validate:
            error = self._validate(entry.get_text())
            if error:
                self._error_label.set_text(error)
                self._error_label.set_visible(True)
            else:
                self._error_label.set_visible(False)

    def _submit(self):
        text = self._entry.get_text()
        if self._validate:
            error = self._validate(text)
            if error:
                self._error_label.set_text(error)
                self._error_label.set_visible(True)
                return
        callback = self._on_submit
        self.popdown()
        if callback:
            callback(text)

    def present(self):
        self.popup()
        self._entry.grab_focus()
        if self._entry.get_text():
            self._entry.select_region(0, -1)


class SystemCommandPaletteDialog(Gtk.Popover):
    """System-style command palette using Gtk.Popover for context-aware positioning."""

    def __init__(self, parent, commands, on_execute, placeholder):
        super().__init__()

        target = _get_popover_parent(parent)
        self.set_parent(target)
        self.set_has_arrow(False)
        self.set_autohide(True)
        _apply_popover_theme(self)

        self._commands = commands or []
        self._filtered_commands = list(self._commands)
        self._on_execute = on_execute
        self._selected_index = 0

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_size_request(550, 400)

        self._entry = ZenSearchEntry(placeholder=placeholder)
        self._entry.connect("search-changed", self._on_search_changed)
        self._entry.connect("activate", self._on_activate)
        content.append(self._entry)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-activated", self._on_row_activated)

        scrolled.set_child(self._listbox)
        content.append(scrolled)
        self.set_child(content)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        self.connect("closed", self._on_closed)

        self._update_results()

    def _on_closed(self, popover):
        if self.get_parent():
            self.unparent()

    def _on_search_changed(self, entry):
        self._filter_commands(entry.get_text())

    def _filter_commands(self, query):
        query = query.lower().strip()
        if not query:
            self._filtered_commands = list(self._commands)
        else:
            scored = []
            for cmd in self._commands:
                name = cmd.get("name", "").lower()
                label = cmd.get("label", "").lower()
                score = 0
                if query in name:
                    score += 100
                if query in label:
                    score += 50
                q_idx = 0
                for c in name + " " + label:
                    if q_idx < len(query) and c == query[q_idx]:
                        score += 10
                        q_idx += 1
                if q_idx == len(query) and score > 0:
                    scored.append((score, cmd))
                elif score >= 50:
                    scored.append((score, cmd))
            scored.sort(key=lambda x: -x[0])
            self._filtered_commands = [cmd for _, cmd in scored]
        self._update_results()

    def _update_results(self):
        while True:
            row = self._listbox.get_first_child()
            if row:
                self._listbox.remove(row)
            else:
                break

        for i, cmd in enumerate(self._filtered_commands[:20]):
            row = self._create_command_row(cmd, i)
            self._listbox.append(row)

        self._selected_index = 0
        first_row = self._listbox.get_first_child()
        if first_row:
            self._listbox.select_row(first_row)

    def _create_command_row(self, cmd, index):
        row = Gtk.ListBoxRow()
        row._command = cmd

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        if cmd.get("icon"):
            icon_label = Gtk.Label(label=cmd["icon"])
            box.append(icon_label)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        label = Gtk.Label(label=cmd.get("label", cmd.get("name", "")))
        label.set_halign(Gtk.Align.START)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        text_box.append(label)

        if cmd.get("hint"):
            hint = Gtk.Label(label=cmd["hint"])
            hint.set_halign(Gtk.Align.START)
            hint.add_css_class("dim-label")
            hint.set_ellipsize(Pango.EllipsizeMode.END)
            text_box.append(hint)

        box.append(text_box)

        if cmd.get("keybind"):
            keybind = Gtk.Label(label=cmd["keybind"])
            keybind.add_css_class("dim-label")
            box.append(keybind)

        row.set_child(box)
        return row

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.popdown()
            return True
        elif keyval == Gdk.KEY_Down:
            self._move_selection(1)
            return True
        elif keyval == Gdk.KEY_Up:
            self._move_selection(-1)
            return True
        return False

    def _move_selection(self, delta):
        rows = list(self._listbox)
        if not rows:
            return
        new_idx = (self._selected_index + delta) % len(rows)
        self._selected_index = new_idx
        self._listbox.select_row(rows[new_idx])

    def _on_activate(self, entry):
        self._execute_selected()

    def _on_row_activated(self, listbox, row):
        if hasattr(row, "_command"):
            self._execute_command(row._command)

    def _execute_selected(self):
        row = self._listbox.get_selected_row()
        if row and hasattr(row, "_command"):
            self._execute_command(row._command)

    def _execute_command(self, cmd):
        action = cmd.get("action")
        callback = self._on_execute
        self.popdown()
        if action:
            action()
        if callback:
            callback(cmd)

    def present(self):
        self.popup()
        self._entry.grab_focus()


# Re-export moved classes for backward compatibility
from popups.path_breadcrumb import SystemContextMenu  # noqa: E402, F401
from popups.recent_items import SystemSelectionDialog  # noqa: E402, F401
