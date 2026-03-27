"""Heading, paragraph, list, blockquote, code-block, and collapsible rendering mixin.

Contains Pango layout creation and GtkSnapshot draw calls for text-based blocks.
"""

from __future__ import annotations

import re

from gi.repository import Graphene, Pango

from editor.preview.content_block import ContentBlock, InlineSpan
from shared.utils import hex_to_gdk_rgba

# Emoji detection for adding visual spacing in rendered text
_EMOJI_RE = re.compile(
    "(["
    "\u2600-\u27bf"  # Misc symbols & dingbats
    "\U0001f300-\U0001f9ff"  # Emoticons, symbols, transport, supplemental
    "\U0001fa00-\U0001faff"  # Extended symbols
    "][\ufe0e\ufe0f]?)"  # Optional variation selector
)


def _add_emoji_spacing(text: str) -> str:
    """Insert a thin space after emoji characters for visual breathing room."""
    return _EMOJI_RE.sub(lambda m: m.group(0) + "\u2009", text)


class TextRendererMixin:
    """Mixin for rendering text-based blocks (headings, paragraphs, lists, etc.)."""

    def _draw_heading(self, snapshot, pango_ctx, block: ContentBlock, width: float):
        scale = self.HEADING_SCALES.get(block.level, 1.0)
        font_size = int(self._base_font_size * scale * self._zoom_level)

        desc = self._font_desc.copy()
        desc.set_size(font_size * Pango.SCALE)
        desc.set_weight(Pango.Weight.BOLD)

        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(desc)
        layout.set_width(int((width - self.PAD_LEFT - self.PAD_RIGHT) * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)

        text, attrs = self._spans_to_pango(block.spans, desc)
        layout.set_text(text, -1)
        if attrs:
            layout.set_attributes(attrs)

        point = Graphene.Point()
        point.init(self.PAD_LEFT, block._y_offset)
        snapshot.save()
        snapshot.translate(point)
        snapshot.append_layout(layout, self._fg_rgba)
        snapshot.restore()

        self._text_regions.append((layout, self.PAD_LEFT + self._draw_x_offset, block._y_offset))

        # Bottom border for h1 and h2
        if block.level <= 2:
            border_y = block._y_offset + block._height - 4
            border_rect = Graphene.Rect()
            border_rect.init(self.PAD_LEFT, border_y, width - self.PAD_LEFT - self.PAD_RIGHT, 1)
            snapshot.append_color(self._border_rgba, border_rect)

    def _draw_paragraph(self, snapshot, pango_ctx, block: ContentBlock, width: float):
        desc = self._scaled_font_desc()
        text_x = self.PAD_LEFT

        # Draw badge if present (e.g. status code on non-collapsible response)
        if block.badge_text and block.badge_color:
            badge_desc = self._scaled_font_desc()
            badge_font_size = max(int((self._base_font_size - 2) * self._zoom_level), 8)
            badge_desc.set_size(badge_font_size * Pango.SCALE)
            badge_desc.set_weight(Pango.Weight.BOLD)

            badge_layout = Pango.Layout.new(pango_ctx)
            badge_layout.set_font_description(badge_desc)
            badge_layout.set_text(block.badge_text, -1)
            _, badge_logical = badge_layout.get_pixel_extents()

            badge_pad_x = 6
            badge_pad_y = 2
            badge_w = badge_logical.width + badge_pad_x * 2
            badge_h = badge_logical.height + badge_pad_y * 2
            badge_y = block._y_offset + 1

            badge_rgba = hex_to_gdk_rgba(block.badge_color)
            badge_rect = Graphene.Rect()
            badge_rect.init(text_x, badge_y, badge_w, badge_h)
            snapshot.append_color(badge_rgba, badge_rect)

            white_rgba = hex_to_gdk_rgba("#ffffff")
            point = Graphene.Point()
            point.init(text_x + badge_pad_x, badge_y + badge_pad_y)
            snapshot.save()
            snapshot.translate(point)
            snapshot.append_layout(badge_layout, white_rgba)
            snapshot.restore()

            text_x += badge_w + 8

        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(desc)
        layout.set_width(int((width - text_x - self.PAD_RIGHT) * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_spacing(int(self.LINE_SPACING * Pango.SCALE))

        text, attrs = self._spans_to_pango(block.spans, desc)
        layout.set_text(text, -1)
        if attrs:
            layout.set_attributes(attrs)

        point = Graphene.Point()
        point.init(text_x, block._y_offset)
        snapshot.save()
        snapshot.translate(point)
        snapshot.append_layout(layout, self._fg_rgba)
        snapshot.restore()

        self._text_regions.append((layout, text_x + self._draw_x_offset, block._y_offset))

    def _draw_code_block(self, snapshot, pango_ctx, block: ContentBlock, width: float):
        # Background rect
        code_x = self.PAD_LEFT
        code_w = width - self.PAD_LEFT - self.PAD_RIGHT
        bg_rect = Graphene.Rect()
        bg_rect.init(code_x, block._y_offset, code_w, block._height)
        snapshot.append_color(self._code_bg_rgba, bg_rect)

        # Rounded corners via border
        border_rect = Graphene.Rect()
        border_rect.init(code_x, block._y_offset, code_w, 1)
        snapshot.append_color(self._border_rgba, border_rect)
        border_rect.init(code_x, block._y_offset + block._height - 1, code_w, 1)
        snapshot.append_color(self._border_rgba, border_rect)

        # Language label
        text_y = block._y_offset + self.CODE_PAD
        if block.language:
            lang_desc = self._mono_font_desc.copy()
            lang_size = max(int((self._base_font_size - 2) * self._zoom_level), 8)
            lang_desc.set_size(lang_size * Pango.SCALE)
            lang_layout = Pango.Layout.new(pango_ctx)
            lang_layout.set_font_description(lang_desc)
            lang_layout.set_text(block.language, -1)

            point = Graphene.Point()
            point.init(code_x + self.CODE_PAD, text_y)
            snapshot.save()
            snapshot.translate(point)
            snapshot.append_layout(lang_layout, self._dim_rgba)
            snapshot.restore()

            _, logical = lang_layout.get_pixel_extents()
            text_y += logical.height + 4

        # Code text
        desc = self._scaled_mono_desc()
        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(desc)
        layout.set_width(int((code_w - self.CODE_PAD * 2) * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.CHAR)
        layout.set_text(block.code, -1)

        point = Graphene.Point()
        point.init(code_x + self.CODE_PAD, text_y)
        snapshot.save()
        snapshot.translate(point)
        snapshot.append_layout(layout, self._fg_rgba)
        snapshot.restore()

        self._text_regions.append((layout, code_x + self.CODE_PAD + self._draw_x_offset, text_y))

    def _draw_list(self, snapshot, pango_ctx, block: ContentBlock, width: float):
        desc = self._scaled_font_desc()
        indent = 20
        y = block._y_offset

        for i, item_spans in enumerate(block.items):
            bullet = f"{i + 1}." if block.ordered else "\u25aa"

            # Bullet
            bullet_layout = Pango.Layout.new(pango_ctx)
            bullet_layout.set_font_description(desc)
            bullet_layout.set_text(bullet, -1)

            point = Graphene.Point()
            point.init(self.PAD_LEFT, y)
            snapshot.save()
            snapshot.translate(point)
            snapshot.append_layout(bullet_layout, self._dim_rgba)
            snapshot.restore()

            # Item text
            layout = Pango.Layout.new(pango_ctx)
            layout.set_font_description(desc)
            layout.set_width(int((width - self.PAD_LEFT - self.PAD_RIGHT - indent) * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_spacing(int(self.LINE_SPACING * Pango.SCALE))

            text, attrs = self._spans_to_pango(item_spans, desc)
            layout.set_text(text, -1)
            if attrs:
                layout.set_attributes(attrs)

            point = Graphene.Point()
            point.init(self.PAD_LEFT + indent, y)
            snapshot.save()
            snapshot.translate(point)
            snapshot.append_layout(layout, self._fg_rgba)
            snapshot.restore()

            self._text_regions.append((layout, self.PAD_LEFT + indent + self._draw_x_offset, y))

            _, logical = layout.get_pixel_extents()
            y += max(logical.height, self._line_height) + 4

    def _draw_blockquote(self, snapshot, pango_ctx, block: ContentBlock, width: float):
        # Left accent bar
        bar_rect = Graphene.Rect()
        bar_rect.init(
            self.PAD_LEFT,
            block._y_offset,
            self.QUOTE_BAR_WIDTH,
            block._height,
        )
        snapshot.append_color(self._accent_rgba, bar_rect)

        # Render children with indent
        desc = self._scaled_font_desc()
        desc.set_style(Pango.Style.ITALIC)
        y = block._y_offset

        for child in block.children:
            text, attrs = self._spans_to_pango(child.spans, desc)
            if not text:
                y += self._line_height * 0.5
                continue

            layout = Pango.Layout.new(pango_ctx)
            layout.set_font_description(desc)
            layout.set_width(int((width - self.PAD_LEFT - self.PAD_RIGHT - self.QUOTE_INDENT) * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_text(text, -1)
            if attrs:
                layout.set_attributes(attrs)

            point = Graphene.Point()
            point.init(self.PAD_LEFT + self.QUOTE_INDENT, y)
            snapshot.save()
            snapshot.translate(point)
            snapshot.append_layout(layout, self._dim_rgba)
            snapshot.restore()

            self._text_regions.append((layout, self.PAD_LEFT + self.QUOTE_INDENT + self._draw_x_offset, y))

            _, logical = layout.get_pixel_extents()
            y += logical.height + self.BLOCK_SPACING

    def _draw_hr(self, snapshot, block: ContentBlock, width: float):
        hr_y = block._y_offset + block._height / 2
        hr_rect = Graphene.Rect()
        hr_rect.init(self.PAD_LEFT, hr_y, width - self.PAD_LEFT - self.PAD_RIGHT, 1)
        snapshot.append_color(self._border_rgba, hr_rect)

    def _draw_collapsible(
        self, snapshot, pango_ctx, block: ContentBlock, width: float, scroll_y: float = 0.0, visible_height: float = 1e9
    ):
        """Draw a collapsible section: optional badge + chevron + header, then children if expanded."""
        chevron = "\u25b6 " if block.collapsed else "\u25bc "
        desc = self._scaled_font_desc()
        desc.set_weight(Pango.Weight.BOLD)

        avail_w = width - self.PAD_LEFT - self.PAD_RIGHT
        text_x = self.PAD_LEFT
        badge_w = 0.0

        # Draw colored left border only when expanded (starts below header)
        if block.border_color and not block.collapsed:
            header_h = getattr(block, "_header_height", 0)
            bar_y = block._y_offset + header_h
            bar_h = block._height - header_h
            if bar_h > 0:
                border_rgba = hex_to_gdk_rgba(block.border_color)
                border_rect = Graphene.Rect()
                border_rect.init(self.PAD_LEFT, bar_y, 3, bar_h)
                snapshot.append_color(border_rgba, border_rect)

        # Draw badge (e.g. HTTP method) if present
        if block.badge_text and block.badge_color:
            badge_desc = self._scaled_font_desc()
            badge_font_size = max(int((self._base_font_size - 2) * self._zoom_level), 8)
            badge_desc.set_size(badge_font_size * Pango.SCALE)
            badge_desc.set_weight(Pango.Weight.BOLD)

            badge_layout = Pango.Layout.new(pango_ctx)
            badge_layout.set_font_description(badge_desc)
            badge_layout.set_text(block.badge_text, -1)
            _, badge_logical = badge_layout.get_pixel_extents()

            badge_pad_x = 6
            badge_pad_y = 2
            badge_w = badge_logical.width + badge_pad_x * 2
            badge_h = badge_logical.height + badge_pad_y * 2
            badge_y = block._y_offset + 1

            # Badge background
            badge_rgba = hex_to_gdk_rgba(block.badge_color)
            badge_rect = Graphene.Rect()
            badge_rect.init(text_x, badge_y, badge_w, badge_h)
            snapshot.append_color(badge_rgba, badge_rect)

            # Badge text (white)
            white_rgba = hex_to_gdk_rgba("#ffffff")
            point = Graphene.Point()
            point.init(text_x + badge_pad_x, badge_y + badge_pad_y)
            snapshot.save()
            snapshot.translate(point)
            snapshot.append_layout(badge_layout, white_rgba)
            snapshot.restore()

            text_x += badge_w + 8

        # Header text with chevron
        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(desc)
        layout.set_width(int((avail_w - badge_w - 8) * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)

        text, attrs = self._spans_to_pango(block.spans, desc)
        layout.set_text(chevron + text, -1)

        # Apply attrs shifted by chevron length
        if attrs and text:
            shifted = Pango.AttrList()
            chevron_bytes = len(chevron.encode("utf-8"))
            it = attrs.get_iterator()
            while True:
                a_range = it.get_attrs()
                for a in a_range:
                    a.start_index += chevron_bytes
                    a.end_index += chevron_bytes
                    shifted.insert(a)
                if not it.next():
                    break
            # Bold the chevron
            chev_attr = Pango.attr_weight_new(Pango.Weight.BOLD)
            chev_attr.start_index = 0
            chev_attr.end_index = chevron_bytes
            shifted.insert(chev_attr)
            layout.set_attributes(shifted)

        point = Graphene.Point()
        point.init(text_x, block._y_offset)
        snapshot.save()
        snapshot.translate(point)
        snapshot.append_layout(layout, self._fg_rgba)
        snapshot.restore()

        self._text_regions.append((layout, text_x + self._draw_x_offset, block._y_offset))

        # Draw children if expanded
        if not block.collapsed and block.children:
            # Indent children past the vertical border bar
            if block.border_color:
                shift = Graphene.Point()
                shift.init(10, 0)
                snapshot.save()
                snapshot.translate(shift)
                self._draw_x_offset += 10
            for child in block.children:
                self._draw_block(
                    snapshot, pango_ctx, child, width - 10 if block.border_color else width, scroll_y, visible_height
                )
            if block.border_color:
                snapshot.restore()
                self._draw_x_offset -= 10
        # Draw inline code content for collapsible code blocks with no children
        elif not block.collapsed and block.code:
            saved_offset = block._y_offset
            saved_height = block._height
            block._y_offset = getattr(block, "_code_y_offset", saved_offset + block._header_height + self.BLOCK_SPACING)
            block._height = getattr(block, "_code_height", saved_height - block._header_height)
            self._draw_code_block(snapshot, pango_ctx, block, width)
            block._y_offset = saved_offset
            block._height = saved_height

    # ------------------------------------------------------------------ #
    #  Pango helpers                                                       #
    # ------------------------------------------------------------------ #

    def _spans_to_pango(self, spans: list[InlineSpan], base_desc: Pango.FontDescription):
        """Convert InlineSpans to a Pango text string + AttrList."""
        if not spans:
            return "", None

        text_parts = []
        attrs = Pango.AttrList()

        for span in spans:
            text = _add_emoji_spacing(span.text)
            byte_start = len("".join(text_parts).encode("utf-8"))
            text_parts.append(text)
            byte_end = len("".join(text_parts).encode("utf-8"))

            if span.bold:
                attr = Pango.attr_weight_new(Pango.Weight.BOLD)
                attr.start_index = byte_start
                attr.end_index = byte_end
                attrs.insert(attr)

            if span.italic:
                attr = Pango.attr_style_new(Pango.Style.ITALIC)
                attr.start_index = byte_start
                attr.end_index = byte_end
                attrs.insert(attr)

            if span.code:
                from fonts import get_font_settings as _get_font_settings

                _editor = _get_font_settings("editor")
                attr = Pango.attr_family_new(_editor["family"])
                attr.start_index = byte_start
                attr.end_index = byte_end
                attrs.insert(attr)
                # Subtle background via foreground color change
                attr = Pango.attr_foreground_new(
                    int(self._accent_rgba.red * 65535),
                    int(self._accent_rgba.green * 65535),
                    int(self._accent_rgba.blue * 65535),
                )
                attr.start_index = byte_start
                attr.end_index = byte_end
                attrs.insert(attr)

            if span.strikethrough:
                attr = Pango.attr_strikethrough_new(True)
                attr.start_index = byte_start
                attr.end_index = byte_end
                attrs.insert(attr)

            if span.link_url:
                attr = Pango.attr_underline_new(Pango.Underline.SINGLE)
                attr.start_index = byte_start
                attr.end_index = byte_end
                attrs.insert(attr)
                attr = Pango.attr_foreground_new(
                    int(self._accent_rgba.red * 65535),
                    int(self._accent_rgba.green * 65535),
                    int(self._accent_rgba.blue * 65535),
                )
                attr.start_index = byte_start
                attr.end_index = byte_end
                attrs.insert(attr)

        full_text = "".join(text_parts)
        return (full_text, attrs) if full_text else (full_text, None)

    def _scaled_font_desc(self) -> Pango.FontDescription:
        """Return the base font desc scaled by zoom level."""
        desc = self._font_desc.copy()
        desc.set_size(int(self._base_font_size * self._zoom_level * Pango.SCALE))
        return desc

    def _scaled_mono_desc(self) -> Pango.FontDescription:
        """Return monospace font desc scaled by zoom level."""
        desc = self._mono_font_desc.copy()
        size = max(int((self._base_font_size - 1) * self._zoom_level), 8)
        desc.set_size(size * Pango.SCALE)
        return desc
