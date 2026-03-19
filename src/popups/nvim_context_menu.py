"""
Neovim-style context menu popup for Zen IDE.
"""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup


class NvimContextMenu(NvimPopup):
    """
    Neovim-style context menu popup.

    A list-based menu for right-click context menus, with vim-style navigation.

    Usage:
        items = [
            {"label": "Close Tab", "action": "close", "enabled": True},
            {"label": "Stop AI", "action": "stop", "enabled": is_processing},
            {"label": "---"},  # separator
            {"label": "New Tab", "action": "new"},
        ]
        menu = NvimContextMenu(parent, items, on_select=handle_action)
        menu.present()
    """

    def __init__(
        self,
        parent: Gtk.Window,
        items: list[dict],
        on_select: callable = None,
        x: int = None,
        y: int = None,
        title: str = "",
        anchor_widget: Gtk.Widget = None,
    ):
        """
        Initialize the context menu.

        Args:
            parent: Parent window
            items: List of menu items. Each item is a dict with:
                   - label: Display text
                   - action: Action identifier (returned on select)
                   - enabled: Whether item is clickable (default True)
                   - icon: Optional icon character
                   Use {"label": "---"} for separator
            on_select: Callback when item is selected, receives action string
            x: Optional x position (relative to anchor_widget)
            y: Optional y position (relative to anchor_widget)
            title: Optional title for the menu
            anchor_widget: Widget where click originated (for positioning)
        """
        self._items = items
        self._on_select = on_select
        self._selected_idx = 0
        self._listbox = None

        # Find first enabled item
        for i, item in enumerate(items):
            if item.get("label") != "---" and item.get("enabled", True):
                self._selected_idx = i
                break

        # Create anchor_rect from x, y if both are provided
        anchor_rect = None
        if anchor_widget is not None and x is not None and y is not None:
            anchor_rect = Gdk.Rectangle()
            anchor_rect.x = int(x)
            anchor_rect.y = int(y)
            anchor_rect.width = 1
            anchor_rect.height = 1
        super().__init__(
            parent,
            title=title,
            width=220,
            height=-1,
            anchor_widget=anchor_widget,
            anchor_rect=anchor_rect,
        )

    def _create_content(self):
        """Create the menu content."""
        self._content_box.set_margin_start(4)
        self._content_box.set_margin_end(4)
        self._content_box.set_margin_top(24 if self._title else 4)
        self._content_box.set_margin_bottom(4)

        self._listbox = Gtk.ListBox()
        self._listbox.add_css_class("nvim-popup-list")
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)

        for i, item in enumerate(self._items):
            if item.get("label") == "---":
                # Separator
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
        self._listbox.connect("row-selected", self._on_row_selected)
        self._content_box.append(self._listbox)

        # Select initial item
        self._update_selection()

    def _create_menu_row(self, item: dict, idx: int) -> Gtk.ListBoxRow:
        """Create a menu item row."""
        row = Gtk.ListBoxRow()
        row.add_css_class("nvim-popup-list-item")
        enabled = item.get("enabled", True)
        row.set_sensitive(enabled)
        row.set_activatable(enabled)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        # Optional icon
        if item.get("icon"):
            icon_label = Gtk.Label(label=item["icon"])
            icon_label.add_css_class("nvim-popup-list-item-icon")
            box.append(icon_label)

        # Label
        label = Gtk.Label(label=item["label"])
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.add_css_class("nvim-popup-list-item-text")
        if not enabled:
            label.set_opacity(0.5)
        box.append(label)

        row.set_child(box)
        return row

    def _update_selection(self):
        """Update the visual selection."""
        if self._listbox:
            row = self._listbox.get_row_at_index(self._selected_idx)
            if row and row.get_sensitive() and row.get_selectable():
                self._listbox.select_row(row)

    def _on_row_activated(self, listbox, row):
        """Handle row activation."""
        idx = row.get_index()
        if idx >= 0 and idx < len(self._items):
            item = self._items[idx]
            if item.get("label") != "---" and item.get("enabled", True):
                action = item.get("action")
                self._result = action
                self.close()
                if self._on_select and action:
                    self._on_select(action)

    def _on_row_selected(self, listbox, row):
        """Handle row selection - skip separators and disabled items."""
        if row is None:
            return
        idx = row.get_index()
        if idx >= 0 and idx < len(self._items):
            item = self._items[idx]
            # If separator or disabled item clicked, unselect and restore valid selection
            if item.get("label") == "---" or not item.get("enabled", True):
                listbox.unselect_row(row)
                self._update_selection()
            else:
                self._selected_idx = idx

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle keyboard navigation."""
        if keyval == Gdk.KEY_Escape:
            self._result = None
            self.close()
            return True

        if keyval in (Gdk.KEY_j, Gdk.KEY_Down):
            self._move_selection(1)
            return True

        if keyval in (Gdk.KEY_k, Gdk.KEY_Up):
            self._move_selection(-1)
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            row = self._listbox.get_row_at_index(self._selected_idx)
            if row and row.get_sensitive():
                self._on_row_activated(self._listbox, row)
            return True

        return False

    def _move_selection(self, delta: int):
        """Move selection by delta, skipping separators and disabled items."""
        new_idx = self._selected_idx
        attempts = 0

        while attempts < len(self._items):
            new_idx = (new_idx + delta) % len(self._items)
            item = self._items[new_idx]
            if item.get("label") != "---" and item.get("enabled", True):
                self._selected_idx = new_idx
                self._update_selection()
                break
            attempts += 1

    def present(self):
        """Show the menu at the specified position or centered."""
        self.set_default_size(self._width, -1)
        super().present()


def show_context_menu(
    parent: Gtk.Window,
    items: list[dict],
    on_select: callable,
    x: int = None,
    y: int = None,
    source_widget: Gtk.Widget = None,
    title: str = "",
):
    """
    Show a context menu.

    Args:
        parent: Parent window
        items: Menu items (see NvimContextMenu for format)
        on_select: Callback when item selected
        x: Optional x position
        y: Optional y position
        source_widget: Optional widget where the click originated (for positioning)
        title: Optional title for the menu
    """
    from popups.system_dialogs import is_nvim_mode

    nvim = is_nvim_mode()
    if not nvim:
        from popups.system_dialogs import SystemContextMenu

        menu = SystemContextMenu(parent, items, on_select, x, y, source_widget, title=title)
        menu.present()
        return menu
    menu = NvimContextMenu(parent, items, on_select, x, y, title=title, anchor_widget=source_widget)
    menu.present()
    return menu
