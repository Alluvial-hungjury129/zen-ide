"""
Unified themed entry widgets for Zen IDE.

ZenSearchEntry and ZenEntry provide consistent font, color, and theme
reactivity for every search/input box in the application.  They are
self-contained: each instance owns its own CssProvider and subscribes
to theme and font changes so styling stays in sync automatically.

Use the *font_context* parameter to choose which font settings to use:
  - ``"editor"`` (default) — main editor font
  - ``"explorer"`` — file-tree / explorer font
"""

from gi.repository import Gtk

from fonts import get_font_settings, subscribe_font_change
from themes import get_theme, subscribe_theme_change, unsubscribe_theme_change


def _build_entry_css(node_type: str, font_context: str) -> str:
    """Generate CSS for an entry widget using current theme and *font_context* font."""
    theme = get_theme()
    settings = get_font_settings(font_context)
    family = settings["family"]
    size = settings["size"]

    return f"""
        {node_type} {{
            font-family: "{family}";
            font-size: {size}pt;
            color: {theme.fg_color};
        }}
        {node_type} > text {{
            font-family: "{family}";
            font-size: {size}pt;
            color: {theme.fg_color};
            background: transparent;
            border: none;
            outline: none;
            outline-width: 0;
        }}
    """


def _setup_zen_entry(widget: Gtk.Widget, node_type: str, font_context: str) -> None:
    """Wire up CSS provider and change subscriptions on *widget*."""
    provider = Gtk.CssProvider()
    widget.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)

    def _refresh(*_args):
        provider.load_from_data(_build_entry_css(node_type, font_context).encode())

    _refresh()

    theme_cb = lambda _theme: _refresh()
    font_cb = lambda comp, _settings: _refresh() if comp == font_context else None

    subscribe_theme_change(theme_cb)
    subscribe_font_change(font_cb)

    # Clean up subscriptions when widget is removed from the tree.
    def _on_unrealize(_w):
        unsubscribe_theme_change(theme_cb)

    widget.connect("unrealize", _on_unrealize)


class ZenSearchEntry(Gtk.SearchEntry):
    """A Gtk.SearchEntry with automatic Zen IDE font and theme colors."""

    def __init__(self, placeholder: str = "Search...", font_context: str = "editor"):
        super().__init__()
        self.set_placeholder_text(placeholder)
        _setup_zen_entry(self, "searchentry", font_context)


class ZenEntry(Gtk.Entry):
    """A Gtk.Entry with automatic Zen IDE font and theme colors."""

    def __init__(self, placeholder: str = "", initial_value: str = "", font_context: str = "editor"):
        super().__init__()
        self.set_placeholder_text(placeholder)
        if initial_value:
            self.set_text(initial_value)
        _setup_zen_entry(self, "entry", font_context)
