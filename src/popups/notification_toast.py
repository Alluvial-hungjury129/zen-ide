"""
Neovim-style notification toast for Zen IDE.
"""

from gi.repository import GLib, Gtk, Pango

from themes import get_theme


class NotificationToast(Gtk.Window):
    """Neovim-style notification toast (non-modal)."""

    def __init__(
        self,
        parent: Gtk.Window,
        message: str,
        level: str = "info",  # info, success, warning, error
        timeout_ms: int = 3000,
    ):
        super().__init__()
        self.set_transient_for(parent)
        self.set_modal(False)
        self.set_decorated(False)
        self.set_resizable(False)

        self._message = message
        self._level = level
        self._timeout_ms = timeout_ms

        self._create_ui()
        self._apply_styles()

        # Auto-close after timeout
        if timeout_ms > 0:
            GLib.timeout_add(timeout_ms, self._on_timeout)

    def _create_ui(self):
        from icons import Icons, apply_icon_font

        # Icon based on level
        icons = {
            "info": Icons.INFO,
            "success": Icons.SUCCESS,
            "warning": Icons.WARNING,
            "error": Icons.ERROR,
        }

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        # Icon
        icon = Gtk.Label(label=icons.get(self._level, Icons.INFO))
        icon.add_css_class(f"toast-icon-{self._level}")
        apply_icon_font(icon)
        box.append(icon)

        # Message
        msg = Gtk.Label(label=self._message)
        msg.add_css_class("toast-message")
        msg.set_ellipsize(Pango.EllipsizeMode.END)
        msg.set_max_width_chars(60)
        box.append(msg)

        self.set_child(box)

    def _apply_styles(self):
        """Apply toast styles."""
        theme = get_theme()

        level_colors = {
            "info": theme.accent_color,
            "success": theme.git_added,
            "warning": theme.git_modified,
            "error": theme.git_deleted,
        }
        border_color = level_colors.get(self._level, theme.accent_color)

        css_provider = Gtk.CssProvider()
        css = f"""
            window {{
                background-color: {theme.panel_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            .toast-message {{
                color: {theme.fg_color};
            }}
            .toast-icon-info {{ color: {theme.accent_color}; }}
            .toast-icon-success {{ color: {theme.git_added}; }}
            .toast-icon-warning {{ color: {theme.git_modified}; }}
            .toast-icon-error {{ color: {theme.git_deleted}; }}
        """
        css_provider.load_from_data(css.encode())

        self.get_style_context().add_provider(
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _on_timeout(self) -> bool:
        """Handle timeout - close the toast."""
        self.close()
        return False

    def present(self):
        """Show the toast at bottom-right of parent."""
        self.set_default_size(-1, -1)
        super().present()


def show_toast(
    parent: Gtk.Window,
    message: str,
    level: str = "info",
    timeout_ms: int = 3000,
) -> NotificationToast:
    """Show a notification toast and return it."""
    toast = NotificationToast(parent, message, level, timeout_ms)
    toast.present()
    return toast
