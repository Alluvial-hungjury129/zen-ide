"""Table layout and rendering mixin for MarkdownCanvas."""

from __future__ import annotations

from gi.repository import Graphene, Pango

from editor.preview.content_block import ContentBlock


class TableRendererMixin:
    """Mixin for table drawing and measurement."""

    @staticmethod
    def _table_col_widths(headers: list[str] | None, num_cols: int, avail_w: float) -> list[float]:
        """Compute per-column widths giving priority to Name and Description."""
        _WEIGHT = {"name": 3, "description": 5}
        if headers and len(headers) == num_cols:
            weights = [_WEIGHT.get(h.lower(), 1) for h in headers]
        else:
            weights = [1] * num_cols
        total = sum(weights)
        return [(w / total) * avail_w for w in weights]

    def _draw_table(self, snapshot, pango_ctx, block: ContentBlock, width: float):
        if not block.headers and not block.rows:
            return

        desc = self._scaled_font_desc()
        all_rows = [block.headers] + block.rows if block.headers else block.rows
        all_span_rows = [block.header_spans] + block.row_spans if block.header_spans else block.row_spans
        num_cols = max(len(row) for row in all_rows) if all_rows else 0
        if num_cols == 0:
            return

        avail_w = width - self.PAD_LEFT - self.PAD_RIGHT
        col_widths = self._table_col_widths(block.headers, num_cols, avail_w)
        row_heights = block._row_heights if block._row_heights else None
        if not row_heights:
            fallback_h = self._line_height * self._zoom_level + 8
            row_heights = [fallback_h] * len(all_rows)

        table_y = block._y_offset
        table_h = sum(row_heights[: len(all_rows)])
        border_r = Graphene.Rect()

        # Top border of entire table
        border_r.init(self.PAD_LEFT, table_y, avail_w, 1)
        snapshot.append_color(self._border_rgba, border_r)

        y = table_y
        for row_idx, row in enumerate(all_rows):
            row_h = row_heights[row_idx] if row_idx < len(row_heights) else (self._line_height * self._zoom_level + 8)
            x = self.PAD_LEFT
            span_row = all_span_rows[row_idx] if row_idx < len(all_span_rows) else None
            for col_idx in range(num_cols):
                cell_text = row[col_idx] if col_idx < len(row) else ""

                layout = Pango.Layout.new(pango_ctx)
                if row_idx == 0 and block.headers:
                    bold_desc = desc.copy()
                    bold_desc.set_weight(Pango.Weight.BOLD)
                    layout.set_font_description(bold_desc)
                else:
                    layout.set_font_description(desc)
                cw = col_widths[col_idx] if col_idx < len(col_widths) else col_widths[-1]
                layout.set_width(int((cw - 12) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)

                cell_spans = span_row[col_idx] if span_row and col_idx < len(span_row) else None
                if cell_spans:
                    text, attrs = self._spans_to_pango(cell_spans, desc)
                    layout.set_text(text, -1)
                    if attrs:
                        layout.set_attributes(attrs)
                else:
                    layout.set_text(cell_text, -1)

                point = Graphene.Point()
                point.init(x + 6, y + 4)
                snapshot.save()
                snapshot.translate(point)
                snapshot.append_layout(layout, self._fg_rgba)
                snapshot.restore()

                self._text_regions.append((layout, x + 6 + self._draw_x_offset, y + 4))

                x += cw

            # Horizontal border below every row
            border_r.init(self.PAD_LEFT, y + row_h - 1, avail_w, 1)
            snapshot.append_color(self._border_rgba, border_r)

            y += row_h

        # Vertical borders between columns (and left/right edges)
        col_x = self.PAD_LEFT
        for col_idx in range(num_cols + 1):
            border_r.init(col_x, table_y, 1, table_h)
            snapshot.append_color(self._border_rgba, border_r)
            if col_idx < num_cols:
                col_x += col_widths[col_idx] if col_idx < len(col_widths) else col_widths[-1]

    def _measure_table(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        all_rows = [block.headers] + block.rows if block.headers else block.rows
        all_span_rows = [block.header_spans] + block.row_spans if block.header_spans else block.row_spans
        if not all_rows:
            return self._line_height
        num_cols = max(len(row) for row in all_rows) if all_rows else 0
        if num_cols == 0:
            return self._line_height
        col_widths = self._table_col_widths(block.headers, num_cols, content_width)
        desc = self._scaled_font_desc()
        # Measure each row's height based on content
        row_heights = []
        for row_idx, row in enumerate(all_rows):
            max_h = self._line_height * self._zoom_level + 8
            span_row = all_span_rows[row_idx] if row_idx < len(all_span_rows) else None
            for col_idx in range(num_cols):
                cell_text = row[col_idx] if col_idx < len(row) else ""
                if cell_text:
                    cw = col_widths[col_idx] if col_idx < len(col_widths) else col_widths[-1]
                    layout = Pango.Layout.new(pango_ctx)
                    layout.set_font_description(desc)
                    layout.set_width(int((cw - 12) * Pango.SCALE))
                    layout.set_wrap(Pango.WrapMode.WORD_CHAR)

                    cell_spans = span_row[col_idx] if span_row and col_idx < len(span_row) else None
                    if cell_spans:
                        text, attrs = self._spans_to_pango(cell_spans, desc)
                        layout.set_text(text, -1)
                        if attrs:
                            layout.set_attributes(attrs)
                    else:
                        layout.set_text(cell_text, -1)

                    _, logical = layout.get_pixel_extents()
                    max_h = max(max_h, logical.height + 8)
            row_heights.append(max_h)
        block._row_heights = row_heights
        return sum(row_heights)
