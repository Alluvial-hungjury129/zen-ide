"""Block positioning and measurement mixin for MarkdownCanvas."""

from __future__ import annotations

from gi.repository import Pango

from editor.preview.content_block import ContentBlock


class BlockLayoutMixin:
    """Mixin providing block layout (measurement and Y-offset computation)."""

    def _layout_blocks(self, content_width: float):
        """Measure all blocks and compute cumulative Y offsets."""
        self._layout_width = content_width
        pango_ctx = self.get_pango_context()
        if pango_ctx is None:
            return

        y = float(self.PAD_TOP)
        for i, block in enumerate(self._blocks):
            # Extra top margin before headings (skip for the first block)
            if block.kind == "heading" and i > 0:
                extra_top = self.HEADING_MARGIN_TOP.get(block.level, 14)
                y += extra_top

            block._y_offset = y
            h = self._measure_block(pango_ctx, block, content_width)
            block._height = h
            y += h + self.BLOCK_SPACING

            # Extra bottom margin after headings
            if block.kind == "heading":
                y += self.HEADING_MARGIN_BOTTOM.get(block.level, 4)

        # Set total content height
        total = y + self.PAD_TOP
        self.set_size_request(-1, max(int(total), 100))
        self._needs_layout = False

    def _measure_block(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        """Return the pixel height of a single block."""
        if block.collapsible:
            return self._measure_collapsible(pango_ctx, block, content_width)
        elif block.kind == "heading":
            return self._measure_heading(pango_ctx, block, content_width)
        elif block.kind == "paragraph":
            return self._measure_paragraph(pango_ctx, block, content_width)
        elif block.kind == "code":
            return self._measure_code(pango_ctx, block, content_width)
        elif block.kind == "table":
            return self._measure_table(pango_ctx, block, content_width)
        elif block.kind == "list":
            return self._measure_list(pango_ctx, block, content_width)
        elif block.kind == "blockquote":
            return self._measure_blockquote(pango_ctx, block, content_width)
        elif block.kind == "hr":
            return 16
        elif block.kind == "image":
            return self._measure_image(pango_ctx, block, content_width)
        elif block.kind == "image_row":
            return self._measure_image_row(pango_ctx, block, content_width)
        return self._line_height

    def _measure_heading(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        scale = self.HEADING_SCALES.get(block.level, 1.0)
        font_size = int(self._base_font_size * scale * self._zoom_level)

        desc = self._font_desc.copy()
        desc.set_size(font_size * Pango.SCALE)
        desc.set_weight(Pango.Weight.BOLD)

        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(desc)
        layout.set_width(int(content_width * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)

        text, attrs = self._spans_to_pango(block.spans, desc)
        layout.set_text(text, -1)
        if attrs:
            layout.set_attributes(attrs)

        _, logical = layout.get_pixel_extents()
        extra = 8 if block.level <= 2 else 4  # bottom border space for h1/h2
        return logical.height + extra

    def _measure_collapsible(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        """Measure a collapsible block: header + children if expanded."""
        desc = self._scaled_font_desc()
        desc.set_weight(Pango.Weight.BOLD)

        # Account for badge width if present
        badge_w = 0.0
        if block.badge_text and block.badge_color:
            badge_desc = self._scaled_font_desc()
            badge_font_size = max(int((self._base_font_size - 2) * self._zoom_level), 8)
            badge_desc.set_size(badge_font_size * Pango.SCALE)
            badge_desc.set_weight(Pango.Weight.BOLD)
            badge_layout = Pango.Layout.new(pango_ctx)
            badge_layout.set_font_description(badge_desc)
            badge_layout.set_text(block.badge_text, -1)
            _, badge_logical = badge_layout.get_pixel_extents()
            badge_w = badge_logical.width + 12 + 8  # pad_x*2 + gap

        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(desc)
        layout.set_width(int((content_width - badge_w) * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)

        chevron = "\u25b6 " if block.collapsed else "\u25bc "
        text, _ = self._spans_to_pango(block.spans, desc)
        layout.set_text(chevron + text, -1)

        _, logical = layout.get_pixel_extents()
        header_h = logical.height + 4
        # If badge is taller, use badge height
        if block.badge_text and block.badge_color:
            badge_h = max(int((self._base_font_size - 2) * self._zoom_level), 8) + 4 + 2
            header_h = max(header_h, badge_h + 4)
        block._header_height = header_h

        if block.collapsed:
            return header_h

        # Collapsible code block with no children -- content lives in block.code
        if not block.children and block.code:
            code_y = block._y_offset + header_h + self.BLOCK_SPACING
            code_h = self._measure_code(pango_ctx, block, content_width)
            block._code_y_offset = code_y
            block._code_height = code_h
            return header_h + self.BLOCK_SPACING + code_h + self.BLOCK_SPACING

        if not block.children:
            return header_h

        # Layout children with absolute y positions
        child_content_w = content_width - 10 if block.border_color else content_width
        child_y = block._y_offset + header_h + self.BLOCK_SPACING
        for i, child in enumerate(block.children):
            if child.kind == "heading" and i > 0:
                extra_top = self.HEADING_MARGIN_TOP.get(child.level, 14)
                child_y += extra_top
            child._y_offset = child_y
            child_h = self._measure_block(pango_ctx, child, child_content_w)
            child._height = child_h
            child_y += child_h + self.BLOCK_SPACING

            # Extra bottom margin after headings
            if child.kind == "heading":
                child_y += self.HEADING_MARGIN_BOTTOM.get(child.level, 4)

        return child_y - block._y_offset

    def _measure_paragraph(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        desc = self._scaled_font_desc()

        badge_w = 0.0
        if block.badge_text and block.badge_color:
            badge_desc = self._scaled_font_desc()
            badge_font_size = max(int((self._base_font_size - 2) * self._zoom_level), 8)
            badge_desc.set_size(badge_font_size * Pango.SCALE)
            badge_desc.set_weight(Pango.Weight.BOLD)
            badge_layout = Pango.Layout.new(pango_ctx)
            badge_layout.set_font_description(badge_desc)
            badge_layout.set_text(block.badge_text, -1)
            _, badge_logical = badge_layout.get_pixel_extents()
            badge_w = badge_logical.width + 12 + 8

        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(desc)
        layout.set_width(int((content_width - badge_w) * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_spacing(int(self.LINE_SPACING * Pango.SCALE))

        text, attrs = self._spans_to_pango(block.spans, desc)
        layout.set_text(text, -1)
        if attrs:
            layout.set_attributes(attrs)

        _, logical = layout.get_pixel_extents()
        h = logical.height
        if block.badge_text and block.badge_color:
            badge_h = max(int((self._base_font_size - 2) * self._zoom_level), 8) + 4 + 2
            h = max(h, badge_h)
        return h

    def _measure_code(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        desc = self._scaled_mono_desc()
        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(desc)
        layout.set_width(int((content_width - self.CODE_PAD * 2) * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.CHAR)
        layout.set_text(block.code, -1)

        _, logical = layout.get_pixel_extents()
        h = logical.height + self.CODE_PAD * 2

        # Add language label height
        if block.language:
            lang_desc = self._mono_font_desc.copy()
            lang_size = max(int((self._base_font_size - 2) * self._zoom_level), 8)
            lang_desc.set_size(lang_size * Pango.SCALE)
            lang_layout = Pango.Layout.new(pango_ctx)
            lang_layout.set_font_description(lang_desc)
            lang_layout.set_text(block.language, -1)
            _, lang_logical = lang_layout.get_pixel_extents()
            h += lang_logical.height + 4

        return h

    def _measure_list(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        desc = self._scaled_font_desc()
        indent = 20
        total = 0.0

        for item_spans in block.items:
            layout = Pango.Layout.new(pango_ctx)
            layout.set_font_description(desc)
            layout.set_width(int((content_width - indent) * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_spacing(int(self.LINE_SPACING * Pango.SCALE))

            text, attrs = self._spans_to_pango(item_spans, desc)
            layout.set_text(text, -1)
            if attrs:
                layout.set_attributes(attrs)

            _, logical = layout.get_pixel_extents()
            total += max(logical.height, self._line_height) + 4

        return total

    def _measure_blockquote(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        desc = self._scaled_font_desc()
        desc.set_style(Pango.Style.ITALIC)
        total = 0.0

        for child in block.children:
            text, attrs = self._spans_to_pango(child.spans, desc)
            if not text:
                total += self._line_height * 0.5
                continue

            layout = Pango.Layout.new(pango_ctx)
            layout.set_font_description(desc)
            layout.set_width(int((content_width - self.QUOTE_INDENT) * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_text(text, -1)
            if attrs:
                layout.set_attributes(attrs)

            _, logical = layout.get_pixel_extents()
            total += logical.height + self.BLOCK_SPACING

        return max(total, self._line_height)
