"""
Keyboard Shortcuts popup for Zen IDE.
"""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup
from shared.settings.keybindings import KeyBindings


class KeyboardShortcutsPopup(NvimPopup):
    """
    Vim-style popup showing keyboard shortcuts.

    Displays categorized shortcuts in a scrollable list with vim-style navigation.
    Press Escape or q to close.
    """

    def __init__(self, parent: Gtk.Window):
        super().__init__(parent, title="Keyboard Shortcuts", width=450, height=500)

    _SCROLL_STEP = 40

    def _create_content(self):
        """Create the shortcuts list content."""
        shortcuts_data = KeyBindings.get_shortcut_categories()

        # Scrolled window for shortcuts
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scrolled.set_min_content_height(350)
        self._scrolled.set_max_content_height(450)
        self._scrolled.set_vexpand(True)

        # Content box inside scrolled window
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        for category, shortcuts in shortcuts_data:
            # Category header
            header = Gtk.Label(label=category)
            header.set_halign(Gtk.Align.START)
            header.set_margin_top(12)
            header.set_margin_bottom(4)
            header.add_css_class("nvim-popup-title")
            content.append(header)

            # Shortcuts in this category
            for name, key in shortcuts:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row.set_margin_start(8)
                row.set_margin_end(8)
                row.set_margin_top(4)
                row.set_margin_bottom(4)

                name_label = Gtk.Label(label=name)
                name_label.set_halign(Gtk.Align.START)
                name_label.set_hexpand(True)
                name_label.add_css_class("nvim-popup-message")
                row.append(name_label)

                key_label = Gtk.Label(label=key)
                key_label.set_halign(Gtk.Align.END)
                key_label.add_css_class("nvim-popup-keybind")
                row.append(key_label)

                content.append(row)

        self._scrolled.set_child(content)
        self._content_box.append(self._scrolled)

        # Hint bar at bottom
        hint_bar = self._create_hint_bar(
            [
                ("Esc", "close"),
                ("q", "close"),
                ("j/k", "scroll"),
            ]
        )
        self._content_box.append(hint_bar)

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle keyboard - j/k scroll, q closes."""
        if keyval == Gdk.KEY_j:
            self._scroll(self._SCROLL_STEP)
            return True
        if keyval == Gdk.KEY_k:
            self._scroll(-self._SCROLL_STEP)
            return True
        if keyval == Gdk.KEY_q:
            self._result = None
            self.close()
            return True
        return super()._on_key_pressed(controller, keyval, keycode, state)

    def _scroll(self, delta: int):
        """Scroll the shortcuts list by delta pixels."""
        adj = self._scrolled.get_vadjustment()
        new_value = adj.get_value() + delta
        adj.set_value(max(adj.get_lower(), min(new_value, adj.get_upper() - adj.get_page_size())))


def show_keyboard_shortcuts(parent: Gtk.Window):
    """Show the keyboard shortcuts popup."""
    popup = KeyboardShortcutsPopup(parent)
    popup.present()
    return popup
