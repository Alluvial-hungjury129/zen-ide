"""
Border overlay widget for NvimPopup.

Draws the popup border (outer + inner double-line) using GtkSnapshot,
with an optional title gap on the top edge.
"""

from gi.repository import Gdk, Graphene, Gsk, Gtk

from shared.settings import get_setting
from themes import get_theme


class _BorderOverlay(Gtk.Widget):
    """Draws the popup border using GtkSnapshot"""

    def __init__(self, popup):
        super().__init__()
        self._popup = popup

    def do_snapshot(self, snapshot):
        from shared.utils import hex_to_rgb_float

        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return

        theme = get_theme()
        radius = get_setting("popup.border_radius", 0)
        half = 0.5
        line_gap = 3
        y_top = self._popup._title_half_height + half

        # Fill the strip above the border with the editor background
        if self._popup._title_half_height > 0:
            er, eg, eb = hex_to_rgb_float(theme.main_bg)
            bg = Gdk.RGBA()
            bg.red, bg.green, bg.blue, bg.alpha = er, eg, eb, 1.0
            fill_h = self._popup._title_half_height + 1
            if radius > 0:
                b = Gsk.PathBuilder.new()
                b.move_to(radius, 0)
                b.line_to(width - radius, 0)
                b.svg_arc_to(radius, radius, 0, False, True, width, radius)
                b.line_to(width, fill_h)
                b.line_to(0, fill_h)
                b.line_to(0, radius)
                b.svg_arc_to(radius, radius, 0, False, True, radius, 0)
                b.close()
                snapshot.append_fill(b.to_path(), Gsk.FillRule.WINDING, bg)
            else:
                snapshot.append_color(bg, Graphene.Rect().init(0, 0, width, fill_h))

        # Border colour and stroke
        r, g, b = hex_to_rgb_float(theme.border_focus)
        border_color = Gdk.RGBA()
        border_color.red, border_color.green, border_color.blue, border_color.alpha = r, g, b, 1.0
        stroke = Gsk.Stroke.new(1.0)

        y_bot = height - half
        x_left = half
        x_right = width - half

        # Title gap
        gap_start = gap_end = 0
        if self._popup._title_label:
            alloc = self._popup._title_label.get_allocation()
            if alloc.width > 1:
                gap_start = alloc.x - 2
                gap_end = alloc.x + alloc.width + 2

        # Outer border
        snapshot.append_stroke(
            self._border_path(x_left, y_top, x_right, y_bot, radius, gap_start, gap_end),
            stroke,
            border_color,
        )

        # Inner border (parallel line inset by line_gap)
        inner_r = max(0, radius - line_gap)
        snapshot.append_stroke(
            self._border_path(
                x_left + line_gap,
                y_top + line_gap,
                x_right - line_gap,
                y_bot - line_gap,
                inner_r,
                gap_start,
                gap_end,
            ),
            stroke,
            border_color,
        )

    @staticmethod
    def _border_path(x_left, y_top, x_right, y_bot, r, gap_start=0, gap_end=0):
        """Build a rounded-rect path, optionally with a title gap on the top edge."""
        has_gap = gap_start < gap_end and gap_start > x_left + r and gap_end < x_right - r
        pb = Gsk.PathBuilder.new()

        if has_gap:
            pb.move_to(gap_end, y_top)
        else:
            pb.move_to(x_left + r, y_top)

        # Top edge → top-right corner
        pb.line_to(x_right - r, y_top)
        if r > 0:
            pb.svg_arc_to(r, r, 0, False, True, x_right, y_top + r)
        # Right edge → bottom-right corner
        pb.line_to(x_right, y_bot - r)
        if r > 0:
            pb.svg_arc_to(r, r, 0, False, True, x_right - r, y_bot)
        # Bottom edge → bottom-left corner
        pb.line_to(x_left + r, y_bot)
        if r > 0:
            pb.svg_arc_to(r, r, 0, False, True, x_left, y_bot - r)
        # Left edge → top-left corner
        pb.line_to(x_left, y_top + r)
        if r > 0:
            pb.svg_arc_to(r, r, 0, False, True, x_left + r, y_top)

        if has_gap:
            pb.line_to(gap_start, y_top)
        else:
            pb.close()

        return pb.to_path()
