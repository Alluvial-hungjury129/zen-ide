"""
Neovim-style selection dialog for Zen IDE.
"""

from gi.repository import Gdk, GLib, Gtk, Pango

from popups.nvim_popup import NvimPopup


class SelectionDialog(NvimPopup):
    """Neovim-style selection menu with j/k navigation."""

    def __init__(
        self,
        parent: Gtk.Window,
        title: str = "Select",
        items: list = None,
        on_select=None,
        show_icons: bool = True,
        max_visible: int = 10,
        on_selection_change=None,
        on_cancel=None,
    ):
        """
        Args:
            parent: Parent window
            title: Dialog title
            items: List of items. Each item can be:
                   - str: Just the label
                   - dict: {"label": str, "hint": str, "icon": str, "value": any}
            on_select: Callback when item is selected, receives the item
            show_icons: Whether to show icons
            max_visible: Maximum number of visible items before scrolling
            on_selection_change: Callback when highlighted item changes (for live preview)
            on_cancel: Callback when dialog is closed without selection
        """
        self._items = items or []
        self._on_select = on_select
        self._on_selection_change = on_selection_change
        self._on_cancel = on_cancel
        self._show_icons = show_icons
        self._max_visible = max_visible
        self._selected_index = 0
        self._in_preview = False
        super().__init__(parent, title, width=500)

    def _create_content(self):
        """Create the selection dialog UI."""
        # Scrolled window for items
        row_height = 32
        scrolled, self._listbox = self._create_scrolled_listbox(
            min_height=min(len(self._items), self._max_visible) * row_height,
            max_height=self._max_visible * row_height,
        )
        self._listbox.connect("row-activated", self._on_row_activated)
        self._listbox.connect("row-selected", self._on_row_selected)
        self._content_box.append(scrolled)

        # Add items
        for i, item in enumerate(self._items):
            row = self._create_item_row(item, i)
            self._listbox.append(row)

        # Select first non-disabled item
        if self._items:
            for i, item in enumerate(self._items):
                if not self._is_disabled(i):
                    self._selected_index = i
                    row = self._listbox.get_row_at_index(i)
                    if row:
                        self._listbox.select_row(row)
                    break

        # Hint
        hint_label = Gtk.Label(label="j/k or ↑↓ to navigate • Enter to select • Esc to close")
        hint_label.add_css_class("nvim-popup-hint")
        hint_label.set_halign(Gtk.Align.CENTER)
        hint_label.set_margin_top(8)
        self._content_box.append(hint_label)

    def _is_disabled(self, index: int) -> bool:
        """Check if an item at index is disabled (separator)."""
        item = self._items[index]
        return isinstance(item, dict) and item.get("disabled", False)

    def _create_item_row(self, item, index: int) -> Gtk.ListBoxRow:
        """Create a row for an item."""
        row = Gtk.ListBoxRow()
        row._item = item
        row._index = index

        # Normalize item to dict
        if isinstance(item, str):
            item_data = {"label": item}
        else:
            item_data = item

        disabled = item_data.get("disabled", False)

        if disabled:
            row.set_activatable(False)
            row.set_selectable(False)
            row.add_css_class("nvim-popup-separator")
            label = Gtk.Label(label=item_data.get("label", ""))
            label.set_halign(Gtk.Align.CENTER)
            label.add_css_class("nvim-popup-list-item-hint")
            label.set_margin_top(6)
            label.set_margin_bottom(2)
            row.set_child(label)
            return row

        row.add_css_class("nvim-popup-list-item")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(2)
        box.set_margin_bottom(2)

        # Icon
        if self._show_icons and item_data.get("icon"):
            icon_label = Gtk.Label(label=item_data["icon"])
            icon_label.add_css_class("nvim-popup-list-item-icon")
            box.append(icon_label)

        # Label and hint container
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        # Label
        label = Gtk.Label(label=item_data.get("label", str(item)))
        label.set_halign(Gtk.Align.START)
        label.add_css_class("nvim-popup-list-item-text")
        label.set_ellipsize(Pango.EllipsizeMode.END)
        text_box.append(label)

        # Hint (optional)
        if item_data.get("hint"):
            hint = Gtk.Label(label=item_data["hint"])
            hint.set_halign(Gtk.Align.START)
            hint.add_css_class("nvim-popup-list-item-hint")
            hint.set_ellipsize(Pango.EllipsizeMode.END)
            text_box.append(hint)

        box.append(text_box)

        # Keyboard shortcut hint (optional, 1-9)
        if index < 9 and not disabled:
            shortcut = Gtk.Label(label=str(index + 1))
            shortcut.add_css_class("nvim-popup-keybind")
            box.append(shortcut)

        row.set_child(box)
        return row

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle key press."""
        if keyval == Gdk.KEY_Escape:
            self._result = None
            self.close()
            return True
        elif keyval == Gdk.KEY_Return:
            self._select_current()
            return True
        elif keyval in (Gdk.KEY_j, Gdk.KEY_Down):
            self._move_selection(1)
            return True
        elif keyval in (Gdk.KEY_k, Gdk.KEY_Up):
            self._move_selection(-1)
            return True
        elif keyval == Gdk.KEY_g:
            # Go to first
            self._move_to(0)
            return True
        elif keyval == Gdk.KEY_G:
            # Go to last
            self._move_to(len(self._items) - 1)
            return True
        elif Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
            # Quick select with number keys
            idx = keyval - Gdk.KEY_1
            if idx < len(self._items):
                self._move_to(idx)
                self._select_current()
            return True
        return False

    def _move_selection(self, delta: int):
        """Move selection by delta, skipping disabled items."""
        n = len(self._items)
        new_idx = self._selected_index
        for _ in range(n):
            new_idx = (new_idx + delta) % n
            if not self._is_disabled(new_idx):
                break
        self._move_to(new_idx)

    def _move_to(self, idx: int):
        """Move selection to specific index, skipping disabled items."""
        if 0 <= idx < len(self._items) and not self._is_disabled(idx):
            self._selected_index = idx
            row = self._listbox.get_row_at_index(idx)
            if row:
                self._listbox.select_row(row)
                row.grab_focus()
                if self._on_selection_change and hasattr(row, "_item"):
                    self._in_preview = True
                    self._on_selection_change(row._item)
                    GLib.idle_add(self._end_preview, idx)

    def _on_row_selected(self, listbox, row):
        """Handle GTK native selection change (e.g. arrow keys handled by listbox)."""
        if row and hasattr(row, "_index") and row._index != self._selected_index:
            self._selected_index = row._index
            if self._on_selection_change and hasattr(row, "_item"):
                self._in_preview = True
                self._on_selection_change(row._item)
                GLib.idle_add(self._end_preview, row._index)

    def _end_preview(self, idx):
        """Re-grab focus after preview callback to counteract CSS-induced focus loss."""
        self._in_preview = False
        row = self._listbox.get_row_at_index(idx)
        if row and not self._closing:
            row.grab_focus()
        return GLib.SOURCE_REMOVE

    def _on_focus_leave(self, controller):
        """Suppress focus-leave close while a preview callback is in progress."""
        if self._in_preview:
            return
        super()._on_focus_leave(controller)

    def _select_current(self):
        """Select the current item."""
        row = self._listbox.get_selected_row()
        if row and hasattr(row, "_item"):
            item = row._item
            if isinstance(item, dict) and item.get("disabled"):
                return
            self._result = item
            callback = self._on_select
            self.close()
            if callback:
                callback(item)

    def _on_row_activated(self, listbox, row):
        """Handle row activation (click/enter)."""
        if hasattr(row, "_item"):
            self._result = row._item
            callback = self._on_select
            item = row._item
            self.close()
            if callback:
                callback(item)

    def close(self):
        """Close the dialog, firing on_cancel if no selection was made."""
        if not self._closing and self._result is None and self._on_cancel:
            self._on_cancel()
        super().close()

    def present(self):
        """Show the dialog."""
        super().present()
        # Focus the first non-disabled row
        row = self._listbox.get_row_at_index(self._selected_index)
        if row:
            row.grab_focus()


def show_selection(
    parent: Gtk.Window,
    title: str = "Select",
    items: list = None,
    on_select=None,
    show_icons: bool = True,
    on_selection_change=None,
    on_cancel=None,
):
    """Show a selection dialog and return it."""
    from popups.nvim_popup import show_popup
    from popups.system_command_palette_dialog import SystemSelectionDialog

    return show_popup(
        SelectionDialog,
        SystemSelectionDialog,
        parent,
        title,
        items,
        on_select,
        show_icons,
        on_selection_change=on_selection_change,
        on_cancel=on_cancel,
    )
