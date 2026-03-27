"""CSS generation and HTML-to-TextBuffer conversion for Markdown Preview.

Contains:
  - _build_github_css(): GitHub-like dark CSS for WebKit backends
  - _HtmlToTextView: HTML parser that populates a GtkTextBuffer (fallback)
"""

from html.parser import HTMLParser


def _build_github_css(theme, font_family=None, font_size=None):
    """Build a GitHub-like dark CSS stylesheet using the IDE theme colors."""
    from fonts import get_font_settings

    if not font_family:
        md_settings = get_font_settings("markdown_preview")
        font_family = md_settings["family"]
    if not font_size:
        md_settings = get_font_settings("markdown_preview")
        font_size = md_settings.get("size", 14)

    editor_settings = get_font_settings("editor")
    code_font = editor_settings["family"]
    code_size = editor_settings.get("size", 16)
    code_stack = f'"{code_font}", monospace'
    body_stack = f'"{font_family}", sans-serif'
    return f"""
    :root {{
        color-scheme: dark;
    }}
    html {{
        height: 100%;
        overflow-y: auto;
    }}
    body {{
        font-family: {body_stack};
        font-size: {font_size}px;
        line-height: 1.8;
        color: {theme.fg_color};
        background-color: {theme.main_bg};
        padding: 0 0 0 24px;
        margin: 0;
        word-wrap: break-word;
        min-height: 100%;
    }}
    /* Scrollbar styling to match editor GTK scrollbar (slider 6px centered in 12px track) */
    ::-webkit-scrollbar {{
        width: 20px;
        background: transparent;
    }}
    ::-webkit-scrollbar-track {{
        background: transparent;
    }}
    ::-webkit-scrollbar-thumb {{
        background-color: {theme.fg_color}40;
        border-radius: 0;
        border: 3px solid transparent;
        background-clip: padding-box;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background-color: {theme.fg_color}66;
        border: 3px solid transparent;
        background-clip: padding-box;
    }}
    h1, h2, h3, h4, h5, h6 {{
        margin-top: 24px;
        margin-bottom: 16px;
        font-weight: 600;
        line-height: 1.25;
        color: {theme.fg_color};
    }}
    h1 {{ font-size: 2em; padding-bottom: 0.3em; border-bottom: 1px solid {theme.border_color}; }}
    h2 {{ font-size: 1.5em; padding-bottom: 0.3em; border-bottom: 1px solid {theme.border_color}; }}
    h3 {{ font-size: 1.25em; }}
    h4 {{ font-size: 1em; }}
    h5 {{ font-size: 0.875em; }}
    h6 {{ font-size: 0.85em; color: {theme.fg_dim}; }}
    p {{ margin-top: 0; margin-bottom: 16px; }}
    a {{ color: {theme.accent_color}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    strong {{ font-weight: 600; }}
    code {{
        font-family: {code_stack};
        font-size: {code_size}px;
        font-variant-ligatures: none;
        font-feature-settings: "liga" 0, "calt" 0;
        padding: 0.2em 0.4em;
        margin: 0;
        background-color: {theme.panel_bg};
        border-radius: 6px;
    }}
    pre {{
        font-family: {code_stack};
        font-variant-ligatures: none;
        font-feature-settings: "liga" 0, "calt" 0;
        padding: 16px;
        overflow: auto;
        font-size: {code_size}px;
        line-height: 1.45;
        background-color: {theme.panel_bg};
        border: 1px solid {theme.border_color};
        border-radius: 6px;
        margin-bottom: 16px;
    }}
    pre code {{
        padding: 0;
        background-color: transparent;
        border-radius: 0;
        font-size: 100%;
    }}
    blockquote {{
        padding: 0 1em;
        color: {theme.fg_dim};
        border-left: 0.25em solid {theme.accent_color};
        margin: 0 0 16px 0;
    }}
    blockquote > :first-child {{ margin-top: 0; }}
    blockquote > :last-child {{ margin-bottom: 0; }}
    ul, ol {{
        padding-left: 2em;
        margin-top: 0;
        margin-bottom: 16px;
    }}
    li {{ margin-top: 0.25em; }}
    li + li {{ margin-top: 0.25em; }}
    table {{
        border-spacing: 0;
        border-collapse: collapse;
        border: none;
        margin-bottom: 16px;
        width: auto;
    }}
    table th, table td {{
        padding: 6px 13px;
        border: 1px solid {theme.border_color};
    }}
    /* Remove outer frame — keep only inner grid lines */
    table tr:first-child th,
    table tr:first-child td {{ border-top: none; }}
    table tr:last-child th,
    table tr:last-child td {{ border-bottom: none; }}
    table th:first-child,
    table td:first-child {{ border-left: none; }}
    table th:last-child,
    table td:last-child {{ border-right: none; }}
    table th {{
        font-weight: 600;
        background-color: {theme.panel_bg};
    }}
    table tr {{
        background-color: {theme.main_bg};
    }}
    table tr:nth-child(2n) {{
        background-color: {theme.fg_color}08;
    }}
    hr {{
        height: 0.25em;
        padding: 0;
        margin: 24px 0;
        background-color: {theme.border_color};
        border: 0;
    }}
    img {{ max-width: 100%; box-sizing: border-box; }}
    del {{ color: {theme.fg_dim}; }}
    input[type="checkbox"] {{
        margin: 0 0.2em 0.25em -1.4em;
        vertical-align: middle;
    }}
    /* Task list items */
    .task-list-item {{ list-style-type: none; }}
    .task-list-item + .task-list-item {{ margin-top: 3px; }}
    """


