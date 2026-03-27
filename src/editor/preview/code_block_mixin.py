"""Code block and inline formatting mixin for MarkdownBlockRenderer.

Provides code fence parsing and inline markdown formatting
(bold, italic, code, links, images, strikethrough) parsing.
"""

from __future__ import annotations

from editor.preview.content_block import InlineSpan


class CodeBlockMixin:
    """Mixin providing code block and inline parsing for MarkdownBlockRenderer.

    Expects the host class to define the compiled regex class attributes:
    - _LINKED_IMAGE_RE, _IMAGE_RE, _LINK_RE
    - _BOLD_ITALIC_RE, _BOLD_RE, _ITALIC_RE
    - _STRIKETHROUGH_RE, _CODE_RE
    """

    def _parse_inline(self, text: str) -> list[InlineSpan]:
        """Parse inline markdown formatting into InlineSpans."""
        spans: list[InlineSpan] = []
        self._parse_inline_recursive(text, spans, bold=False, italic=False, strikethrough=False)
        return spans if spans else [InlineSpan(text)]

    def _parse_inline_recursive(
        self,
        text: str,
        spans: list[InlineSpan],
        bold: bool,
        italic: bool,
        strikethrough: bool,
    ):
        if not text:
            return

        # Find the earliest inline match
        best_match = None
        best_pos = len(text)
        best_type = None

        for pattern, ptype in [
            (self._LINKED_IMAGE_RE, "linked_image"),
            (self._IMAGE_RE, "image"),
            (self._LINK_RE, "link"),
            (self._BOLD_ITALIC_RE, "bold_italic"),
            (self._BOLD_RE, "bold"),
            (self._STRIKETHROUGH_RE, "strikethrough"),
            (self._CODE_RE, "code"),
            (self._ITALIC_RE, "italic"),
        ]:
            m = pattern.search(text)
            if m and m.start() < best_pos:
                best_match = m
                best_pos = m.start()
                best_type = ptype

        if best_match is None:
            if text:
                spans.append(InlineSpan(text, bold=bold, italic=italic, strikethrough=strikethrough))
            return

        # Text before the match
        if best_pos > 0:
            spans.append(
                InlineSpan(
                    text[:best_pos],
                    bold=bold,
                    italic=italic,
                    strikethrough=strikethrough,
                )
            )

        if best_type == "linked_image":
            alt = best_match.group(1)
            image_url = best_match.group(2)
            link_url = best_match.group(3)
            # Render as an image span with the link URL attached
            spans.append(InlineSpan(f"[image: {alt}]", italic=True, link_url=link_url, image_url=image_url))
        elif best_type == "image":
            alt = best_match.group(1)
            spans.append(InlineSpan(f"[image: {alt}]", italic=True))
        elif best_type == "link":
            link_text = best_match.group(1)
            link_url = best_match.group(2)
            spans.append(InlineSpan(link_text, bold=bold, italic=italic, link_url=link_url))
        elif best_type == "bold_italic":
            inner = best_match.group(1) or best_match.group(2)
            self._parse_inline_recursive(inner, spans, bold=True, italic=True, strikethrough=strikethrough)
        elif best_type == "bold":
            inner = best_match.group(1) or best_match.group(2)
            self._parse_inline_recursive(inner, spans, bold=True, italic=italic, strikethrough=strikethrough)
        elif best_type == "italic":
            inner = best_match.group(1) or best_match.group(2)
            self._parse_inline_recursive(inner, spans, bold=bold, italic=True, strikethrough=strikethrough)
        elif best_type == "strikethrough":
            inner = best_match.group(1)
            self._parse_inline_recursive(inner, spans, bold=bold, italic=italic, strikethrough=True)
        elif best_type == "code":
            spans.append(InlineSpan(best_match.group(1), code=True))

        # Text after the match
        remaining = text[best_match.end() :]
        if remaining:
            self._parse_inline_recursive(remaining, spans, bold=bold, italic=italic, strikethrough=strikethrough)
