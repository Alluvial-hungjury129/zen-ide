"""Tests for TerminalMarkdownRenderer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from ai.terminal_markdown_renderer import TerminalMarkdownRenderer

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"


def _fg(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m"


COLORS = {
    "header": "#ff0000",
    "code": "#00ff00",
    "inline_code": "#00ffff",
    "quote": "#ffff00",
    "link": "#0000ff",
    "list": "#ff00ff",
    "accent": "#ff8800",
}


def make_renderer():
    r = TerminalMarkdownRenderer()
    r.update_colors(COLORS)
    return r


def make_narrow_renderer(width=20):
    r = TerminalMarkdownRenderer(terminal_width_fn=lambda: width)
    r.update_colors(COLORS)
    return r


class TestHeaders:
    def test_h1(self):
        r = make_renderer()
        result = r.format_block("# Hello World")
        assert BOLD in result
        assert _fg(COLORS["header"]) in result
        assert "Hello World" in result

    def test_h2(self):
        r = make_renderer()
        result = r.format_block("## Subtitle")
        assert BOLD in result
        assert "Subtitle" in result

    def test_h3(self):
        r = make_renderer()
        result = r.format_block("### Small Header")
        assert BOLD not in result
        assert _fg(COLORS["header"]) in result
        assert "Small Header" in result


class TestCodeBlocks:
    def test_fenced_code_block(self):
        r = make_renderer()
        result = r.format_block("```python\nprint('hello')\n```")
        lines = result.split("\n")
        assert "┌" in lines[0]
        assert "python" in lines[0]
        assert "│" in lines[1]
        # Pygments wraps tokens in ANSI codes, so check chars are present
        import re

        plain = re.sub(r"\x1b\[[0-9;]*m", "", lines[1])
        assert "print" in plain
        assert "hello" in plain
        assert "└" in lines[2]

    def test_code_block_state_tracking(self):
        r = make_renderer()
        # Feed line by line to test state tracking
        r.feed("```\n")
        assert r._in_code_block
        r.feed("some code\n")
        assert r._in_code_block
        r.feed("```\n")
        assert not r._in_code_block


class TestInlineFormatting:
    def test_bold(self):
        r = make_renderer()
        result = r.format_block("This is **bold** text")
        assert BOLD in result
        assert "bold" in result

    def test_italic(self):
        r = make_renderer()
        result = r.format_block("This is *italic* text")
        assert ITALIC in result
        assert "italic" in result

    def test_inline_code(self):
        r = make_renderer()
        result = r.format_block("Use `print()` here")
        assert _fg(COLORS["inline_code"]) in result
        assert "print()" in result

    def test_bold_italic(self):
        r = make_renderer()
        result = r.format_block("This is ***both*** styled")
        assert BOLD in result
        assert ITALIC in result


class TestBlockquotes:
    def test_blockquote(self):
        r = make_renderer()
        result = r.format_block("> quoted text")
        assert "▎" in result
        assert "quoted text" in result
        assert DIM in result

    def test_blockquote_wraps_to_terminal_width(self):
        r = make_narrow_renderer(24)
        result = r.format_block("> " + ("quoted " * 6).strip())
        plain_lines = [self._strip_ansi(line) for line in result.split("\n")]

        assert len(plain_lines) > 1
        assert all(line.startswith("▎ ") for line in plain_lines)
        assert all(len(line) <= 24 for line in plain_lines)

    @staticmethod
    def _strip_ansi(text):
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestLists:
    def test_unordered_list(self):
        r = make_renderer()
        result = r.format_block("- item one")
        assert "●" in result  # Filled circle bullet
        assert "item one" in result

    def test_ordered_list(self):
        r = make_renderer()
        result = r.format_block("1. first item")
        assert "1." in result
        assert "first item" in result

    def test_list_item_wraps_to_terminal_width(self):
        r = make_narrow_renderer(24)
        result = r.format_block("- " + ("wrapped " * 6).strip())
        plain_lines = [self._strip_ansi(line) for line in result.split("\n")]

        assert len(plain_lines) > 1
        assert plain_lines[0].startswith("● ")
        assert all(len(line) <= 24 for line in plain_lines)

    @staticmethod
    def _strip_ansi(text):
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestLinks:
    def test_link(self):
        r = make_renderer()
        result = r.format_block("Click [here](https://example.com)")
        assert UNDERLINE in result
        assert "here" in result
        assert "https://example.com" not in result


class TestHorizontalRule:
    def test_hr(self):
        r = make_renderer()
        result = r.format_block("---")
        assert "─" in result


class TestStreaming:
    def test_line_buffering(self):
        r = make_renderer()
        r.update_colors(COLORS)
        # Partial line is now emitted immediately for real-time display
        result = r.feed("partial")
        assert "partial" in result
        # Complete line overwrites the partial via \r in the caller
        result = r.feed(" line\n")
        assert "partial line" in result

    def test_flush(self):
        r = make_renderer()
        r.feed("no newline")
        result = r.flush()
        assert "no newline" in result

    def test_multiple_lines(self):
        r = make_renderer()
        result = r.feed("line1\nline2\n")
        assert "line1" in result
        assert "line2" in result

    def test_reset(self):
        r = make_renderer()
        r.feed("```\n")
        assert r._in_code_block
        r.reset()
        assert not r._in_code_block
        assert r._line_buffer == ""


class TestFormatBlock:
    def test_mixed_content(self):
        r = make_renderer()
        r.update_colors(COLORS)
        md = "# Title\n\nSome **bold** text\n\n```python\ncode()\n```\n\n- item"
        result = r.format_block(md)
        assert "Title" in result
        # Pygments wraps code tokens in ANSI, so strip them
        import re

        plain = re.sub(r"\x1b\[[0-9;]*m", "", result)
        assert "code()" in plain
        assert "●" in result  # Filled circle bullet

    def test_plain_text_wraps_to_terminal_width(self):
        r = make_narrow_renderer(24)
        result = r.format_block("wrap this sentence so it always stays visible")
        plain_lines = [self._strip_ansi(line) for line in result.split("\n")]

        assert len(plain_lines) > 1
        assert all(len(line) <= 24 for line in plain_lines)

    @staticmethod
    def _strip_ansi(text):
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestTables:
    def _strip_ansi(self, text):
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def _get_plain_lines(self, result):
        return [self._strip_ansi(l) for l in result.split("\n") if l.strip()]

    def _assert_all_lines_same_width(self, result, msg=""):
        """Assert every non-empty line of a rendered table has the same display width."""
        from shared.utils import display_width

        plain_lines = self._get_plain_lines(result)
        widths = [display_width(l) for l in plain_lines]
        assert len(set(widths)) == 1, f"Line widths differ{' (' + msg + ')' if msg else ''}: {widths}\n" + "\n".join(
            f"  [{w}] {l!r}" for w, l in zip(widths, plain_lines)
        )

    def _assert_pipe_positions_consistent(self, result):
        """Assert │ characters appear at the same positions across all content rows."""
        from shared.utils import display_width

        plain_lines = self._get_plain_lines(result)
        row_lines = [l for l in plain_lines if "│" in l]
        if len(row_lines) < 2:
            return

        # Compute display-width position of each │ in each row
        def pipe_positions(line):
            positions = []
            pos = 0
            for ch in line:
                if ch == "│":
                    positions.append(pos)
                pos += display_width(ch)
            return positions

        ref = pipe_positions(row_lines[0])
        for i, line in enumerate(row_lines[1:], 1):
            actual = pipe_positions(line)
            assert actual == ref, (
                f"Pipe positions differ at row {i}: {actual} vs {ref}\n  row 0: {row_lines[0]!r}\n  row {i}: {line!r}"
            )

    def _assert_border_junction_positions(self, result):
        """Assert border junction chars (┬┼┴) align with │ in content rows."""
        from shared.utils import display_width

        plain_lines = self._get_plain_lines(result)
        content_rows = [l for l in plain_lines if "│" in l]
        border_rows = [l for l in plain_lines if l and l[0] in "┌├└"]
        if not content_rows or not border_rows:
            return

        def pipe_positions(line):
            positions = []
            pos = 0
            for ch in line:
                if ch == "│":
                    positions.append(pos)
                pos += display_width(ch)
            return positions

        def junction_positions(line):
            positions = []
            pos = 0
            for ch in line:
                if ch in "┬┼┴":
                    positions.append(pos)
                pos += display_width(ch)
            return positions

        ref_pipes = pipe_positions(content_rows[0])
        # Interior pipes (not first/last) should align with junctions
        interior_pipes = ref_pipes[1:-1] if len(ref_pipes) > 2 else []
        for border in border_rows:
            junctions = junction_positions(border)
            assert junctions == interior_pipes, (
                f"Junction positions {junctions} don't match interior pipes {interior_pipes}\n"
                f"  content: {content_rows[0]!r}\n  border:  {border!r}"
            )

    # ── Basic structure ──

    def test_basic_table(self):
        r = make_renderer()
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = r.format_block(md)
        assert "┌" in result
        assert "│" in result
        assert "└" in result

    def test_table_inline_formatting(self):
        r = make_renderer()
        md = "| Name | Value |\n|---|---|\n| **bold** | `code` |"
        result = r.format_block(md)
        plain = self._strip_ansi(result)
        assert "**" not in plain
        assert "`" not in plain
        assert "bold" in plain
        assert "code" in plain

    # ── Alignment regression tests ──

    def test_table_columns_aligned(self):
        r = make_renderer()
        md = "| # | File |\n|---|---|\n| 1 | **`long_name.py`** |"
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "columns aligned")
        self._assert_pipe_positions_consistent(result)

    def test_table_separator_lines_match(self):
        r = make_renderer()
        md = "| A | B |\n|---|---|\n| x | y |"
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "separator lines")
        self._assert_border_junction_positions(result)

    def test_table_with_emoji(self):
        """Emoji (wide chars) must not break alignment."""
        r = make_renderer()
        md = "| Feature | Status |\n|---------|--------|\n| Rendering | ✅ Done |\n| Alignment | ❌ Broken |"
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "emoji table")
        self._assert_pipe_positions_consistent(result)
        self._assert_border_junction_positions(result)

    def test_table_with_unicode_symbols(self):
        """Arrows, dashes, checkmarks must not break alignment."""
        r = make_renderer()
        md = "| Symbol | Name |\n|--------|------|\n| → | Arrow |\n| — | Em dash |\n| ✓ | Check |"
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "unicode symbols")
        self._assert_pipe_positions_consistent(result)

    def test_table_mixed_emoji_and_inline_code(self):
        """Cells with both emoji and inline code must stay aligned."""
        r = make_renderer()
        md = (
            "| Layer | Examples | Equivalent |\n"
            "|-------|----------|------------|\n"
            "| UI | `Normal`, `StatusLine` | `main_bg` |\n"
            "| Syntax | `Comment`, `String` | ✅ already semantic |\n"
            "| LSP | `@function` → links | fallbacks ✅ |"
        )
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "mixed emoji + code")
        self._assert_pipe_positions_consistent(result)
        self._assert_border_junction_positions(result)

    def test_table_many_columns(self):
        """Tables with 4+ columns must stay aligned."""
        r = make_renderer()
        md = (
            "| City | Country | Pop | Continent |\n"
            "|------|---------|-----|-----------|\n"
            "| Tokyo | Japan | 14M | Asia |\n"
            "| Paris | France | 2M | Europe |\n"
            "| Lagos | Nigeria | 15M | Africa |"
        )
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "4-column table")
        self._assert_pipe_positions_consistent(result)
        self._assert_border_junction_positions(result)

    def test_table_single_column(self):
        """Single-column table edge case."""
        r = make_renderer()
        md = "| Item |\n|------|\n| one |\n| two |"
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "single column")

    def test_table_empty_cells(self):
        """Empty cells must not break alignment."""
        r = make_renderer()
        md = "| A | B | C |\n|---|---|---|\n| x |   | z |\n|   | y |   |"
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "empty cells")
        self._assert_pipe_positions_consistent(result)

    def test_table_varying_cell_lengths(self):
        """Cells with very different lengths must pad correctly."""
        r = make_renderer()
        md = "| Short | A very long cell value here |\n|-------|----------------------------|\n| x | y |"
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "varying lengths")
        self._assert_pipe_positions_consistent(result)

    def test_table_bold_and_code_cells(self):
        """Bold and code formatting must not add visible width."""
        r = make_renderer()
        md = "| Type | Value |\n|------|-------|\n| plain | text |\n| **bold** | `inline` |"
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "bold + code cells")
        self._assert_pipe_positions_consistent(result)

    def test_table_streamed_via_feed(self):
        """Tables received line-by-line via feed() must render identically."""
        r = make_renderer()
        lines = [
            "| A | B |\n",
            "|---|---|\n",
            "| ✅ x | y |\n",
            "\n",  # blank line ends table
        ]
        output = ""
        for line in lines:
            output += r.feed(line)
        output += r.flush()
        plain_lines = self._get_plain_lines(output)
        table_lines = [l for l in plain_lines if "│" in l or l[0:1] in "┌├└"]
        if table_lines:
            from shared.utils import display_width

            widths = [display_width(l) for l in table_lines]
            assert len(set(widths)) == 1, f"Streamed table widths differ: {widths}"

    def test_table_with_multiple_emoji_per_cell(self):
        """Multiple emoji in a single cell must be measured correctly."""
        r = make_renderer()
        md = "| Icons | Desc |\n|-------|------|\n| ✅❌ | both |\n| ✅ | one |"
        result = r.format_block(md)
        self._assert_all_lines_same_width(result, "multiple emoji per cell")
        self._assert_pipe_positions_consistent(result)


class TestNoColors:
    def test_works_without_colors(self):
        r = TerminalMarkdownRenderer()
        result = r.format_block("# Hello\n**bold**\n`code`")
        assert "Hello" in result
        assert "bold" in result
        assert "code" in result


class TestXMLTagsPassThrough:
    """The renderer treats any XML-like text as plain text (passed through as-is)."""

    @staticmethod
    def _strip_ansi(text):
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_angle_bracket_not_xml(self):
        """Angle brackets in math expressions should remain as plain text."""
        r = make_renderer()
        result = r.format_block("x < 5 and y > 3")
        plain = self._strip_ansi(result)
        assert "x < 5 and y > 3" in plain

    def test_xml_in_code_block_still_rendered(self):
        """XML inside code blocks is handled by Pygments."""
        r = make_renderer()
        result = r.format_block("```xml\n<tag>content</tag>\n```")
        assert "┌" in result
        assert "│" in result


class TestHelperFunctions:
    """Tests for standalone helper functions."""

    def test_hex_to_rgb_valid(self):
        from ai.terminal_markdown_renderer import _hex_to_rgb

        assert _hex_to_rgb("#ff0000") == (255, 0, 0)
        assert _hex_to_rgb("#00ff00") == (0, 255, 0)
        assert _hex_to_rgb("#0000ff") == (0, 0, 255)
        assert _hex_to_rgb("#aabbcc") == (170, 187, 204)

    def test_hex_to_rgb_without_hash(self):
        from ai.terminal_markdown_renderer import _hex_to_rgb

        assert _hex_to_rgb("ff0000") == (255, 0, 0)

    def test_hex_to_rgb_invalid_length(self):
        from ai.terminal_markdown_renderer import _hex_to_rgb

        assert _hex_to_rgb("abc") is None
        assert _hex_to_rgb("") is None
        assert _hex_to_rgb("#ab") is None

    def test_darken(self):
        from ai.terminal_markdown_renderer import _darken

        result = _darken("#ffffff", 0.5)
        assert result == "#7f7f7f"

    def test_darken_black(self):
        from ai.terminal_markdown_renderer import _darken

        result = _darken("#000000", 0.5)
        assert result == "#000000"

    def test_darken_invalid_returns_default(self):
        from ai.terminal_markdown_renderer import _darken

        result = _darken("bad", 0.5)
        assert result == "#1e1e2e"

    def test_darken_full(self):
        from ai.terminal_markdown_renderer import _darken

        result = _darken("#ffffff", 0.0)
        assert result == "#000000"


class TestPartialLineStreaming:
    """Tests for real-time partial line emission during streaming."""

    def test_partial_line_emitted_immediately(self):
        r = make_renderer()
        result = r.feed("hell")
        assert "hell" in result

    def test_partial_then_complete(self):
        r = make_renderer()
        r1 = r.feed("hell")
        r2 = r.feed("o world\n")
        assert "hell" in r1
        assert "hello world" in r2

    def test_partial_not_emitted_inside_code_block(self):
        r = make_renderer()
        r.feed("```python\n")
        result = r.feed("partial_code")
        # Inside code block, partial lines without \n are not emitted (buffered)
        assert result == ""

    def test_partial_not_emitted_inside_table(self):
        r = make_renderer()
        r.feed("| A | B |\n")
        r.feed("|---|---|\n")
        result = r.feed("| x | y |")
        # Table rows are buffered until table ends — no output yet
        assert result == ""

    def test_leading_empty_lines_skipped(self):
        r = make_renderer()
        result = r.feed("\n\n\nactual content\n")
        assert "actual content" in result
        # Leading blank lines should be skipped
        lines = result.split("\n")
        assert lines[0] != ""


class TestCodeBlockRendering:
    """Additional tests for code block rendering."""

    def test_code_block_without_language(self):
        r = make_renderer()
        result = r.format_block("```\nplain code\n```")
        assert "┌" in result
        assert "└" in result
        assert "plain code" in _strip_ansi(result)

    def test_unclosed_code_block_flushed(self):
        r = make_renderer()
        r.feed("```python\ncode_line\n")
        result = r.flush()
        assert "└" in result  # closing border added by flush

    def test_code_block_width_uses_terminal(self):
        r = make_narrow_renderer(40)
        result = r.format_block("```\nshort\n```")
        assert "┌" in result
        assert "└" in result

    def test_code_block_incremental_highlighting(self):
        r = make_renderer()
        r.feed("```python\n")
        result = r.feed("print('hello')\n")
        assert "│" in result
        plain = _strip_ansi(result)
        assert "print" in plain

    def test_flush_closing_fence_no_trailing_newline(self):
        """When the closing ``` has no trailing newline, flush() should close
        the code block cleanly without opening a new one (no stray ┌ border)."""
        r = make_renderer()
        r.feed("```python\nprint('hi')\n")
        # The closing fence is left in _line_buffer without a trailing newline
        r.feed("```")
        result = r.flush()
        plain = _strip_ansi(result)
        # Should have the bottom border but NOT a new top border
        assert "┌" not in plain, f"Stray top border found in flush output: {plain!r}"

    def test_flush_closing_fence_only_one_top_border(self):
        """Full code block streamed without trailing newline after closing fence
        should produce exactly one ┌ and one └."""
        r = make_renderer()
        output = r.feed("```python\ncode()\n")
        output += r.feed("```")
        output += r.flush()
        plain = _strip_ansi(output)
        assert plain.count("┌") == 1, f"Expected 1 top border, got {plain.count('┌')}"
        assert plain.count("└") == 1, f"Expected 1 bottom border, got {plain.count('└')}"


