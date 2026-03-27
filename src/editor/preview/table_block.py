"""Table block rendering mixin and HTML block parser.

Provides table row parsing, HTML block-to-ContentBlock conversion,
and the lightweight _HtmlBlockParser for extracting table structure
and images from raw HTML blocks.
"""

from __future__ import annotations

from html.parser import HTMLParser

from editor.preview.content_block import ContentBlock, InlineSpan


class TableBlockMixin:
    """Mixin providing table and HTML block parsing for MarkdownBlockRenderer.

    Expects the host class to define:
    - self._parse_inline(text) -> list[InlineSpan]
    - self._LINKED_IMAGE_RE, self._IMAGE_RE (compiled regexes)
    """

    def _parse_table_row(self, line: str) -> list[str]:
        """Parse a table row string into cell values."""
        cells = line.split("|")
        # Strip leading/trailing empty cells from pipe-delimited format
        if cells and not cells[0].strip():
            cells = cells[1:]
        if cells and not cells[-1].strip():
            cells = cells[:-1]
        return [c.strip() for c in cells]

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
