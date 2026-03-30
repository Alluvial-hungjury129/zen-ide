"""Line number renderer (center column) — centered line numbers."""

from gi.repository import Graphene, Gtk, GtkSource, Pango

from shared.utils import hex_to_gdk_rgba
from themes import get_theme

from .constants import _MIN_DIGITS, _NUM_PAD


class LineNumberRenderer(GtkSource.GutterRenderer):
    __gtype_name__ = "LineNumberRenderer"

    def __init__(self, view, fold_manager):
        super().__init__()
        self._view = view
        self._fm = fold_manager
        self._layout = None
        self._char_width = 0.0
        self._cached_width = 0
        self.set_xpad(0)
        self.set_ypad(0)

        buf = view.get_buffer()
        if buf:
            buf.connect("notify::cursor-position", lambda *_: self.queue_draw())
            buf.connect("changed", lambda *_: self._update_width())

    def _ensure_char_width(self):
        if self._char_width > 0:
            return
        pc = self._view.get_pango_context()
        if pc is None:
            return
        font_desc = pc.get_font_description()
        if font_desc is None:
            return
        metrics = pc.get_metrics(font_desc)
        self._char_width = metrics.get_approximate_digit_width() / Pango.SCALE
        if self._char_width <= 0:
            self._char_width = 8.0

    def _compute_width(self):
        self._ensure_char_width()
        buf = self._view.get_buffer()
        line_count = buf.get_line_count() if buf else 1
        digits = max(_MIN_DIGITS, len(str(line_count)))
        return int(digits * self._char_width) + _NUM_PAD * 2

    def _update_width(self):
        new_w = self._compute_width()
        if new_w != self._cached_width:
            self._cached_width = new_w
            self.queue_resize()

    def do_measure(self, _orientation, _for_size):
        w = self._compute_width()
        self._cached_width = w
        return w, w, -1, -1

    def do_query_data(self, lines, line):
        pass

    def do_snapshot_line(self, snapshot, lines, line):
        if any(sl < line <= el for sl, el in self._fm._collapsed.items()):
            return

        # Paint gutter background per-line
        theme = get_theme()
        line_y_bg, line_h_bg = lines.get_line_yrange(line, Gtk.TextWindowType.WIDGET)
        snapshot.append_color(
            hex_to_gdk_rgba(theme.line_number_bg, 1.0), Graphene.Rect().init(0, line_y_bg, self._cached_width, line_h_bg)
        )
        is_current = lines.is_cursor(line)
        num_fg = hex_to_gdk_rgba(theme.fg_color if is_current else theme.line_number_fg, 1.0)

        if self._layout is None:
            self._layout = self._view.create_pango_layout("")

        self._layout.set_text(str(line + 1), -1)
        _ink, logical = self._layout.get_pixel_extents()
        line_y, line_h = lines.get_line_yrange(line, Gtk.TextWindowType.WIDGET)
        x = self._cached_width - logical.width - _NUM_PAD
        y = line_y + (line_h - logical.height) / 2

        snapshot.save()
        snapshot.translate(Graphene.Point().init(x, y))
        snapshot.append_layout(self._layout, num_fg)
        snapshot.restore()
