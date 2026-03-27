"""Indent guide drawing and diagnostic wave rendering for ZenSourceView."""

from gi.repository import Graphene, Gtk, Pango

from constants import NO_INDENT_GUIDE_LANGS

from .core import _iter_at_line, _iter_at_offset


class ZenSourceViewGuttersMixin:
    """Mixin providing indent guides and diagnostic wave drawing for ZenSourceView."""

    def _draw_diagnostic_waves(self, snapshot):
        """Draw custom wavy underlines for diagnostic-tagged text ranges."""
        buf = self.get_buffer()
        tag_table = buf.get_tag_table()
        error_tag = tag_table.lookup("diag_error_underline")
        warning_tag = tag_table.lookup("diag_warning_underline")
        if error_tag is None and warning_tag is None:
            return

        visible = self.get_visible_rect()
        vis_start, _ = self.get_line_at_y(visible.y)
        vis_end, _ = self.get_line_at_y(visible.y + visible.height)
        if not vis_end.ends_line():
            vis_end.forward_to_line_end()

        # Capture offset bounds immediately so we compare ints, not iterators.
        # This prevents stale-iterator warnings if the buffer is modified
        # between consecutive iterator operations.
        vis_end_offset = vis_end.get_offset()

        btwc = self.buffer_to_window_coords
        tags_and_colors = []
        if error_tag:
            tags_and_colors.append((error_tag, self._diag_error_wave_rgba))
        if warning_tag:
            tags_and_colors.append((warning_tag, self._diag_warning_wave_rgba))

        for tag, color in tags_and_colors:
            it = vis_start.copy()
            while it.get_offset() <= vis_end_offset:
                if not it.has_tag(tag):
                    if not it.forward_to_tag_toggle(tag):
                        break
                    if it.get_offset() > vis_end_offset:
                        break
                    if not it.has_tag(tag):
                        continue

                range_start = it.copy()
                if not it.forward_to_tag_toggle(tag):
                    it = buf.get_iter_at_offset(vis_end_offset)
                range_end = it.copy()

                # Use pre-built set of fold-unsafe lines — includes fold
                # headers (invisible tag starts at their end) and hidden lines.
                hidden = self._fold_unsafe_lines

                # Draw line by line within the tagged range
                ls = range_start.copy()
                range_end_offset = range_end.get_offset()
                while ls.get_offset() < range_end_offset:
                    cur_line = ls.get_line()

                    # Skip lines hidden by fold — Pango layout is invalid
                    if cur_line in hidden:
                        next_it = _iter_at_line(buf, cur_line + 1)
                        if next_it.get_line() == cur_line:
                            break
                        ls = next_it
                        continue

                    le = range_end.copy()
                    if le.get_line() > cur_line:
                        le = _iter_at_line(buf, cur_line)
                        if not le.ends_line():
                            le.forward_to_line_end()

                    # Re-create iters from character offsets so internal
                    # byte indices are guaranteed fresh.
                    ls_fresh = _iter_at_offset(buf, ls.get_offset())
                    le_fresh = _iter_at_offset(buf, le.get_offset())

                    sr = self.get_iter_location(ls_fresh)
                    er = self.get_iter_location(le_fresh)
                    sx, sy = btwc(Gtk.TextWindowType.WIDGET, sr.x, sr.y)
                    ex, _ = btwc(Gtk.TextWindowType.WIDGET, er.x, 0)
                    wave_y = sy + sr.height + 1
                    wave_w = ex - sx

                    if wave_w > 0:
                        self._draw_wavy_line(snapshot, sx, wave_y, wave_w, color)

                    next_it = _iter_at_line(buf, cur_line + 1)
                    if next_it.get_line() == cur_line:
                        break
                    ls = next_it

    @staticmethod
    def _draw_wavy_line(snapshot, x, y, width, color):
        """Draw a smooth wavy/squiggly line using GskPathBuilder."""
        from gi.repository import Gdk, Gsk

        r, g, b, a = color
        step = 4.0  # half-wavelength in pixels
        amplitude = 2.5

        builder = Gsk.PathBuilder.new()
        builder.move_to(x, y)
        pos_x = x
        pos_y = y
        i = 0.0
        going_up = True
        while i < width:
            seg = min(step, width - i)
            dy = -amplitude if going_up else amplitude
            pos_x += seg
            pos_y += dy
            builder.line_to(pos_x, pos_y)
            going_up = not going_up
            i += seg

        path = builder.to_path()
        stroke = Gsk.Stroke.new(1.8)

        wave_color = Gdk.RGBA()
        wave_color.red, wave_color.green, wave_color.blue, wave_color.alpha = r, g, b, a
        snapshot.append_stroke(path, stroke, wave_color)

    def _draw_indent_guides_snapshot(self, snapshot):
        """Draw indent guides using GTK4 snapshot.append_color.

        Optimisations vs. the naïve per-line-per-column approach:
        1. X coordinates are pre-computed once per guide column, not per line.
        2. Consecutive visible lines at the same column are merged into a
           single tall rectangle, cutting append_color calls ~3-5×.
        3. The Gdk.RGBA colour object is cached on the instance (not
           allocated every frame).
        """
        buf = self.get_buffer()
        lang = buf.get_language() if hasattr(buf, "get_language") else None
        if lang is None or lang.get_id() in NO_INDENT_GUIDE_LANGS:
            return

        tab_w = self.get_tab_width()
        metrics = self.get_pango_context().get_metrics(None, None)
        char_w = metrics.get_approximate_char_width() / Pango.SCALE

        indent_step = self._compute_indent_step(buf, tab_w)
        indent_px = char_w * indent_step
        if indent_px <= 0:
            return

        # Recompute guide levels only when buffer content changed
        if self._guide_levels_dirty or self._cached_guide_levels is None:
            lang_id = lang.get_id() if lang else None
            start_it = buf.get_start_iter()
            end_it = buf.get_end_iter()
            all_text = buf.get_text(start_it, end_it, True)
            text_lines = all_text.split("\n")
            from editor.indent_guide_levels import compute_guide_levels

            self._cached_guide_levels = compute_guide_levels(text_lines, indent_step, tab_w, lang_id)
            self._guide_levels_dirty = False

        levels = self._cached_guide_levels

        # Visible line range
        visible = self.get_visible_rect()
        start_it, _ = self.get_line_at_y(visible.y)
        end_it, _ = self.get_line_at_y(visible.y + visible.height)
        start_ln = start_it.get_line()
        end_ln = end_it.get_line()

        if end_ln < start_ln or not levels:
            return

        btwc = self.buffer_to_window_coords
        fold_unsafe = getattr(self, "_fold_unsafe_lines", set())

        # Find a safe line for padding_x measurement
        pad_ln = start_ln
        while pad_ln in fold_unsafe and pad_ln <= end_ln:
            pad_ln += 1
        if pad_ln > end_ln:
            return
        pad_it = _iter_at_line(buf, pad_ln)
        padding_x = self.get_iter_location(pad_it).x

        # Selected line range — skip guides on selected lines
        sel_start_ln = sel_end_ln = -1
        if buf.get_has_selection():
            sel_s, sel_e = buf.get_selection_bounds()
            sel_start_ln = sel_s.get_line()
            sel_end_ln = sel_e.get_line()

        # Collect per-line y/height for visible lines (one GTK call each)
        n_levels = len(levels)
        line_y = [0] * (end_ln - start_ln + 1)
        line_h = [0] * (end_ln - start_ln + 1)
        line_lvl = [0] * (end_ln - start_ln + 1)
        for i, ln in enumerate(range(start_ln, end_ln + 1)):
            if ln >= n_levels:
                break
            lvl = levels[ln]
            if lvl <= 0 or sel_start_ln <= ln <= sel_end_ln or ln in fold_unsafe:
                line_lvl[i] = 0
                continue
            it = _iter_at_line(buf, ln)
            loc = self.get_iter_location(it)
            _, wy = btwc(Gtk.TextWindowType.WIDGET, 0, loc.y)
            line_y[i] = wy
            line_h[i] = loc.height
            line_lvl[i] = lvl

        # Determine max guide columns needed
        max_lvl = max(line_lvl) if line_lvl else 0
        if max_lvl <= 0:
            return

        # Pre-compute window X for each guide column once
        col_x = [0] * max_lvl
        for g in range(max_lvl):
            bx = padding_x + int(indent_px * g)
            col_x[g], _ = btwc(Gtk.TextWindowType.WIDGET, bx, 0)

        color = self._guide_color
        guide_rect = Graphene.Rect()
        n_lines = end_ln - start_ln + 1

        # Draw merged vertical spans per guide column
        for g in range(max_lvl):
            wx = col_x[g]
            span_start = -1
            span_y = 0
            span_bottom = 0
            for i in range(n_lines):
                if line_lvl[i] > g:
                    if span_start < 0:
                        span_start = i
                        span_y = line_y[i]
                    span_bottom = line_y[i] + line_h[i]
                else:
                    if span_start >= 0:
                        guide_rect.init(wx, span_y, 1, span_bottom - span_y)
                        snapshot.append_color(color, guide_rect)
                        span_start = -1
            if span_start >= 0:
                guide_rect.init(wx, span_y, 1, span_bottom - span_y)
                snapshot.append_color(color, guide_rect)
