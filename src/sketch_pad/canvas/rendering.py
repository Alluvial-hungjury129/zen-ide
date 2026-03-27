"""GtkSnapshot shape drawing mixin for SketchCanvas."""

from gi.repository import Graphene, Gsk, Pango

from shared.utils import tuple_to_gdk_rgba
from sketch_pad.sketch_model import (
    ACTOR_HEIGHT,
    ACTOR_WIDTH,
    ActorShape,
    ArrowShape,
    CloudShape,
    DatabaseShape,
    RectangleShape,
    TopicShape,
)
from themes import get_theme

from .helpers import _hex


class RenderingMixin:
    """Mixin providing all GtkSnapshot rendering methods."""

    def do_snapshot(self, snapshot):
        width = self.get_width()
        height = self.get_height()
        theme = get_theme()
        if self._dark_mode:
            bg = _hex(theme.panel_bg)
            fg = _hex(theme.fg_color)
        else:
            bg = _hex(theme.fg_color)
            fg = _hex(theme.panel_bg)
        bounds = Graphene.Rect().init(0, 0, width, height)
        snapshot.push_clip(bounds)
        snapshot.append_color(tuple_to_gdk_rgba(bg), bounds)

        snapshot.save()
        snapshot.scale(self._zoom, self._zoom)
        snapshot.translate(Graphene.Point().init(self._pan_x, self._pan_y))

        if self._show_grid:
            self._draw_grid(snapshot, width, height, fg)

        grid = self._board.render()

        # Strip text from the grid for the shape being edited so only
        # _draw_editing_text renders it (single text source, no shift).
        if self._text_editing and self._text_shape_id:
            self._strip_editing_shape_text(grid)

        fd = Pango.FontDescription.new()
        fd.set_family(self._grid_font_family)
        fd.set_size(int(self._font_size * Pango.SCALE))

        # Fill backgrounds for shapes with fill_color
        self._draw_fill_colors(snapshot)

        # Board chars
        self._draw_chars(snapshot, grid, fd, fg)

        # Re-draw chars in custom text_color for shapes that have one
        self._draw_colored_chars(snapshot, grid, fd)

        # Custom font-size text overlays
        self._draw_custom_font_texts(snapshot, fg)

        # Preview while creating a shape
        if self._drawing and self._draw_start and self._draw_end:
            preview = self._make_preview_shape()
            if preview:
                pg: dict[tuple[int, int], str] = {}
                preview.render(pg)
                accent = _hex(theme.accent_color)
                self._draw_chars(snapshot, pg, fd, accent)

        # Selection highlight & handles
        self._draw_selection(snapshot, theme)

        # Alignment guides (shown while dragging shapes)
        if self._alignment_guides:
            self._draw_alignment_guides(snapshot, theme, width, height)

        # Marquee selection rectangle
        if self._marquee_selecting and self._marquee_start and self._marquee_end:
            ms, me = self._marquee_start, self._marquee_end
            accent = _hex(theme.accent_color)
            x = min(ms[0], me[0]) * self._cell_w
            y = min(ms[1], me[1]) * self._cell_h
            w = (abs(me[0] - ms[0]) + 1) * self._cell_w
            h = (abs(me[1] - ms[1]) + 1) * self._cell_h
            snapshot.append_color(tuple_to_gdk_rgba(accent, 0.15), Graphene.Rect().init(x, y, w, h))
            builder = Gsk.PathBuilder.new()
            builder.add_rect(Graphene.Rect().init(x, y, w, h))
            stroke = Gsk.Stroke.new(1)
            stroke.set_dash([4, 3])
            snapshot.append_stroke(builder.to_path(), stroke, tuple_to_gdk_rgba(accent, 0.6))

        # Text cursor
        if self._text_editing:
            self._draw_editing_text(snapshot, fg, bg)
            self._draw_text_selection(snapshot, theme, fg, bg)
            self._draw_text_cursor(snapshot, theme)

        # Magnetic snap indicators
        if self._drawing:
            for snap_data in [self._draw_snap_start, self._draw_snap_end]:
                if snap_data:
                    conn, sc, sr = snap_data
                    if conn:
                        accent = _hex(theme.accent_color)
                        cx = sc * self._cell_w + self._cell_w / 2
                        cy = sr * self._cell_h + self._cell_h / 2
                        builder = Gsk.PathBuilder.new()
                        builder.add_circle(Graphene.Point().init(cx, cy), 8)
                        stroke = Gsk.Stroke.new(1)
                        snapshot.append_stroke(builder.to_path(), stroke, tuple_to_gdk_rgba(accent, 0.6))

        snapshot.restore()
        snapshot.pop()

    def _draw_grid(self, snapshot, width, height, fg_color):
        vc = int(width / (self._cell_w * self._zoom)) + 2
        vr = int(height / (self._cell_h * self._zoom)) + 2
        sc = int(-self._pan_x / self._cell_w) - 1
        sr = int(-self._pan_y / self._cell_h) - 1
        builder = Gsk.PathBuilder.new()
        for col in range(sc, sc + vc):
            x = col * self._cell_w
            builder.move_to(x, sr * self._cell_h)
            builder.line_to(x, (sr + vr) * self._cell_h)
        for row in range(sr, sr + vr):
            y = row * self._cell_h
            builder.move_to(sc * self._cell_w, y)
            builder.line_to((sc + vc) * self._cell_w, y)
        stroke = Gsk.Stroke.new(0.5)
        snapshot.append_stroke(builder.to_path(), stroke, tuple_to_gdk_rgba(fg_color, 0.06))

    def _strip_editing_shape_text(self, grid: dict[tuple[int, int], str]):
        """Remove text chars from grid for the shape being edited."""
        shape = self._board.get_shape(self._text_shape_id)
        if not shape or getattr(shape, "font_size", None):
            return  # Font-size shapes use Pango overlay, not grid text
        if isinstance(shape, (RectangleShape, DatabaseShape, TopicShape, CloudShape)):
            interior = shape.get_interior_bounds()
            if interior:
                il, it, ir, ib = interior
                for r in range(it, ib + 1):
                    for c in range(il, ir + 1):
                        if (c, r) in grid:
                            grid[(c, r)] = " "
        elif isinstance(shape, ArrowShape) and shape.text:
            path = shape._compute_path()
            if path:
                mid = path[len(path) // 2]
                lines = shape.text.split("\n")
                num_lines = len(lines)
                for i, line in enumerate(lines):
                    h_offset = -(len(line) // 2)
                    for j in range(len(line)):
                        key = (mid[0] + h_offset + j, mid[1] - num_lines + i)
                        if key in grid:
                            grid[key] = " "
        elif isinstance(shape, ActorShape) and shape.text:
            text_row = shape.top + ACTOR_HEIGHT
            text_start = shape.left + (ACTOR_WIDTH - len(shape.text)) // 2
            for j in range(len(shape.text)):
                key = (text_start + j, text_row)
                if key in grid:
                    grid[key] = " "

    def _draw_chars(self, snapshot, grid: dict, fd, color: tuple):
        if not grid:
            return
        ctx = self.get_pango_context()
        if not ctx:
            return
        rgba = tuple_to_gdk_rgba(color)
        layout = Pango.Layout.new(ctx)
        layout.set_font_description(fd)
        for (col, row), ch in grid.items():
            if not ch or ch == " ":
                continue
            layout.set_text(ch, -1)
            snapshot.save()
            snapshot.translate(Graphene.Point().init(col * self._cell_w, row * self._cell_h))
            snapshot.append_layout(layout, rgba)
            snapshot.restore()

    def _draw_fill_colors(self, snapshot):
        for shape in self._board.z_sorted():
            fc = shape.fill_color
            if not fc:
                continue
            if isinstance(shape, ArrowShape):
                continue
            interior = shape.get_interior_bounds()
            if not interior:
                continue
            left, top, right, bottom = interior
            # Expand fill toward the border lines, leaving only 1px gap
            half_cw = self._cell_w / 2
            half_ch = self._cell_h / 2
            expand_x = half_cw - 1
            expand_y = half_ch - 1
            x = left * self._cell_w - expand_x
            y = top * self._cell_h - expand_y
            w = (right - left + 1) * self._cell_w + 2 * expand_x
            h = (bottom - top + 1) * self._cell_h + 2 * expand_y
            snapshot.append_color(tuple_to_gdk_rgba(_hex(fc)), Graphene.Rect().init(x, y, w, h))

    def _draw_colored_chars(self, snapshot, grid: dict, fd):
        ctx = self.get_pango_context()
        if not ctx:
            return
        # Build color map: (col, row) -> hex_color
        color_map: dict[tuple[int, int], str] = {}
        for shape in self._board.z_sorted():
            # Arrow line coloring via fill_color
            if isinstance(shape, ArrowShape) and shape.fill_color:
                all_chars: dict[tuple[int, int], str] = {}
                shape.render(all_chars)
                text_chars: dict[tuple[int, int], str] = {}
                shape.render_text(text_chars)
                for pos in all_chars:
                    if pos not in text_chars and pos in grid:
                        color_map[pos] = shape.fill_color
            # Text coloring via text_color
            tc = shape.text_color
            if not tc:
                continue
            temp: dict[tuple[int, int], str] = {}
            shape.render_text(temp)
            for pos in temp:
                if pos in grid:
                    color_map[pos] = tc
        if not color_map:
            return
        layout = Pango.Layout.new(ctx)
        layout.set_font_description(fd)
        # Group by color to minimise RGBA object creation
        by_color: dict[str, list[tuple[int, int]]] = {}
        for pos, hc in color_map.items():
            by_color.setdefault(hc, []).append(pos)
        for hc, positions in by_color.items():
            rgba = tuple_to_gdk_rgba(_hex(hc))
            for col, row in positions:
                ch = grid.get((col, row))
                if not ch or ch == " ":
                    continue
                layout.set_text(ch, -1)
                snapshot.save()
                snapshot.translate(Graphene.Point().init(col * self._cell_w, row * self._cell_h))
                snapshot.append_layout(layout, rgba)
                snapshot.restore()

    def _draw_custom_font_texts(self, snapshot, fg):
        ctx = self.get_pango_context()
        if not ctx:
            return
        fg_rgba = tuple_to_gdk_rgba(fg)
        for shape in self._board.z_sorted():
            if not getattr(shape, "font_size", None) or not shape.text:
                continue
            text_rgba = tuple_to_gdk_rgba(_hex(shape.text_color)) if shape.text_color else fg_rgba
            fd = Pango.FontDescription.new()
            fd.set_family(self._font_family)
            fd.set_size(int(shape.font_size * Pango.SCALE))
            layout = Pango.Layout.new(ctx)
            layout.set_font_description(fd)
            layout.set_text(shape.text, -1)
            layout.set_alignment(Pango.Alignment.CENTER)

            if isinstance(shape, (RectangleShape, DatabaseShape, TopicShape, CloudShape)):
                # Centre text in interior pixel area
                if isinstance(shape, (TopicShape, CloudShape, DatabaseShape)):
                    interior = shape.get_interior_bounds()
                    if interior:
                        il, it, ir, ib = interior
                        ix = il * self._cell_w
                        iy = it * self._cell_h
                        iw = (ir - il + 1) * self._cell_w
                        ih = (ib - it + 1) * self._cell_h
                    else:
                        continue
                else:
                    ix = (shape.left + 1) * self._cell_w
                    iy = (shape.top + 1) * self._cell_h
                    iw = (shape.width - 2) * self._cell_w
                    ih = (shape.height - 2) * self._cell_h
                layout.set_width(int(iw * Pango.SCALE))
                _, text_ext = layout.get_pixel_extents()
                ty = iy + max(0, (ih - text_ext.height) / 2)
                snapshot.save()
                snapshot.translate(Graphene.Point().init(ix, ty))
                snapshot.append_layout(layout, text_rgba)
                snapshot.restore()
            elif isinstance(shape, ArrowShape):
                anchor = shape.get_text_anchor()
                cx = anchor[0] * self._cell_w + self._cell_w / 2
                cy = anchor[1] * self._cell_h + self._cell_h / 2
                _, text_ext = layout.get_pixel_extents()
                snapshot.save()
                snapshot.translate(Graphene.Point().init(cx - text_ext.width / 2, cy - text_ext.height / 2))
                snapshot.append_layout(layout, text_rgba)
                snapshot.restore()

    def _visual_bounds(self, shape):
        """Pixel bounds of shape's visible border ink, tighter than cell bounds."""
        ci = self._char_ink
        if not ci:
            return (
                shape.left * self._cell_w,
                shape.top * self._cell_h,
                shape.width * self._cell_w,
                shape.height * self._cell_h,
            )
        if isinstance(shape, CloudShape):
            u = ci.get("_", (0, 0, int(self._cell_w), int(self._cell_h)))
            lp = ci.get("(", (0, 0, int(self._cell_w), int(self._cell_h)))
            rp = ci.get(")", (0, 0, int(self._cell_w), int(self._cell_h)))
            top_y = shape.top * self._cell_h + u[1]
            bot_y = shape.bottom * self._cell_h + u[1] + u[3]
            left_x = shape.left * self._cell_w + lp[0]
            right_x = shape.right * self._cell_w + rp[0] + rp[2]
        elif isinstance(shape, DatabaseShape):
            # Use ─/│ ink for tight bounds, same as RectangleShape.
            hl = ci.get("─", (0, 0, int(self._cell_w), int(self._cell_h)))
            vl = ci.get("│", (0, 0, int(self._cell_w), int(self._cell_h)))
            top_y = shape.top * self._cell_h + hl[1]
            bot_y = shape.bottom * self._cell_h + hl[1] + hl[3]
            left_x = shape.left * self._cell_w + vl[0]
            right_x = shape.right * self._cell_w + vl[0] + vl[2]
        elif isinstance(shape, (RectangleShape, TopicShape)):
            hl = ci.get("─", (0, 0, int(self._cell_w), int(self._cell_h)))
            vl = ci.get("│", (0, 0, int(self._cell_w), int(self._cell_h)))
            top_y = shape.top * self._cell_h + hl[1]
            bot_y = shape.bottom * self._cell_h + hl[1] + hl[3]
            left_x = shape.left * self._cell_w + vl[0]
            right_x = shape.right * self._cell_w + vl[0] + vl[2]
        else:
            return (
                shape.left * self._cell_w,
                shape.top * self._cell_h,
                shape.width * self._cell_w,
                shape.height * self._cell_h,
            )
        return (left_x, top_y, right_x - left_x, bot_y - top_y)

    def _draw_selection(self, snapshot, theme):
        if not self._selected_ids:
            return
        accent = _hex(theme.accent_color)
        for shape in self.selected_shapes:
            if isinstance(shape, ArrowShape) and self._text_only_selection and len(self._selected_ids) == 1:
                self._draw_text_only_sel(snapshot, shape, accent)
            elif isinstance(shape, ArrowShape):
                self._draw_arrow_sel(snapshot, shape, accent)
            else:
                vx, vy, vw, vh = self._visual_bounds(shape)
                pad = 2
                builder = Gsk.PathBuilder.new()
                builder.add_rect(Graphene.Rect().init(vx - pad, vy - pad, vw + 2 * pad, vh + 2 * pad))
                stroke = Gsk.Stroke.new(2.0)
                stroke.set_dash([5, 3])
                snapshot.append_stroke(builder.to_path(), stroke, tuple_to_gdk_rgba(accent, 0.7))
                if len(self._selected_ids) == 1:
                    self._draw_resize_handles(snapshot, shape, accent)

    def _draw_arrow_sel(self, snapshot, shape: ArrowShape, accent):
        path = shape._compute_path()
        if len(path) < 2:
            return
        # Arrow path highlight
        builder = Gsk.PathBuilder.new()
        x0 = path[0][0] * self._cell_w + self._cell_w / 2
        y0 = path[0][1] * self._cell_h + self._cell_h / 2
        builder.move_to(x0, y0)
        for c, r in path[1:]:
            builder.line_to(c * self._cell_w + self._cell_w / 2, r * self._cell_h + self._cell_h / 2)
        stroke = Gsk.Stroke.new(3)
        snapshot.append_stroke(builder.to_path(), stroke, tuple_to_gdk_rgba(accent, 0.55))
        # Endpoint handles — connected endpoints get a diamond, unconnected get a circle
        for end_name, (c, r), conn in [
            ("start", (shape.start_col, shape.start_row), shape.start_connection),
            ("end", (shape.end_col, shape.end_row), shape.end_connection),
        ]:
            cx = c * self._cell_w + self._cell_w / 2
            cy = r * self._cell_h + self._cell_h / 2
            if conn:
                # Diamond for connected endpoints
                ds = 6
                builder = Gsk.PathBuilder.new()
                builder.move_to(cx, cy - ds)
                builder.line_to(cx + ds, cy)
                builder.line_to(cx, cy + ds)
                builder.line_to(cx - ds, cy)
                builder.close()
                snapshot.append_fill(builder.to_path(), Gsk.FillRule.WINDING, tuple_to_gdk_rgba(accent, 0.9))
                if conn.pinned:
                    # Inner dot to indicate pinned state
                    if self._dark_mode:
                        dot_color = tuple_to_gdk_rgba((0, 0, 0), 0.8)
                    else:
                        dot_color = tuple_to_gdk_rgba((1, 1, 1), 0.8)
                    builder = Gsk.PathBuilder.new()
                    builder.add_circle(Graphene.Point().init(cx, cy), 2)
                    snapshot.append_fill(builder.to_path(), Gsk.FillRule.WINDING, dot_color)
            else:
                # Circle for unconnected endpoints
                builder = Gsk.PathBuilder.new()
                builder.add_circle(Graphene.Point().init(cx, cy), 5)
                snapshot.append_fill(builder.to_path(), Gsk.FillRule.WINDING, tuple_to_gdk_rgba(accent, 0.8))
        # Highlight connected shapes at connection points
        self._draw_connection_hints(snapshot, shape, accent)

    def _draw_text_only_sel(self, snapshot, shape: ArrowShape, accent):
        """Draw selection highlight only around the arrow's text label."""
        pad = 2
        if shape.font_size and shape.text:
            # Pixel-accurate bounds for custom font_size text
            ctx = self.get_pango_context()
            if not ctx:
                return
            fd = Pango.FontDescription.new()
            fd.set_family(self._font_family)
            fd.set_size(int(shape.font_size * Pango.SCALE))
            layout = Pango.Layout.new(ctx)
            layout.set_font_description(fd)
            layout.set_text(shape.text, -1)
            layout.set_alignment(Pango.Alignment.CENTER)
            anchor = shape.get_text_anchor()
            cx = anchor[0] * self._cell_w + self._cell_w / 2
            cy = anchor[1] * self._cell_h + self._cell_h / 2
            _, text_ext = layout.get_pixel_extents()
            vx = cx - text_ext.width / 2 - pad
            vy = cy - text_ext.height / 2 - pad
            vw = text_ext.width + 2 * pad
            vh = text_ext.height + 2 * pad
        else:
            bounds = shape.text_bounds()
            if not bounds:
                return
            left, top, right, bottom = bounds
            vx = left * self._cell_w - pad
            vy = top * self._cell_h - pad
            vw = (right - left + 1) * self._cell_w + 2 * pad
            vh = (bottom - top + 1) * self._cell_h + 2 * pad
        builder = Gsk.PathBuilder.new()
        builder.add_rect(Graphene.Rect().init(vx, vy, vw, vh))
        stroke = Gsk.Stroke.new(2.0)
        stroke.set_dash([5, 3])
        snapshot.append_stroke(builder.to_path(), stroke, tuple_to_gdk_rgba(accent, 0.7))

    def _draw_connection_hints(self, snapshot, arrow: ArrowShape, accent):
        for conn in [arrow.start_connection, arrow.end_connection]:
            if not conn:
                continue
            target = self._board.get_shape(conn.shape_id)
            if not target:
                continue
            ec, er = target.edge_point_from_connection(conn.edge, conn.ratio)
            cx = ec * self._cell_w + self._cell_w / 2
            cy = er * self._cell_h + self._cell_h / 2
            # Outer glow ring on the shape edge
            builder = Gsk.PathBuilder.new()
            builder.add_circle(Graphene.Point().init(cx, cy), 20)
            snapshot.append_fill(builder.to_path(), Gsk.FillRule.WINDING, tuple_to_gdk_rgba(accent, 0.35))
            # Mid glow ring
            builder = Gsk.PathBuilder.new()
            builder.add_circle(Graphene.Point().init(cx, cy), 12)
            snapshot.append_fill(builder.to_path(), Gsk.FillRule.WINDING, tuple_to_gdk_rgba(accent, 0.45))
            # Inner bright dot
            builder = Gsk.PathBuilder.new()
            builder.add_circle(Graphene.Point().init(cx, cy), 5)
            snapshot.append_fill(builder.to_path(), Gsk.FillRule.WINDING, tuple_to_gdk_rgba(accent, 0.85))
            # Highlight on the connected shape border
            sx = target.left * self._cell_w - 4
            sy = target.top * self._cell_h - 4
            sw = target.width * self._cell_w + 8
            sh = target.height * self._cell_h + 8
            builder = Gsk.PathBuilder.new()
            builder.add_rect(Graphene.Rect().init(sx, sy, sw, sh))
            stroke = Gsk.Stroke.new(2.5)
            snapshot.append_stroke(builder.to_path(), stroke, tuple_to_gdk_rgba(accent, 0.45))

    def _draw_resize_handles(self, snapshot, shape, accent):
        hs = 4
        vx, vy, vw, vh = self._visual_bounds(shape)
        pts = [
            (vx, vy),
            (vx + vw / 2, vy),
            (vx + vw, vy),
            (vx, vy + vh / 2),
            (vx + vw, vy + vh / 2),
            (vx, vy + vh),
            (vx + vw / 2, vy + vh),
            (vx + vw, vy + vh),
        ]
        rgba = tuple_to_gdk_rgba(accent, 0.8)
        for hx, hy in pts:
            snapshot.append_color(rgba, Graphene.Rect().init(hx - hs, hy - hs, hs * 2, hs * 2))
