"""Shared block cursor drawing for Gtk.TextView subclasses.

Draws a filled rectangle (block cursor) at the insert mark position.
Used by ``BlockCursorTextView`` and ``ZenSourceView`` when the
``wide_cursor`` setting is enabled.
"""

from gi.repository import Gdk, Graphene, Gtk, Pango

from constants import CURSOR_ALPHA

_PANGO_SCALE = Pango.SCALE


def draw_block_cursor(view, snapshot):
    """Draw a block cursor at the insert mark on *view*.

    Parameters
    ----------
    view : Gtk.TextView | GtkSource.View
        The text view to draw on.
    snapshot : Gtk.Snapshot
        The current snapshot from ``do_snapshot``.
    """
    buf = view.get_buffer()
    insert = buf.get_insert()
    it = buf.get_iter_at_mark(insert)

    # Cursor position in buffer coordinates
    strong, _weak = view.get_cursor_locations(it)
    x, y = view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, strong.x, strong.y)

    # Use Pango font metrics for consistent monospace character cell width
    pc = view.get_pango_context()
    font_desc = pc.get_font_description()
    metrics = pc.get_metrics(font_desc)
    char_w = metrics.get_approximate_char_width() / _PANGO_SCALE

    if char_w <= 0:
        char_w = max(strong.height * 0.6, 8)

    from themes import get_theme

    theme = get_theme()
    color = Gdk.RGBA()
    color.parse(theme.fg_color)
    color.alpha = CURSOR_ALPHA

    rect = Graphene.Rect()
    rect.init(x, y, char_w, strong.height)
    snapshot.append_color(color, rect)
