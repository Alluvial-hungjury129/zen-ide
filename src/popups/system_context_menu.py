"""
Path breadcrumb / context menu widget for system-style popover.

Extracted from system_dialogs.py — contains SystemContextMenu.
"""

from gi.repository import Gdk, Gtk

from popups.system_command_palette_dialog import _apply_popover_theme, _get_popover_parent


class SystemContextMenu(Gtk.Popover):
    """System-style context menu using Gtk.Popover for context-aware positioning."""

    def __init__(self, parent, items, on_select, x=None, y=None, source_widget=None, title=""):
        super().__init__()

        target = source_widget or _get_popover_parent(parent)
        self.set_parent(target)
        self.set_has_arrow(False)
        self.set_autohide(True)

        if x is not None and y is not None:
            rect = Gdk.Rectangle()
            rect.x = int(x)
            rect.y = int(y)
            rect.width = 1
            rect.height = 1
            self.set_pointing_to(rect)

        self._items = items
        self._on_select = on_select
        self._selected_idx = 0

        for i, item in enumerate(items):
            if item.get("label") != "---" and item.get("enabled", True):
                self._selected_idx = i
                break

        self._apply_popover_css()

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_start(4)
        content.set_margin_end(4)
        content.set_margin_top(4)
        content.set_margin_bottom(4)

        if title:
            title_label = Gtk.Label(label=title)
            title_label.add_css_class("dim-label")
            title_label.set_margin_top(20)
            title_label.set_margin_bottom(4)
            content.append(title_label)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)

        for i, item in enumerate(self._items):
            if item.get("label") == "---":
                sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
                sep.set_margin_top(4)
                sep.set_margin_bottom(4)
                row = Gtk.ListBoxRow()
                row.set_selectable(False)
                row.set_activatable(False)
                row.set_child(sep)
            else:
                row = self._create_menu_row(item, i)
            self._listbox.append(row)

        self._listbox.connect("row-activated", self._on_row_activated)
        content.append(self._listbox)
        self.set_child(content)

        # Select initial item
        row = self._listbox.get_row_at_index(self._selected_idx)
        if row and row.get_sensitive() and row.get_selectable():
            self._listbox.select_row(row)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        self.connect("closed", self._on_closed)

    def _apply_popover_css(self):
        """Apply themed border CSS to the popover."""
        _apply_popover_theme(self)

    def _on_closed(self, popover):
        if self.get_parent():
            self.unparent()

    def _create_menu_row(self, item, idx):
        row = Gtk.ListBoxRow()
        enabled = item.get("enabled", True)
        row.set_sensitive(enabled)
        row.set_activatable(enabled)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        if item.get("icon"):
            icon_label = Gtk.Label(label=item["icon"])
            box.append(icon_label)

        label = Gtk.Label(label=item["label"])
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        if not enabled:
            label.set_opacity(0.5)
        box.append(label)

        row.set_child(box)
        return row

    def _on_row_activated(self, listbox, row):
        idx = row.get_index()
        if 0 <= idx < len(self._items):
            item = self._items[idx]
            if item.get("label") != "---" and item.get("enabled", True):
                action = item.get("action")
                self.popdown()
                if self._on_select and action:
                    self._on_select(action)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.popdown()
            return True
        if keyval == Gdk.KEY_Down:
            self._move_selection(1)
            return True
        if keyval == Gdk.KEY_Up:
            self._move_selection(-1)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            row = self._listbox.get_row_at_index(self._selected_idx)
            if row and row.get_sensitive():
                self._on_row_activated(self._listbox, row)
            return True
        return False

    def _move_selection(self, delta):
        new_idx = self._selected_idx
        attempts = 0
        while attempts < len(self._items):
            new_idx = (new_idx + delta) % len(self._items)
            item = self._items[new_idx]
            if item.get("label") != "---" and item.get("enabled", True):
                self._selected_idx = new_idx
                row = self._listbox.get_row_at_index(new_idx)
                if row:
                    self._listbox.select_row(row)
                break
            attempts += 1

    def present(self):
        self.popup()
