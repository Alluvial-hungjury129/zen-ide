"""MarkdownBlockRenderer — parse markdown text into ContentBlocks.

Line-oriented parser that produces ContentBlocks with accurate source_line
tracking for editor<->preview scroll sync. Handles GFM features: code fences,
tables, task lists, headings, lists, blockquotes, horizontal rules, inline
formatting (bold, italic, code, links, strikethrough), and raw HTML blocks
(tables, images, details/summary).
"""

from __future__ import annotations

import re

from editor.preview.code_block_mixin import CodeBlockMixin
from editor.preview.content_block import ContentBlock, InlineSpan
from editor.preview.table_block_mixin import TableBlockMixin


class MarkdownBlockRenderer(TableBlockMixin, CodeBlockMixin):
    """Convert markdown text to a list of ContentBlocks."""

    # Inline patterns
    _BOLD_ITALIC_RE = re.compile(r"\*\*\*(.+?)\*\*\*|___(.+?)___")
    _BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
    _ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
    _STRIKETHROUGH_RE = re.compile(r"~~(.+?)~~")
    _CODE_RE = re.compile(r"`([^`]+)`")
    _LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    _IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    _STANDALONE_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
    # Linked image: [![alt](image_url)](link_url)
    _LINKED_IMAGE_RE = re.compile(r"\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)")
    _STANDALONE_LINKED_IMAGE_RE = re.compile(r"^\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)\s*$")

    _HTML_IMG_STANDALONE_RE = re.compile(r"^<img\s[^>]*/?\s*>\s*$", re.IGNORECASE)
    _HTML_IMG_ATTR_RE = re.compile(r'(\w+)\s*=\s*["\']([^"\']*)["\']')

    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
    _HR_RE = re.compile(r"^(\*{3,}|-{3,}|_{3,})\s*$")
    _FENCE_RE = re.compile(r"^```(\w*)\s*$")
    _UL_RE = re.compile(r"^(\s*)([-*+])\s+(.+)$")
    _OL_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.+)$")
    _QUOTE_RE = re.compile(r"^>\s?(.*)")
    _TABLE_SEP_RE = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")

    # HTML block-level opening tags that interrupt paragraph flow.
    _HTML_BLOCK_OPEN_RE = re.compile(
        r"^\s*<(table|thead|tbody|tr|td|th|div|section|details|summary|figure|figcaption|picture|video|audio|iframe|center)\b",
        re.IGNORECASE,
    )
    # Paired close tag for the above
    _HTML_BLOCK_CLOSE_RE = re.compile(
        r"</\s*(table|div|section|details|figure|picture|video|audio|iframe|center)\s*>", re.IGNORECASE
    )

    def render(self, markdown_text: str) -> list[ContentBlock]:
        """Parse markdown text and return content blocks."""
        lines = markdown_text.split("\n")
        blocks: list[ContentBlock] = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Empty line
            if not stripped:
                i += 1
                continue

            # Code fence
            fence_match = self._FENCE_RE.match(stripped)
            if fence_match:
                lang = fence_match.group(1) or ""
                code_lines = []
                start_line = i
                i += 1
                while i < len(lines):
                    if lines[i].strip().startswith("```"):
                        i += 1
                        break
                    code_lines.append(lines[i])
                    i += 1
                blocks.append(
                    ContentBlock(
                        kind="code",
                        source_line=start_line,
                        language=lang,
                        code="\n".join(code_lines),
                    )
                )
                continue

            # Heading
            heading_match = self._HEADING_RE.match(stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                blocks.append(
                    ContentBlock(
                        kind="heading",
                        source_line=i,
                        level=level,
                        spans=self._parse_inline(text),
                    )
                )
                i += 1
                continue

            # Horizontal rule
            if self._HR_RE.match(stripped):
                blocks.append(ContentBlock(kind="hr", source_line=i))
                i += 1
                continue

            # Blockquote
            quote_match = self._QUOTE_RE.match(stripped)
            if quote_match:
                quote_lines = []
                start_line = i
                while i < len(lines):
                    qm = self._QUOTE_RE.match(lines[i].strip())
                    if qm:
                        quote_lines.append(qm.group(1))
                        i += 1
                    elif lines[i].strip() == "":
                        break
                    else:
                        break

                children = []
                for ql in quote_lines:
                    if ql.strip():
                        children.append(
                            ContentBlock(
                                kind="paragraph",
                                spans=self._parse_inline(ql),
                            )
                        )

                blocks.append(
                    ContentBlock(
                        kind="blockquote",
                        source_line=start_line,
                        children=children,
                    )
                )
                continue

            # Table (check if next line is a separator)
            if "|" in stripped and i + 1 < len(lines):
                next_stripped = lines[i + 1].strip()
                if self._TABLE_SEP_RE.match(next_stripped) and "|" in next_stripped:
                    headers = self._parse_table_row(stripped)
                    header_spans = [self._parse_inline(h) for h in headers]
                    start_line = i
                    i += 2  # skip header + separator
                    rows = []
                    row_spans = []
                    while i < len(lines) and "|" in lines[i]:
                        row = self._parse_table_row(lines[i].strip())
                        if row:
                            rows.append(row)
                            row_spans.append([self._parse_inline(c) for c in row])
                        i += 1
                    blocks.append(
                        ContentBlock(
                            kind="table",
                            source_line=start_line,
                            headers=headers,
                            rows=rows,
                            header_spans=header_spans,
                            row_spans=row_spans,
                        )
                    )
                    continue

            # Standalone linked image: [![alt](img_url)](link_url)
            linked_img_match = self._STANDALONE_LINKED_IMAGE_RE.match(stripped)
            if linked_img_match:
                blocks.append(
                    ContentBlock(
                        kind="image",
                        source_line=i,
                        image_alt=linked_img_match.group(1),
                        image_url=linked_img_match.group(2),
                    )
                )
                i += 1
                continue

            # Standalone image
            img_match = self._STANDALONE_IMAGE_RE.match(stripped)
            if img_match:
                blocks.append(
                    ContentBlock(
                        kind="image",
                        source_line=i,
                        image_alt=img_match.group(1),
                        image_url=img_match.group(2),
                    )
                )
                i += 1
                continue

            # HTML <img> tag (standalone)
            html_img_match = self._HTML_IMG_STANDALONE_RE.match(stripped)
            if html_img_match:
                attrs = dict(self._HTML_IMG_ATTR_RE.findall(stripped))
                src = attrs.get("src", "")
                if src:
                    width = None
                    height = None
                    try:
                        width = int(attrs["width"]) if "width" in attrs else None
                    except ValueError:
                        pass
                    try:
                        height = int(attrs["height"]) if "height" in attrs else None
                    except ValueError:
                        pass
                    blocks.append(
                        ContentBlock(
                            kind="image",
                            source_line=i,
                            image_alt=attrs.get("alt", ""),
                            image_url=src,
                            image_width=width,
                            image_height=height,
                        )
                    )
                    i += 1
                    continue

            # HTML block (e.g. <table>, <div>, <details>, etc.)
            html_block_match = self._HTML_BLOCK_OPEN_RE.match(stripped)
            if html_block_match:
                tag_name = html_block_match.group(1).lower()
                html_lines = []
                start_line = i
                # Collect lines until we find the matching close tag (or EOF).
                # Track nesting depth for the outermost tag.
                depth = 0
                open_re = re.compile(rf"<{tag_name}\b", re.IGNORECASE)
                close_re = re.compile(rf"</{tag_name}\s*>", re.IGNORECASE)
                while i < len(lines):
                    current = lines[i]
                    # Count opening and closing tags on this line
                    depth += len(open_re.findall(current))
                    depth -= len(close_re.findall(current))
                    html_lines.append(current)
                    i += 1
                    if depth <= 0:
                        break
                html_text = "\n".join(html_lines)
                html_blocks = self._parse_html_block(html_text, start_line)
                blocks.extend(html_blocks)
                continue

            # Unordered list
            ul_match = self._UL_RE.match(line)
            if ul_match:
                items = []
                start_line = i
                while i < len(lines):
                    m = self._UL_RE.match(lines[i])
                    if m:
                        items.append(self._parse_inline(m.group(3)))
                        i += 1
                    elif lines[i].strip() == "":
                        break
                    elif lines[i].startswith("  ") or lines[i].startswith("\t"):
                        # Continuation of previous item
                        if items:
                            cont_spans = self._parse_inline(lines[i].strip())
                            items[-1].append(InlineSpan(" "))
                            items[-1].extend(cont_spans)
                        i += 1
                    else:
                        break
                blocks.append(
                    ContentBlock(
                        kind="list",
                        source_line=start_line,
                        items=items,
                        ordered=False,
                    )
                )
                continue

            # Ordered list
            ol_match = self._OL_RE.match(line)
            if ol_match:
                items = []
                start_line = i
                while i < len(lines):
                    m = self._OL_RE.match(lines[i])
                    if m:
                        items.append(self._parse_inline(m.group(3)))
                        i += 1
                    elif lines[i].strip() == "":
                        break
                    elif lines[i].startswith("  ") or lines[i].startswith("\t"):
                        if items:
                            cont_spans = self._parse_inline(lines[i].strip())
                            items[-1].append(InlineSpan(" "))
                            items[-1].extend(cont_spans)
                        i += 1
                    else:
                        break
                blocks.append(
                    ContentBlock(
                        kind="list",
                        source_line=start_line,
                        items=items,
                        ordered=True,
                    )
                )
                continue

            # Paragraph (collect consecutive non-blank lines)
            para_lines = []
            hard_breaks = []
            start_line = i
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    break
                if self._HEADING_RE.match(s):
                    break
                if self._HR_RE.match(s):
                    break
                if self._FENCE_RE.match(s):
                    break
                if self._QUOTE_RE.match(s):
                    break
                if self._UL_RE.match(lines[i]):
                    break
                if self._OL_RE.match(lines[i]):
                    break
                if self._STANDALONE_IMAGE_RE.match(s):
                    break
                if self._STANDALONE_LINKED_IMAGE_RE.match(s):
                    break
                if self._HTML_IMG_STANDALONE_RE.match(s):
                    break
                if self._HTML_BLOCK_OPEN_RE.match(s):
                    break
                if "|" in s and i + 1 < len(lines):
                    next_s = lines[i + 1].strip()
                    if self._TABLE_SEP_RE.match(next_s) and "|" in next_s:
                        break
                para_lines.append(s)
                hard_breaks.append(lines[i].rstrip("\r").endswith("  "))
                i += 1

            if para_lines:
                parts = []
                for idx, pl in enumerate(para_lines):
                    parts.append(pl)
                    if idx < len(para_lines) - 1:
                        parts.append("\n" if hard_breaks[idx] else " ")
                text = "".join(parts)
                blocks.append(
                    ContentBlock(
                        kind="paragraph",
                        source_line=start_line,
                        spans=self._parse_inline(text),
                    )
                )

        return blocks
