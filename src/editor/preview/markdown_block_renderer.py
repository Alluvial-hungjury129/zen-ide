"""MarkdownBlockRenderer — parse markdown text into ContentBlocks.

Line-oriented parser that produces ContentBlocks with accurate source_line
tracking for editor↔preview scroll sync. Handles GFM features: code fences,
tables, task lists, headings, lists, blockquotes, horizontal rules, inline
formatting (bold, italic, code, links, strikethrough), and raw HTML blocks
(tables, images, details/summary).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from editor.preview.content_block import ContentBlock, InlineSpan


class MarkdownBlockRenderer:
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

    # ------------------------------------------------------------------ #
    #  Inline parsing                                                      #
    # ------------------------------------------------------------------ #

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

    def _parse_table_row(self, line: str) -> list[str]:
        """Parse a table row string into cell values."""
        cells = line.split("|")
        # Strip leading/trailing empty cells from pipe-delimited format
        if cells and not cells[0].strip():
            cells = cells[1:]
        if cells and not cells[-1].strip():
            cells = cells[:-1]
        return [c.strip() for c in cells]

    # ------------------------------------------------------------------ #
    #  HTML block parsing                                                  #
    # ------------------------------------------------------------------ #

    def _parse_html_block(self, html_text: str, source_line: int) -> list[ContentBlock]:
        """Parse a raw HTML block into ContentBlocks.

        Supports <table> with <tr>/<td>/<th> (including <img> in cells),
        standalone <img> tags, and falls back to rendering the text content
        of other HTML blocks as a paragraph.
        """
        parser = _HtmlBlockParser()
        try:
            parser.feed(html_text)
        except Exception:
            # Fallback: render raw HTML as a paragraph
            return [
                ContentBlock(
                    kind="paragraph",
                    source_line=source_line,
                    spans=[InlineSpan(html_text)],
                )
            ]

        blocks: list[ContentBlock] = []

        # --- HTML <table> → table block or image grid ---
        if parser.table_rows:
            # Check if the table is primarily an image layout:
            # every non-empty cell is an <img> tag.
            all_images = True
            image_cells = []
            for row in parser.table_rows:
                row_images = []
                for cell in row:
                    if cell.get("images"):
                        row_images.append(cell)
                    elif cell.get("text", "").strip():
                        all_images = False
                        break
                    # else: empty cell, skip
                if not all_images:
                    break
                image_cells.append(row_images)

            if all_images and image_cells:
                # Group images by HTML table row. Rows with multiple
                # images produce an ``image_row`` block (side-by-side
                # layout); single-image rows produce a plain ``image``.
                for row in image_cells:
                    row_imgs: list[dict] = []
                    row_cell_align = ""
                    for cell in row:
                        # Capture cell-level align for single-image rows
                        if cell.get("align"):
                            row_cell_align = cell["align"].lower()
                        for img in cell["images"]:
                            width = None
                            height = None
                            width_pct = None
                            width_raw = img.get("width", "")
                            height_raw = img.get("height", "")
                            # Handle percentage widths — store as percentage
                            # for the renderer to apply relative to content width.
                            if width_raw and "%" in str(width_raw):
                                try:
                                    width_pct = float(str(width_raw).replace("%", "").strip())
                                except (ValueError, TypeError):
                                    pass
                            else:
                                try:
                                    width = int(width_raw) if width_raw else None
                                except (ValueError, TypeError):
                                    pass
                            try:
                                height = int(height_raw) if height_raw and "%" not in str(height_raw) else None
                            except (ValueError, TypeError):
                                pass
                            row_imgs.append(
                                {
                                    "url": img.get("src", ""),
                                    "alt": img.get("alt", ""),
                                    "width": width,
                                    "height": height,
                                    "width_pct": width_pct,
                                }
                            )

                    if len(row_imgs) == 1:
                        # Single image row → plain image block
                        ri = row_imgs[0]
                        blocks.append(
                            ContentBlock(
                                kind="image",
                                source_line=source_line,
                                image_alt=ri["alt"],
                                image_url=ri["url"],
                                image_width=ri["width"],
                                image_height=ri["height"],
                                image_width_pct=ri.get("width_pct"),
                                image_align=row_cell_align,
                            )
                        )
                    elif row_imgs:
                        # Multiple images in one row → image_row block
                        blocks.append(
                            ContentBlock(
                                kind="image_row",
                                source_line=source_line,
                                images=row_imgs,
                            )
                        )
            else:
                # Text table — convert to a markdown-style table block.
                # First row with <th> is the header; otherwise first row is header.
                has_header = any(cell.get("is_header") for cell in parser.table_rows[0]) if parser.table_rows else False

                if has_header:
                    header_row = parser.table_rows[0]
                    data_rows = parser.table_rows[1:]
                else:
                    header_row = None
                    data_rows = parser.table_rows

                num_cols = max(len(row) for row in parser.table_rows)

                def _cell_text(cell):
                    """Extract display text from a parsed cell dict."""
                    parts = []
                    if cell.get("text", "").strip():
                        parts.append(cell["text"].strip())
                    for img in cell.get("images", []):
                        alt = img.get("alt", "")
                        parts.append(f"[image: {alt}]" if alt else "[image]")
                    return " ".join(parts) if parts else ""

                headers = []
                header_spans = []
                if header_row:
                    for ci in range(num_cols):
                        cell = header_row[ci] if ci < len(header_row) else {}
                        t = _cell_text(cell)
                        headers.append(t)
                        header_spans.append(self._parse_inline(t))

                rows = []
                row_spans = []
                for dr in data_rows:
                    row = []
                    rs = []
                    for ci in range(num_cols):
                        cell = dr[ci] if ci < len(dr) else {}
                        t = _cell_text(cell)
                        row.append(t)
                        rs.append(self._parse_inline(t))
                    rows.append(row)
                    row_spans.append(rs)

                blocks.append(
                    ContentBlock(
                        kind="table",
                        source_line=source_line,
                        headers=headers,
                        rows=rows,
                        header_spans=header_spans,
                        row_spans=row_spans,
                    )
                )

        # --- Standalone images found outside <table> ---
        for img in parser.standalone_images:
            width = None
            height = None
            width_raw = img.get("width", "")
            height_raw = img.get("height", "")
            try:
                width = int(width_raw) if width_raw and "%" not in width_raw else None
            except (ValueError, TypeError):
                pass
            try:
                height = int(height_raw) if height_raw and "%" not in height_raw else None
            except (ValueError, TypeError):
                pass
            blocks.append(
                ContentBlock(
                    kind="image",
                    source_line=source_line,
                    image_alt=img.get("alt", ""),
                    image_url=img.get("src", ""),
                    image_width=width,
                    image_height=height,
                )
            )

        # --- Remaining plain text (from non-table HTML blocks) ---
        if parser.text_parts and not parser.table_rows:
            text = " ".join(parser.text_parts).strip()
            if text:
                # Check if text contains standalone linked images and extract them as image blocks
                remaining_text = text
                while remaining_text:
                    linked_m = self._LINKED_IMAGE_RE.search(remaining_text)
                    standalone_m = self._IMAGE_RE.search(remaining_text)

                    # Pick whichever match comes first
                    best_m = None
                    best_type = None
                    if linked_m and (standalone_m is None or linked_m.start() <= standalone_m.start()):
                        best_m = linked_m
                        best_type = "linked_image"
                    elif standalone_m:
                        best_m = standalone_m
                        best_type = "image"

                    if best_m is None:
                        # No more images — emit remaining text as paragraph
                        stripped_rem = remaining_text.strip()
                        if stripped_rem:
                            blocks.append(
                                ContentBlock(
                                    kind="paragraph",
                                    source_line=source_line,
                                    spans=self._parse_inline(stripped_rem),
                                )
                            )
                        break

                    # Text before the image match → paragraph
                    before = remaining_text[: best_m.start()].strip()
                    if before:
                        blocks.append(
                            ContentBlock(
                                kind="paragraph",
                                source_line=source_line,
                                spans=self._parse_inline(before),
                            )
                        )

                    # The image itself → image block
                    if best_type == "linked_image":
                        blocks.append(
                            ContentBlock(
                                kind="image",
                                source_line=source_line,
                                image_alt=best_m.group(1),
                                image_url=best_m.group(2),
                            )
                        )
                    else:
                        blocks.append(
                            ContentBlock(
                                kind="image",
                                source_line=source_line,
                                image_alt=best_m.group(1),
                                image_url=best_m.group(2),
                            )
                        )

                    remaining_text = remaining_text[best_m.end() :]

        # If nothing was extracted, emit a blank to avoid losing source lines
        if not blocks:
            blocks.append(
                ContentBlock(
                    kind="paragraph",
                    source_line=source_line,
                    spans=[InlineSpan("")],
                )
            )

        return blocks


class _HtmlBlockParser(HTMLParser):
    """Lightweight HTML parser that extracts table structure and images.

    After calling ``feed(html)``, results are available as:
    - ``table_rows``: list of rows, each row is a list of cell dicts
        ``{"text": str, "is_header": bool, "images": [{"src","alt","width","height"}]}``
    - ``standalone_images``: list of image dicts found outside ``<table>``
    - ``text_parts``: collected text outside table cells
    """

    def __init__(self):
        super().__init__()
        self.table_rows: list[list[dict]] = []
        self.standalone_images: list[dict] = []
        self.text_parts: list[str] = []

        self._in_table = False
        self._current_row: list[dict] | None = None
        self._current_cell: dict | None = None
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == "table":
            self._in_table = True
        elif tag_lower == "tr":
            self._current_row = []
        elif tag_lower in ("td", "th"):
            self._current_cell = {
                "text": "",
                "is_header": tag_lower == "th",
                "images": [],
                "align": attrs_dict.get("align", ""),
                "colspan": attrs_dict.get("colspan", ""),
            }
            self._in_cell = True
        elif tag_lower == "img":
            img_info = {
                "src": attrs_dict.get("src", ""),
                "alt": attrs_dict.get("alt", ""),
                "width": attrs_dict.get("width", ""),
                "height": attrs_dict.get("height", ""),
            }
            if self._in_cell and self._current_cell is not None:
                self._current_cell["images"].append(img_info)
            else:
                self.standalone_images.append(img_info)

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in ("td", "th"):
            if self._current_cell is not None and self._current_row is not None:
                self._current_row.append(self._current_cell)
            self._current_cell = None
            self._in_cell = False
        elif tag_lower == "tr":
            if self._current_row is not None and self._current_row:
                self.table_rows.append(self._current_row)
            self._current_row = None
        elif tag_lower == "table":
            self._in_table = False

    def handle_data(self, data):
        if self._in_cell and self._current_cell is not None:
            self._current_cell["text"] += data
        elif not self._in_table:
            stripped = data.strip()
            if stripped:
                self.text_parts.append(stripped)
