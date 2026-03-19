"""ContentBlock — intermediate representation for native markdown/OpenAPI rendering.

Block list is the IR between parsers (markdown, OpenAPI) and the MarkdownCanvas
renderer. Each block carries a source_line for editor↔preview scroll sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InlineSpan:
    """A run of styled text within a paragraph, heading, or list item."""

    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    strikethrough: bool = False
    link_url: str | None = None


@dataclass
class ContentBlock:
    """A structural block in a rendered document.

    The *kind* field determines which other fields are relevant:
    - ``heading``:    level, spans
    - ``paragraph``:  spans
    - ``code``:       language, code
    - ``table``:      headers, rows
    - ``list``:       items, ordered
    - ``blockquote``: children
    - ``image``:      image_url, image_alt, image_width, image_height,
                      image_width_pct, image_align
    - ``image_row``:  images (list of dicts, laid out horizontally)
    - ``hr``:         (no extra fields)
    """

    kind: str
    source_line: int = 0

    # heading
    level: int = 1

    # inline text (heading, paragraph, blockquote text)
    spans: list[InlineSpan] = field(default_factory=list)

    # code block
    language: str = ""
    code: str = ""

    # table
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    header_spans: list[list[InlineSpan]] = field(default_factory=list)
    row_spans: list[list[list[InlineSpan]]] = field(default_factory=list)

    # list
    items: list[list[InlineSpan]] = field(default_factory=list)
    ordered: bool = False

    # blockquote / collapsible (recursive)
    children: list[ContentBlock] = field(default_factory=list)

    # collapsible section
    collapsible: bool = False
    collapsed: bool = True

    # swagger-style visual hints
    badge_text: str = ""  # e.g. "GET", "POST"
    badge_color: str = ""  # hex background for badge
    border_color: str = ""  # colored left border on collapsible cards

    # image (single)
    image_url: str = ""
    image_alt: str = ""
    image_width: int | None = None
    image_height: int | None = None
    image_width_pct: float | None = None  # percentage width (e.g. 50 for "50%")
    image_align: str = ""  # "center", "left", "right" — from HTML align attr

    # image_row (multiple images side-by-side)
    # Each entry: {"url": str, "alt": str, "width": int|None, "height": int|None}
    images: list[dict] = field(default_factory=list)

    # rendering cache (filled by MarkdownCanvas)
    _y_offset: float = 0.0
    _height: float = 0.0
    _header_height: float = 0.0
    _row_heights: list[float] = field(default_factory=list)
