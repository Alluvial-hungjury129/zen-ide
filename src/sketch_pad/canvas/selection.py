"""
Selection, resize handle hit-testing, and resize logic mixin for SketchCanvas.
"""

from sketch_pad.sketch_model import (
    CLOUD_MIN_HEIGHT,
    CLOUD_MIN_WIDTH,
    DATABASE_MIN_HEIGHT,
    DATABASE_MIN_WIDTH,
    TOPIC_MIN_HEIGHT,
    TOPIC_MIN_WIDTH,
    ActorShape,
    ArrowShape,
    CloudShape,
    DatabaseShape,
    RectangleShape,
    TopicShape,
)


class SelectionMixin:
    """Mixin providing selection, resize handle hit-testing, and resize logic."""

    def _handle_select_press(self, col: int, row: int, sx: float, sy: float, *, cmd_held: bool = False):
        self._exit_text_edit()
        shape = self._board.get_shape_at(col, row)
        # Detect text-only hit on arrow labels
        text_only = isinstance(shape, ArrowShape) and shape.text_contains(col, row)
        if shape:
            if cmd_held:
                if shape.id in self._selected_ids:
                    self._selected_ids.discard(shape.id)
                else:
                    self._selected_ids.add(shape.id)
                self._text_only_selection = False
            else:
                if shape.id not in self._selected_ids:
                    self._selected_ids = {shape.id}
                self._text_only_selection = text_only
        else:
            if not cmd_held:
                self._selected_ids.clear()
            self._text_only_selection = False
            self._marquee_selecting = True
            self._marquee_start = (col, row)
            self._marquee_end = (col, row)
            self._drag_start_screen = (sx, sy)
        self.queue_draw()

    def _hit_resize_handle(self, sx: float, sy: float) -> str | None:
        if not self._selected_ids:
            return None
        shape = self.selected_shapes[0] if self.selected_shapes else None
        if not shape or isinstance(shape, ArrowShape):
            return None
        r = 8
        vx, vy, vw, vh = self._visual_bounds(shape)

        # Convert canvas coords to screen coords
        def _to_screen(cx, cy):
            return ((cx + self._pan_x) * self._zoom, (cy + self._pan_y) * self._zoom)

        handles = {
            "tl": _to_screen(vx, vy),
            "tr": _to_screen(vx + vw, vy),
            "bl": _to_screen(vx, vy + vh),
            "br": _to_screen(vx + vw, vy + vh),
            "tc": _to_screen(vx + vw / 2, vy),
            "bc": _to_screen(vx + vw / 2, vy + vh),
            "ml": _to_screen(vx, vy + vh / 2),
            "mr": _to_screen(vx + vw, vy + vh / 2),
        }
        for name, (hx, hy) in handles.items():
            if abs(sx - hx) <= r and abs(sy - hy) <= r:
                return name
        return None

    def _hit_arrow_endpoint(self, shape: ArrowShape, sx: float, sy: float) -> str | None:
        r = 10
        for end_name, (c, rr) in [("start", (shape.start_col, shape.start_row)), ("end", (shape.end_col, shape.end_row))]:
            ex, ey = self._grid_to_screen(c, rr)
            # Center of the cell
            ex += self._cell_w * self._zoom / 2
            ey += self._cell_h * self._zoom / 2
            if abs(sx - ex) <= r and abs(sy - ey) <= r:
                return end_name
        return None

    def _apply_resize(self, cursor_col: int, cursor_row: int):
        shape = self._board.get_shape(self._resize_shape_id)
        if not shape or isinstance(shape, (ArrowShape, ActorShape)):
            return
        o = self._resize_orig
        ol, ot = o["left"], o["top"]
        or_ = ol + o["width"] - 1
        ob = ot + o["height"] - 1
        nl, nt, nr, nb = ol, ot, or_, ob
        h = self._resize_handle
        if h in ("tl", "ml", "bl"):
            nl = min(cursor_col, or_ - 1)
        if h in ("tr", "mr", "br"):
            nr = max(cursor_col, ol + 1)
        if h in ("tl", "tc", "tr"):
            nt = min(cursor_row, ob - 1)
        if h in ("bl", "bc", "br"):
            nb = max(cursor_row, ot + 1)
        # Enforce minimum size
        min_w, min_h = 2, 2
        if isinstance(shape, DatabaseShape):
            min_w, min_h = shape.min_size_for_text() if shape.text else (DATABASE_MIN_WIDTH, DATABASE_MIN_HEIGHT)
        elif isinstance(shape, CloudShape):
            min_w, min_h = shape.min_size_for_text() if shape.text else (CLOUD_MIN_WIDTH, CLOUD_MIN_HEIGHT)
        elif isinstance(shape, TopicShape):
            min_w, min_h = TOPIC_MIN_WIDTH, TOPIC_MIN_HEIGHT
        elif isinstance(shape, RectangleShape) and shape.text:
            min_w, min_h = shape.min_size_for_text()
        if nr - nl + 1 < min_w:
            if h in ("tl", "ml", "bl"):
                nl = nr - min_w + 1
            else:
                nr = nl + min_w - 1
        if nb - nt + 1 < min_h:
            if h in ("tl", "tc", "tr"):
                nt = nb - min_h + 1
            else:
                nb = nt + min_h - 1
        shape.left = nl
        shape.top = nt
        shape.width = nr - nl + 1
        shape.height = nb - nt + 1
