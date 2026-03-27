"""
Text rendering mixin for SketchCanvas — drawing text cursors, selections,
and editing overlays during inline text editing.
"""

from gi.repository import Graphene, Pango

from shared.utils import tuple_to_gdk_rgba
from sketch_pad.sketch_model import (
    ActorShape,
    ArrowShape,
    CloudShape,
    DatabaseShape,
    RectangleShape,
    TopicShape,
)

from .helpers import _hex


class TextRenderingMixin:
    """Mixin providing text cursor, selection highlight, and editing overlay rendering."""

    def _draw_editing_text(self, snapshot, fg, bg):
        """Clear and re-render text for non-font-size shapes during editing.

        Font-size shapes are rendered solely by _draw_custom_font_texts,
        so this only handles grid-based (non-font-size) shapes.
        """
        shape = self._board.get_shape(self._text_shape_id) if self._text_shape_id else None
        if not shape:
            return

        fs = getattr(shape, "font_size", None)

        if fs:
            # Font-size shapes: text rendered by _draw_custom_font_texts only
            return

        # --- clear the interior so the grid text underneath is hidden ---
        interior = getattr(shape, "get_interior_bounds", lambda: None)()
        if interior:
            il, it, ir, ib = interior
            x = il * self._cell_w
            y = it * self._cell_h
            w = (ir - il + 1) * self._cell_w
            h = (ib - it + 1) * self._cell_h
            snapshot.append_color(tuple_to_gdk_rgba(bg), Graphene.Rect().init(x, y, w, h))
        elif isinstance(shape, ArrowShape):
            anchor = shape.get_text_anchor()
            num_lines = len(self._text_buffer)
            max_w = max((len(l) for l in self._text_buffer), default=0)
            if max_w and num_lines:
                ax = (anchor[0] - max_w // 2 - 1) * self._cell_w
                ay = (anchor[1] - num_lines + 1) * self._cell_h
                aw = (max_w + 2) * self._cell_w
                ah = num_lines * self._cell_h
                snapshot.append_color(tuple_to_gdk_rgba(bg), Graphene.Rect().init(ax, ay, aw, ah))

        # --- render text from the buffer at cursor-aligned positions ---
        ctx = self.get_pango_context()
        if not ctx:
            return
        fg_rgba = tuple_to_gdk_rgba(fg)
        fd = Pango.FontDescription.new()
        fd.set_family(self._grid_font_family)
        fd.set_size(int(self._font_size * Pango.SCALE))
        layout = Pango.Layout.new(ctx)
        layout.set_font_description(fd)
        for line_idx, line_text in enumerate(self._text_buffer):
            for char_idx, ch in enumerate(line_text):
                col, row = self._text_pos_to_grid(line_idx, char_idx)
                layout.set_text(ch, -1)
                snapshot.save()
                snapshot.translate(Graphene.Point().init(col * self._cell_w, row * self._cell_h))
                snapshot.append_layout(layout, fg_rgba)
                snapshot.restore()

    def _draw_text_cursor(self, snapshot, theme):
        accent = _hex(theme.accent_color)
        shape = self._board.get_shape(self._text_shape_id) if self._text_shape_id else None
        fs = getattr(shape, "font_size", None) if shape else None
        if fs:
            x, y, h = self._custom_font_cursor_pos(shape)
            snapshot.append_color(tuple_to_gdk_rgba(accent, 0.8), Graphene.Rect().init(x, y, 2, h))
        else:
            x = self._text_cursor_col * self._cell_w
            y = self._text_cursor_row * self._cell_h
            snapshot.append_color(tuple_to_gdk_rgba(accent, 0.8), Graphene.Rect().init(x, y, 2, self._cell_h))

    def _text_pos_to_grid(self, line: int, char: int) -> tuple[int, int]:
        """Convert text buffer (line, char) to grid (col, row)."""
        shape = self._board.get_shape(self._text_shape_id) if self._text_shape_id else None
        if not shape:
            return (char, line)
        num_lines = len(self._text_buffer)
        line_text = self._text_buffer[line] if line < num_lines else ""
        if isinstance(shape, (RectangleShape, DatabaseShape, TopicShape, CloudShape)):
            interior = shape.get_interior_bounds()
            if interior:
                il, it, ir, ib = interior
                ih = ib - it + 1
                v_offset = max(0, (ih - num_lines) // 2)
                iw = ir - il + 1
                h_offset = max(0, (iw - len(line_text)) // 2)
                return (il + h_offset + char, it + v_offset + line)
            return (shape.left + char, shape.top + line)
        elif isinstance(shape, ArrowShape):
            anchor = shape.get_text_anchor()
            h_offset = -(len(line_text) // 2)
            return (anchor[0] + h_offset + char, anchor[1] - num_lines + line + 1)
        elif isinstance(shape, ActorShape):
            text_row = shape.top + shape.height - 1
            text_start = shape.left + (shape.width - len(line_text)) // 2
            return (text_start + char, text_row)
        elif isinstance(shape, TopicShape):
            interior = shape.get_interior_bounds()
            if interior:
                il, it, ir, ib = interior
                ih = ib - it + 1
                iw = ir - il + 1
                v_offset = max(0, (ih - num_lines) // 2)
                h_offset = max(0, (iw - len(line_text)) // 2)
                return (il + h_offset + char, it + v_offset + line)
            return (shape.left + 1 + char, shape.top)
        return (char, line)

    def _draw_text_selection(self, snapshot, theme, fg_color, bg_color):
        """Draw highlight rectangles over selected text and redraw chars with contrast."""
        if not self._has_text_selection():
            return
        sl, sc, el, ec = self._get_text_selection_ordered()
        accent = _hex(theme.accent_color)
        shape = self._board.get_shape(self._text_shape_id) if self._text_shape_id else None
        fs = getattr(shape, "font_size", None) if shape else None
        accent_rgba = tuple_to_gdk_rgba(accent, 0.45)

        # Collect rectangles and selected text fragments for redrawing
        rects = []
        for line_idx in range(sl, el + 1):
            line_text = self._text_buffer[line_idx] if line_idx < len(self._text_buffer) else ""
            start_c = sc if line_idx == sl else 0
            end_c = ec if line_idx == el else len(line_text)
            if start_c >= end_c:
                continue
            if fs and shape:
                xs, ys, lh = self._custom_font_cursor_pos(shape, line_idx, start_c)
                xe, _, _ = self._custom_font_cursor_pos(shape, line_idx, end_c)
                snapshot.append_color(accent_rgba, Graphene.Rect().init(xs, ys, xe - xs, lh))
                rects.append(("custom", line_idx, start_c, end_c, xs, ys, lh))
            else:
                cs, rs = self._text_pos_to_grid(line_idx, start_c)
                ce, _ = self._text_pos_to_grid(line_idx, end_c)
                snapshot.append_color(
                    accent_rgba,
                    Graphene.Rect().init(cs * self._cell_w, rs * self._cell_h, (ce - cs) * self._cell_w, self._cell_h),
                )
                rects.append(("grid", line_idx, start_c, end_c, cs, rs, None))

        # Redraw selected characters on top with background color for contrast
        ctx = self.get_pango_context()
        if not ctx:
            return
        bg_rgba = tuple_to_gdk_rgba(bg_color)
        fd = Pango.FontDescription.new()
        layout = Pango.Layout.new(ctx)
        for entry in rects:
            mode = entry[0]
            line_idx, start_c, end_c = entry[1], entry[2], entry[3]
            line_text = self._text_buffer[line_idx] if line_idx < len(self._text_buffer) else ""
            sel_text = line_text[start_c:end_c]
            if not sel_text:
                continue
            if mode == "custom" and fs:
                fd.set_family(self._font_family)
                xs, ys = entry[4], entry[5]
                fd.set_size(int(fs * Pango.SCALE))
                layout.set_font_description(fd)
                layout.set_text(sel_text, -1)
                snapshot.save()
                snapshot.translate(Graphene.Point().init(xs, ys))
                snapshot.append_layout(layout, bg_rgba)
                snapshot.restore()
            else:
                fd.set_family(self._grid_font_family)
                cs, rs = entry[4], entry[5]
                fd.set_size(int(self._font_size * Pango.SCALE))
                layout.set_font_description(fd)
                for j, ch in enumerate(sel_text):
                    layout.set_text(ch, -1)
                    snapshot.save()
                    snapshot.translate(Graphene.Point().init((cs + j) * self._cell_w, rs * self._cell_h))
                    snapshot.append_layout(layout, bg_rgba)
                    snapshot.restore()
