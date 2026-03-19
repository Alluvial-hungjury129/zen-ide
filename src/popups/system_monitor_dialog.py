"""
System Monitor Dialog for Zen IDE.
"""

from typing import Optional

from gi.repository import Gdk, Gtk

from shared.system_monitor import SystemMonitorPanel
from themes import get_theme


class SystemMonitorDialog(Gtk.Window):
    """Standalone dialog for System Monitor."""

    def __init__(self, parent: Optional[Gtk.Window] = None):
        super().__init__(
            title="System Monitor - Zen IDE",
            default_width=450,
            default_height=600,
        )

        if parent:
            self.set_transient_for(parent)
            self.set_modal(True)

        self._panel = SystemMonitorPanel(on_close=self.close)
        self.set_child(self._panel)

        # Apply theme
        theme = get_theme()
        css_provider = Gtk.CssProvider()
        css = f"""
            window {{
                background-color: {theme.panel_bg};
            }}
        """
        css_provider.load_from_data(css.encode())

        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )

        # Start monitoring when window is shown
        self.connect("show", lambda w: self._panel.show_panel())
        self.connect("close-request", self._on_close_request)

        # Setup keyboard handler for Escape to close
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle key press - Escape to close."""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_close_request(self, window):
        """Clean up when closing."""
        self._panel.hide_panel()
        return False


def show_system_monitor(parent: Optional[Gtk.Window] = None) -> SystemMonitorDialog:
    """Show the system monitor dialog.

    Args:
        parent: Parent window.

    Returns:
        The dialog instance.
    """
    dialog = SystemMonitorDialog(parent)
    dialog.present()
    return dialog
