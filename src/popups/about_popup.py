"""
About popup for Zen IDE.
"""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup


class AboutPopup(NvimPopup):
    """
    Vim-style About dialog popup.

    Shows application info in a clean, minimal popup.
    Press Escape or q to close.
    """

    def __init__(self, parent: Gtk.Window):
        super().__init__(parent, title="About", width=350, height=-1)

    def _create_content(self):
        """Create the about content."""
        # App name
        name_label = Gtk.Label(label="[Zen IDE]")
        name_label.add_css_class("nvim-popup-title")
        name_label.set_margin_bottom(4)
        self._content_box.append(name_label)

        # Version
        version_label = Gtk.Label(label="Version 1.0.0")
        version_label.add_css_class("nvim-popup-hint")
        version_label.set_margin_bottom(16)
        self._content_box.append(version_label)

        # Description
        desc_label = Gtk.Label(label="A minimalist opinionated IDE for general purpose code development")
        desc_label.add_css_class("nvim-popup-message")
        desc_label.set_wrap(True)
        desc_label.set_margin_bottom(16)
        self._content_box.append(desc_label)

        # Info rows
        info_items = [
            ("Framework", "Python+GTK4"),
            ("License", "MIT"),
            ("Contributors", "Zen IDE Team"),
        ]

        for label_text, value_text in info_items:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_margin_top(2)
            row.set_margin_bottom(2)

            label = Gtk.Label(label=f"{label_text}:")
            label.set_halign(Gtk.Align.START)
            label.add_css_class("nvim-popup-hint")
            label.set_width_chars(12)
            row.append(label)

            value = Gtk.Label(label=value_text)
            value.set_halign(Gtk.Align.START)
            value.add_css_class("nvim-popup-message")
            row.append(value)

            self._content_box.append(row)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_margin_top(16)
        self._content_box.append(spacer)

        # Hint bar
        hint_bar = self._create_hint_bar(
            [
                ("Esc", "close"),
                ("q", "close"),
            ]
        )
        self._content_box.append(hint_bar)

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle keyboard - q also closes."""
        if keyval == Gdk.KEY_q:
            self._result = None
            self.close()
            return True
        return super()._on_key_pressed(controller, keyval, keycode, state)


def show_about(parent: Gtk.Window):
    """Show the about popup."""
    popup = AboutPopup(parent)
    popup.present()
    return popup
