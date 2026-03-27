"""
Alignment guides and snapping mixin for SketchCanvas.
"""

from gi.repository import Gsk

from shared.utils import tuple_to_gdk_rgba
from sketch_pad.sketch_model import ArrowShape

from .helpers import _hex


class AlignmentMixin:
    """Mixin providing alignment guide computation and drawing."""

    def _compute_alignment_guides(self):
        """Compute alignment guide lines between dragged shapes and other shapes."""
        self._alignment_guides.clear()
        moving_ids = self._selected_ids
        if not moving_ids:
            return

        # Collect edges and centers of moving shapes (non-arrows only)
        moving_lefts, moving_rights, moving_tops, moving_bottoms = [], [], [], []
        moving_cx, moving_cy = [], []
        for shape in self.selected_shapes:
            if isinstance(shape, ArrowShape):
                continue
            moving_lefts.append(shape.left)
            moving_rights.append(shape.right)
            moving_tops.append(shape.top)
            moving_bottoms.append(shape.bottom)
            moving_cx.append(shape.left + shape.width / 2)
            moving_cy.append(shape.top + shape.height / 2)

        if not moving_lefts:
            return

        # Collect edges and centers of stationary shapes
        guides = []
        for shape in self._board.shapes.values():
            if shape.id in moving_ids or isinstance(shape, ArrowShape):
                continue
            other_cols = [shape.left, shape.right, shape.left + shape.width / 2]
            other_rows = [shape.top, shape.bottom, shape.top + shape.height / 2]
            # Check vertical alignment (same column)
            for mc in moving_lefts + moving_rights + moving_cx:
                for oc in other_cols:
                    if abs(mc - oc) < 0.5:
                        guides.append(("v", oc))
            # Check horizontal alignment (same row)
            for mr in moving_tops + moving_bottoms + moving_cy:
                for orow in other_rows:
                    if abs(mr - orow) < 0.5:
                        guides.append(("h", orow))

        # Deduplicate
        self._alignment_guides = list(set(guides))

    def _draw_alignment_guides(self, snapshot, theme, width, height):
        """Draw alignment guide lines across the canvas."""
        accent = _hex(theme.accent_color)
        # Visible range in grid coords
        vw = width / self._zoom
        vh = height / self._zoom
        min_col = -self._pan_x / self._cell_w - 10 if self._cell_w > 0 else 0
        max_col = min_col + vw / self._cell_w + 20 if self._cell_w > 0 else 100
        min_row = -self._pan_y / self._cell_h - 10 if self._cell_h > 0 else 0
        max_row = min_row + vh / self._cell_h + 20 if self._cell_h > 0 else 100

        for kind, pos in self._alignment_guides:
            builder = Gsk.PathBuilder.new()
            if kind == "v":
                x = pos * self._cell_w + self._cell_w / 2
                builder.move_to(x, min_row * self._cell_h)
                builder.line_to(x, max_row * self._cell_h)
            else:
                y = pos * self._cell_h + self._cell_h / 2
                builder.move_to(min_col * self._cell_w, y)
                builder.line_to(max_col * self._cell_w, y)
            stroke = Gsk.Stroke.new(0.8)
            stroke.set_dash([6, 4])
            snapshot.append_stroke(builder.to_path(), stroke, tuple_to_gdk_rgba(accent, 0.5))
