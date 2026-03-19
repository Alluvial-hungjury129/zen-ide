"""
Copilot provider selection popup for Zen IDE.
"""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup


class CopilotPopup(NvimPopup):
    """Nvim-style popup for Copilot provider selection."""

    def __init__(self, parent: Gtk.Window, on_confirm: callable = None):
        self._on_confirm = on_confirm
        super().__init__(parent, title="Copilot", width=350, height=-1)

    def _create_content(self):
        """Create the popup content."""
        # Message
        message = self._create_message_label("Switch to GitHub Copilot as your AI provider?")
        self._content_box.append(message)

        # Hint about Copilot features
        hint = Gtk.Label(label="Uses your GitHub Copilot subscription")
        hint.add_css_class("nvim-popup-hint")
        hint.set_halign(Gtk.Align.START)
        hint.set_margin_top(8)
        self._content_box.append(hint)

        # Button row
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(12)

        cancel_btn = self._create_button("Cancel")
        cancel_btn.connect("clicked", lambda b: self.close())
        button_box.append(cancel_btn)

        confirm_btn = self._create_button("Switch to Copilot", primary=True)
        confirm_btn.connect("clicked", self._on_confirm_clicked)
        button_box.append(confirm_btn)

        self._content_box.append(button_box)

        # Keybind hints
        hints = self._create_hint_bar(
            [
                ("Enter", "confirm"),
                ("Esc", "cancel"),
            ]
        )
        self._content_box.append(hints)

    def _on_confirm_clicked(self, button):
        """Handle confirm button click."""
        self.close()
        if self._on_confirm:
            self._on_confirm()

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle key press events."""
        if keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter:
            self._on_confirm_clicked(None)
            return True
        return super()._on_key_pressed(controller, keyval, keycode, state)
