"""
Recent items / selection dialog for system-style popover.

Extracted from system_dialogs.py — contains SystemSelectionDialog.
"""

from gi.repository import Gdk, Gtk, Pango

from popups.system_dialogs import _apply_popover_theme, _get_popover_parent


class SystemSelectionDialog(Gtk.Popover):
    """System-style selection dialog using Gtk.Popover for context-aware positioning."""

    def __init__(
        self, parent, title, items, on_select, show_icons=True, max_visible=10, on_selection_change=None, on_cancel=None
    ):
        super().__init__()

        target = _get_popover_parent(parent)
        self.set_parent(target)
        self.set_has_arrow(False)
        self.set_autohide(True)
        _apply_popover_theme(self)

        self._items = items or []
        self._on_select = on_select
        self._on_selection_change = on_selection_change
        self._on_cancel = on_cancel
        self._show_icons = show_icons
        self._selected = False
        self._selected_index = 0

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_size_request(400, -1)

        if title:
            title_label = Gtk.Label(label=title)
            title_label.set_halign(Gtk.Align.START)
            title_label.add_css_class("title-3")
            content.append(title_label)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        row_height = 32
        scrolled.set_min_content_height(min(len(self._items), max_visible) * row_height)
        scrolled.set_max_content_height(max_visible * row_height)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-activated", self._on_row_activated)

        for i, item in enumerate(self._items):
            row = self._create_item_row(item, i)
            self._listbox.append(row)

        if self._items:
            for i, item in enumerate(self._items):
                item_data = {"label": item} if isinstance(item, str) else item
                if not item_data.get("disabled", False):
                    self._selected_index = i
                    row = self._listbox.get_row_at_index(i)
                    if row:
                        self._listbox.select_row(row)
                    break

        scrolled.set_child(self._listbox)
        content.append(scrolled)
        self.set_child(content)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        self.connect("closed", self._on_closed)

        self._listbox.connect("row-selected", self._on_row_selected)

    def _on_closed(self, popover):
        if not self._selected and self._on_cancel:
            self._on_cancel()
        if self.get_parent():
            self.unparent()

    def _on_row_selected(self, listbox, row):
        """Handle row selection change for live preview."""
        if row and hasattr(row, "_item") and self._on_selection_change:
            item = row._item
            if isinstance(item, dict) and item.get("disabled"):
                return
            self._on_selection_change(item)

    def _create_item_row(self, item, index):
        row = Gtk.ListBoxRow()
        row._item = item

        item_data = {"label": item} if isinstance(item, str) else item

        if item_data.get("disabled", False):
            row.set_activatable(False)
            row.set_selectable(False)
            label = Gtk.Label(label=item_data.get("label", ""))
            label.set_halign(Gtk.Align.CENTER)
            label.add_css_class("dim-label")
            label.set_margin_top(6)
            label.set_margin_bottom(2)
            row.set_child(label)
            return row

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(2)
        box.set_margin_bottom(2)

        if self._show_icons and item_data.get("icon"):
            icon_label = Gtk.Label(label=item_data["icon"])
            box.append(icon_label)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        label = Gtk.Label(label=item_data.get("label", str(item)))
        label.set_halign(Gtk.Align.START)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        text_box.append(label)

        if item_data.get("hint"):
            hint = Gtk.Label(label=item_data["hint"])
            hint.set_halign(Gtk.Align.START)
            hint.add_css_class("dim-label")
            hint.set_ellipsize(Pango.EllipsizeMode.END)
            text_box.append(hint)

        box.append(text_box)
        row.set_child(box)
        return row

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.popdown()
            return True
        return False

    def _on_row_activated(self, listbox, row):
        if hasattr(row, "_item"):
            item = row._item
            if isinstance(item, dict) and item.get("disabled"):
                return
            self._selected = True
            callback = self._on_select
            self.popdown()
            if callback:
                callback(item)

    def present(self):
        self.popup()
        row = self._listbox.get_row_at_index(self._selected_index)
        if row:
            row.grab_focus()
