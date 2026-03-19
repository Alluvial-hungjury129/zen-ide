"""ZenButton — consistent button widget for the entire IDE.

Provides a uniform button with:
- Fixed height (ZEN_BUTTON_HEIGHT)
- Dynamic width
- Consistent font from editor settings
- Icon-only, text-only, or icon+text modes
- Toggle support
- Theme integration (flat, primary, danger variants)

Usage::

    from shared.ui import ZenButton

    # Icon-only button
    btn = ZenButton(icon=Icons.TRASH, tooltip="Clear")
    btn.connect("clicked", on_clear)

    # Text button
    btn = ZenButton(label="Replace All")

    # Icon + text button
    btn = ZenButton(icon=Icons.PLUS, label="Note")

    # Primary action button
    btn = ZenButton(label="OK", variant="primary")

    # Toggle button
    btn = ZenButton(icon=Icons.TOOL_SELECT, tooltip="Select", toggle=True)
"""

from gi.repository import Gdk, Gtk

from constants import ZEN_BUTTON_HEIGHT, ZEN_BUTTON_ICON_SIZE
from fonts import get_font_settings, subscribe_font_change
from icons import get_icon_font_name
from themes import get_theme, subscribe_theme_change

# CSS class applied to every ZenButton instance
_CSS_CLASS = "zen-btn"
_CSS_CLASS_PRIMARY = "zen-btn-primary"
_CSS_CLASS_DANGER = "zen-btn-danger"

# Global CSS provider — shared by all instances, rebuilt on theme/font change
_global_provider: Gtk.CssProvider | None = None
_provider_installed = False


def _rebuild_global_css():
    """Rebuild and install the global ZenButton CSS."""
    global _global_provider, _provider_installed

    theme = get_theme()
    font_settings = get_font_settings("editor")
    font_family = font_settings["family"]
    font_size = font_settings.get("size", 13)
    btn_font_size = max(9, font_size - 2)
    nerd_font = get_icon_font_name()

    font_css = f'font-family: "{nerd_font}", "{font_family}", system-ui'

    css = f"""
        .{_CSS_CLASS} {{
            min-height: {ZEN_BUTTON_HEIGHT}px;
            padding: 0 8px;
            margin: 0;
            {font_css};
            font-size: {btn_font_size}px;
        }}
        .{_CSS_CLASS} > label {{
            {font_css};
            font-size: {btn_font_size}px;
        }}
        .{_CSS_CLASS} > box > label {{
            {font_css};
            font-size: {btn_font_size}px;
        }}

        /* icon-only: square button with no horizontal padding */
        .{_CSS_CLASS}.zen-btn-icon {{
            min-width: {ZEN_BUTTON_HEIGHT}px;
            padding: 0;
        }}
        .{_CSS_CLASS}.zen-btn-icon > label {{
            font-size: {ZEN_BUTTON_ICON_SIZE}px;
        }}

        /* Primary variant */
        .{_CSS_CLASS_PRIMARY} {{
            background-color: {theme.accent_color};
            color: #ffffff;
            border: none;
            font-weight: bold;
        }}
        .{_CSS_CLASS_PRIMARY}:hover {{
            opacity: 0.85;
        }}

        /* Danger variant */
        .{_CSS_CLASS_DANGER} {{
            background-color: {theme.git_deleted};
            color: #ffffff;
            border: none;
        }}
        .{_CSS_CLASS_DANGER}:hover {{
            opacity: 0.85;
        }}
    """

    if _global_provider is None:
        _global_provider = Gtk.CssProvider()

    _global_provider.load_from_data(css.encode())

    if not _provider_installed:
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(display, _global_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            _provider_installed = True


def _on_theme_change(_theme):
    _rebuild_global_css()


def _on_font_change(component, _settings):
    if component == "editor":
        _rebuild_global_css()


def _ensure_global_css():
    """Lazily install the global CSS on first ZenButton creation."""
    global _provider_installed
    if not _provider_installed:
        _rebuild_global_css()
        subscribe_theme_change(_on_theme_change)
        subscribe_font_change(_on_font_change)


class ZenButton(Gtk.ToggleButton):
    """Consistent button widget used across the IDE.

    Parameters
    ----------
    label:
        Text shown on the button.
    icon:
        Nerd Font icon character (shown left of label, or alone).
    tooltip:
        Tooltip text.
    toggle:
        If True, the button keeps toggle (active/inactive) state.
    variant:
        ``"flat"`` (default), ``"primary"``, or ``"danger"``.
    icon_size:
        Override icon font-size in px (default uses ZEN_BUTTON_ICON_SIZE).
    """

    def __init__(
        self,
        *,
        label: str | None = None,
        icon: str | None = None,
        tooltip: str | None = None,
        toggle: bool = False,
        variant: str = "flat",
        icon_size: int | None = None,
    ):
        Gtk.ToggleButton.__init__(self)
        self._is_toggle = toggle

        if not toggle:
            self.connect_after("clicked", ZenButton._prevent_toggle)

        _ensure_global_css()

        self.add_css_class("flat")
        self.add_css_class(_CSS_CLASS)
        self.set_valign(Gtk.Align.CENTER)

        if variant == "primary":
            self.add_css_class(_CSS_CLASS_PRIMARY)
        elif variant == "danger":
            self.add_css_class(_CSS_CLASS_DANGER)

        # Build child content
        if icon and label:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            icon_lbl = Gtk.Label(label=icon)
            icon_lbl.set_xalign(0.5)
            icon_lbl.set_yalign(0.5)
            if icon_size:
                self._apply_icon_size(icon_lbl, icon_size)
            box.append(icon_lbl)
            text_lbl = Gtk.Label(label=label)
            box.append(text_lbl)
            self.set_child(box)
        elif icon:
            self.add_css_class("zen-btn-icon")
            lbl = Gtk.Label(label=icon)
            lbl.set_xalign(0.5)
            lbl.set_yalign(0.5)
            if icon_size:
                self._apply_icon_size(lbl, icon_size)
            self.set_child(lbl)
        elif label:
            self.set_label(label)

        if tooltip:
            self.set_tooltip_text(tooltip)

    @staticmethod
    def _prevent_toggle(btn):
        """Reset active state so non-toggle buttons don't stay pressed."""
        if btn.get_active():
            btn.set_active(False)

    @staticmethod
    def _apply_icon_size(label_widget: Gtk.Label, size_px: int):
        """Apply a custom icon size to a label via inline CSS."""
        provider = Gtk.CssProvider()
        provider.load_from_data(f"label {{ font-size: {size_px}px; }}".encode())
        label_widget.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