class _HtmlToTextView(HTMLParser):
    """Parse cmarkgfm HTML output and insert formatted text into a GtkTextBuffer."""

    _BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "li", "tr", "table", "hr"}

    def __init__(self, buf):
        super().__init__()
        self._buf = buf
        self._tag_stack = []
        self._in_pre = False
        self._in_code = False
        self._list_stack = []
        self._table_rows = []
        self._current_row = []
        self._in_table = False
        self._in_th = False
        self._cell_text = ""

    def _insert(self, text, *tag_names):
        end = self._buf.get_end_iter()
        if tag_names:
            valid = [t for t in tag_names if self._buf.get_tag_table().lookup(t)]
            if valid:
                self._buf.insert_with_tags_by_name(end, text, *valid)
                return
        self._buf.insert(end, text)

    def _active_tags(self):
        mapping = {
            "strong": "bold",
            "b": "bold",
            "em": "italic",
            "i": "italic",
            "del": "strikethrough",
            "s": "strikethrough",
            "code": "code",
        }
        tags = []
        for t in self._tag_stack:
            if t in mapping and mapping[t] not in tags:
                tags.append(mapping[t])
        if self._in_pre and "code" in tags:
            tags.remove("code")
            tags.append("code_block")
        elif self._in_pre:
            tags.append("code_block")
        return tags

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._tag_stack.append(tag)
        elif tag in ("strong", "b", "em", "i", "del", "s", "code"):
            self._tag_stack.append(tag)
        elif tag == "pre":
            self._in_pre = True
        elif tag == "a":
            self._tag_stack.append("a")
        elif tag == "blockquote":
            self._tag_stack.append("blockquote")
            self._insert("  ▎ ", "quote_bar")
        elif tag == "ul":
            self._list_stack.append(("ul", 0))
        elif tag == "ol":
            start = int(attrs_dict.get("start", "1"))
            self._list_stack.append(("ol", start - 1))
        elif tag == "li":
            indent = "  " * max(0, len(self._list_stack) - 1)
            if self._list_stack:
                kind, count = self._list_stack[-1]
                if kind == "ul":
                    self._insert(f"{indent}  ▪ ", "list_item")
                else:
                    count += 1
                    self._list_stack[-1] = (kind, count)
                    self._insert(f"{indent}  {count}. ", "list_item")
            self._tag_stack.append("li")
        elif tag == "hr":
            self._insert("─" * 40 + "\n", "hr")
        elif tag == "br":
            self._insert("\n")
        elif tag == "table":
            self._in_table = True
            self._table_rows = []
        elif tag == "tr":
            self._current_row = []
        elif tag in ("th", "td"):
            self._in_th = tag == "th"
            self._cell_text = ""
        elif tag == "input":
            checked = "checked" in attrs_dict
            self._insert("☑ " if checked else "☐ ")
        elif tag == "p":
            self._tag_stack.append("p")

    def handle_endtag(self, tag):
        if tag in ("th", "td"):
            self._current_row.append((self._cell_text.strip(), self._in_th))
            self._cell_text = ""
            return
        if tag == "tr":
            if self._current_row:
                self._table_rows.append(self._current_row)
            self._current_row = []
            return
        if tag == "table":
            self._render_table()
            self._in_table = False
            self._table_rows = []
            return
        if tag in ("thead", "tbody"):
            return
        if tag == "pre":
            self._in_pre = False
            self._insert("\n")
            return
        if tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self._insert("\n")
            return
        if tag in (
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "strong",
            "b",
            "em",
            "i",
            "del",
            "s",
            "code",
            "a",
            "blockquote",
            "li",
            "p",
        ):
            for idx in range(len(self._tag_stack) - 1, -1, -1):
                if self._tag_stack[idx] == tag:
                    self._tag_stack.pop(idx)
                    break
        if tag in self._BLOCK_TAGS:
            self._insert("\n")
        if tag in ("h1", "h2"):
            self._insert("─" * 50 + "\n", "heading_rule")

    def handle_data(self, data):
        if self._in_table:
            self._cell_text += data
            return
        if self._in_pre:
            self._insert(data, *self._active_tags())
            return
        tags = self._active_tags()
        for t in self._tag_stack:
            if t in ("h1", "h2", "h3", "h4", "h5", "h6") and t not in tags:
                tags.append(t)
        if "a" in self._tag_stack and "link" not in tags:
            tags.append("link")
        if "blockquote" in self._tag_stack and "quote" not in tags:
            tags.append("quote")
        if "li" in self._tag_stack and "list_item" not in tags:
            tags.append("list_item")
        self._insert(data, *tags)

    def handle_entityref(self, name):
        from html import unescape

        self.handle_data(unescape(f"&{name};"))

    def handle_charref(self, name):
        from html import unescape

        self.handle_data(unescape(f"&#{name};"))

    def _render_table(self):
        if not self._table_rows:
            return
        num_cols = max(len(row) for row in self._table_rows)
        col_widths = [0] * num_cols
        for row in self._table_rows:
            for i, (cell, _) in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))
        col_widths = [max(w, 1) for w in col_widths]
        has_header = self._table_rows and any(is_th for _, is_th in self._table_rows[0])

        # Top border: ┌──────┬──────┐
        top = "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"
        self._insert(top + "\n", "table_cell")

        for row_idx, row in enumerate(self._table_rows):
            parts = []
            for i in range(num_cols):
                cell_text = row[i][0] if i < len(row) else ""
                parts.append(f" {cell_text.ljust(col_widths[i])} ")
            line = "│" + "│".join(parts) + "│"
            tag = "table_header" if (row_idx == 0 and has_header) else "table_cell"
            self._insert(line + "\n", tag)
            if row_idx == 0 and has_header:
                sep = "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"
                self._insert(sep + "\n", "table_cell")

        # Bottom border: └──────┴──────┘
        bottom = "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"
        self._insert(bottom + "\n", "table_cell")
