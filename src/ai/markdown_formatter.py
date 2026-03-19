"""Markdown formatter for GtkTextBuffer.

Parses markdown text and applies TextTags for rich rendering in Gtk.TextView.
"""

import re

from gi.repository import Gtk, Pango


def apply_markdown(buf: Gtk.TextBuffer, text: str, theme) -> None:
    """Parse markdown and apply formatting tags to a GtkTextBuffer."""
    _ensure_tags(buf, theme)
    buf.set_text("")

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # skip closing ```
            code_text = "\n".join(code_lines)
            _insert_tagged(buf, code_text, "code_block")
            _insert_plain(buf, "\n")
            continue

        # Headers
        header_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if header_match:
            level = len(header_match.group(1))
            _insert_tagged(buf, header_match.group(2), f"h{level}")
            _insert_plain(buf, "\n")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})\s*$", line):
            _insert_tagged(buf, "─" * 40, "dim")
            _insert_plain(buf, "\n")
            i += 1
            continue

        # Bullet list
        bullet_match = re.match(r"^(\s*)[*\-+]\s+(.+)$", line)
        if bullet_match:
            indent = len(bullet_match.group(1)) // 2
            prefix = "  " * indent + "• "
            _insert_plain(buf, prefix)
            _insert_inline(buf, bullet_match.group(2))
            _insert_plain(buf, "\n")
            i += 1
            continue

        # Numbered list
        num_match = re.match(r"^(\s*)\d+[.)]\s+(.+)$", line)
        if num_match:
            indent = len(num_match.group(1)) // 2
            prefix = "  " * indent
            _insert_plain(buf, prefix)
            _insert_inline(buf, num_match.group(2))
            _insert_plain(buf, "\n")
            i += 1
            continue

        # Normal line with inline formatting
        _insert_inline(buf, line)
        _insert_plain(buf, "\n")
        i += 1

    # Remove trailing newline
    end = buf.get_end_iter()
    prev = end.copy()
    if prev.backward_char():
        if buf.get_text(prev, end, False) == "\n":
            buf.delete(prev, end)


def _ensure_tags(buf: Gtk.TextBuffer, theme) -> None:
    """Create formatting tags if they don't already exist."""
    table = buf.get_tag_table()

    tags = {
        "bold": {"weight": Pango.Weight.BOLD},
        "italic": {"style": Pango.Style.ITALIC},
        "bold_italic": {"weight": Pango.Weight.BOLD, "style": Pango.Style.ITALIC},
        "code_inline": {
            "family": "monospace",
            "background": theme.hover_bg,
            "foreground": theme.term_yellow or theme.accent_color,
        },
        "code_block": {
            "family": "monospace",
            "background": theme.panel_bg,
            "foreground": theme.fg_color,
            "left-margin": 16,
            "right-margin": 16,
            "pixels-above-lines": 4,
            "pixels-below-lines": 4,
        },
        "h1": {
            "weight": Pango.Weight.BOLD,
            "scale": 1.4,
            "foreground": theme.accent_color,
        },
        "h2": {
            "weight": Pango.Weight.BOLD,
            "scale": 1.2,
            "foreground": theme.accent_color,
        },
        "h3": {
            "weight": Pango.Weight.BOLD,
            "scale": 1.1,
            "foreground": theme.fg_color,
        },
        "link": {
            "foreground": theme.accent_color,
            "underline": Pango.Underline.SINGLE,
        },
        "dim": {
            "foreground": theme.fg_dim,
        },
        "strikethrough": {
            "strikethrough": True,
        },
    }

    for name, props in tags.items():
        if table.lookup(name):
            table.remove(table.lookup(name))
        buf.create_tag(name, **props)


def _insert_plain(buf: Gtk.TextBuffer, text: str) -> None:
    """Insert plain text at end of buffer."""
    buf.insert(buf.get_end_iter(), text)


def _insert_tagged(buf: Gtk.TextBuffer, text: str, tag_name: str) -> None:
    """Insert text with a tag at end of buffer."""
    start_offset = buf.get_end_iter().get_offset()
    buf.insert(buf.get_end_iter(), text)
    start = buf.get_iter_at_offset(start_offset)
    end = buf.get_end_iter()
    tag = buf.get_tag_table().lookup(tag_name)
    if tag:
        buf.apply_tag(tag, start, end)


# Inline patterns: bold+italic, bold, italic, strikethrough, inline code, links
_INLINE_PATTERN = re.compile(
    r"(\*\*\*(.+?)\*\*\*)"  # bold+italic
    r"|(\*\*(.+?)\*\*)"  # bold
    r"|(\*(.+?)\*)"  # italic
    r"|(~~(.+?)~~)"  # strikethrough
    r"|(`([^`]+?)`)"  # inline code
    r"|(\[([^\]]+)\]\(([^)]+)\))"  # links [text](url)
)


def _insert_inline(buf: Gtk.TextBuffer, text: str) -> None:
    """Insert text with inline markdown formatting."""
    pos = 0
    for m in _INLINE_PATTERN.finditer(text):
        # Insert text before match
        if m.start() > pos:
            _insert_plain(buf, text[pos : m.start()])

        if m.group(2):  # bold+italic ***text***
            _insert_tagged(buf, m.group(2), "bold_italic")
        elif m.group(4):  # bold **text**
            _insert_tagged(buf, m.group(4), "bold")
        elif m.group(6):  # italic *text*
            _insert_tagged(buf, m.group(6), "italic")
        elif m.group(8):  # strikethrough ~~text~~
            _insert_tagged(buf, m.group(8), "strikethrough")
        elif m.group(10):  # inline code `text`
            _insert_tagged(buf, m.group(10), "code_inline")
        elif m.group(12):  # link [text](url)
            _insert_tagged(buf, m.group(13), "link")

        pos = m.end()

    # Insert remaining text
    if pos < len(text):
        _insert_plain(buf, text[pos:])