class TestTerminalWidthFallback:
    """Tests for terminal width fallback behavior."""

    def test_default_width_80(self):
        r = TerminalMarkdownRenderer()
        assert r._get_terminal_width() == 80

    def test_custom_width_fn(self):
        r = TerminalMarkdownRenderer(terminal_width_fn=lambda: 120)
        assert r._get_terminal_width() == 120

    def test_width_fn_exception_fallback(self):
        r = TerminalMarkdownRenderer(terminal_width_fn=lambda: 1 / 0)
        assert r._get_terminal_width() == 80

    def test_min_width_20(self):
        r = TerminalMarkdownRenderer(terminal_width_fn=lambda: 5)
        assert r._get_terminal_width() == 20


class TestHardWrapAnsi:
    """Tests for ANSI-aware hard wrapping."""

    def test_no_wrap_when_fits(self):
        r = make_renderer()
        result = r._hard_wrap_ansi("short", 80)
        assert result == ["short"]

    def test_wraps_long_text(self):
        r = make_renderer()
        result = r._hard_wrap_ansi("a" * 20, 10)
        assert len(result) == 2
        # Each line is 10 chars plain text; the last line gets remaining 10
        assert _strip_ansi(result[0]) == "a" * 10
        assert _strip_ansi(result[1]) == "a" * 10

    def test_preserves_ansi_across_wrap(self):
        r = make_renderer()
        styled = f"{BOLD}{'x' * 20}{RESET}"
        result = r._hard_wrap_ansi(styled, 10)
        assert len(result) >= 2
        # Each line should have BOLD reapplied
        assert BOLD in result[1]

    def test_empty_string(self):
        r = make_renderer()
        result = r._hard_wrap_ansi("", 80)
        assert result == [""]

    def test_max_width_zero(self):
        r = make_renderer()
        result = r._hard_wrap_ansi("text", 0)
        assert result == ["text"]


def _strip_ansi(text):
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)
