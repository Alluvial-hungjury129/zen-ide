"""Tests for AnsiBuffer — ANSI escape sequence parser."""

from ai.ansi_buffer import AnsiBuffer, StyledSpan


class TestStyledSpan:
    """Tests for the StyledSpan data class."""

    def test_default_attributes(self):
        span = StyledSpan("hello")
        assert span.text == "hello"
        assert span.fg is None
        assert span.bg is None
        assert span.bold is False
        assert span.dim is False
        assert span.italic is False
        assert span.underline is False

    def test_custom_attributes(self):
        span = StyledSpan("hi", fg="#ff0000", bg="#000000", bold=True, italic=True)
        assert span.fg == "#ff0000"
        assert span.bg == "#000000"
        assert span.bold is True
        assert span.italic is True

    def test_copy_style_empty_text(self):
        span = StyledSpan("text", fg="#aabbcc", bold=True, underline=True)
        copy = span.copy_style()
        assert copy.text == ""
        assert copy.fg == "#aabbcc"
        assert copy.bold is True
        assert copy.underline is True


class TestAnsiBufferPlainText:
    """Tests for plain text (no ANSI codes)."""

    def test_single_line(self):
        buf = AnsiBuffer()
        buf.feed("hello world")
        assert buf.get_text() == "hello world"
        assert buf.get_line_count() == 1

    def test_multiple_lines(self):
        buf = AnsiBuffer()
        buf.feed("line1\nline2\nline3")
        assert buf.get_line_count() == 3
        assert buf.get_line_text(0) == "line1"
        assert buf.get_line_text(1) == "line2"
        assert buf.get_line_text(2) == "line3"

    def test_empty_lines(self):
        buf = AnsiBuffer()
        buf.feed("a\n\nb")
        assert buf.get_line_count() == 3
        assert buf.get_line_text(1) == ""

    def test_get_text_joins_with_newlines(self):
        buf = AnsiBuffer()
        buf.feed("alpha\nbeta")
        assert buf.get_text() == "alpha\nbeta"

    def test_feed_bytes(self):
        buf = AnsiBuffer()
        buf.feed_bytes(b"hello bytes")
        assert buf.get_text() == "hello bytes"

    def test_feed_bytes_invalid_utf8(self):
        buf = AnsiBuffer()
        buf.feed_bytes(b"hello\xff\xfeworld")
        text = buf.get_text()
        assert "hello" in text
        assert "world" in text

    def test_clear(self):
        buf = AnsiBuffer()
        buf.feed("some text\nmore text")
        buf.clear()
        assert buf.get_text() == ""
        assert buf.get_line_count() == 1
        assert len(buf.dirty_lines) == 0


class TestAnsiBufferSGR:
    """Tests for SGR (Select Graphic Rendition) handling."""

    def test_bold(self):
        buf = AnsiBuffer()
        buf.feed("\033[1mbold text\033[0m")
        line = buf.get_line(0)
        assert len(line) == 1
        assert line[0].bold is True
        assert line[0].text == "bold text"

    def test_dim(self):
        buf = AnsiBuffer()
        buf.feed("\033[2mdim\033[0m")
        line = buf.get_line(0)
        assert line[0].dim is True

    def test_italic(self):
        buf = AnsiBuffer()
        buf.feed("\033[3mitalic\033[0m")
        line = buf.get_line(0)
        assert line[0].italic is True

    def test_underline(self):
        buf = AnsiBuffer()
        buf.feed("\033[4munderlined\033[0m")
        line = buf.get_line(0)
        assert line[0].underline is True

    def test_reset_clears_all_styles(self):
        buf = AnsiBuffer()
        buf.feed("\033[1m\033[3mstyles\033[0mplain")
        line = buf.get_line(0)
        assert line[0].bold is True
        assert line[0].italic is True
        assert line[1].bold is False
        assert line[1].italic is False

    def test_disable_bold_dim(self):
        buf = AnsiBuffer()
        buf.feed("\033[1m\033[2mboth\033[22mnormal")
        line = buf.get_line(0)
        assert line[0].bold is True
        assert line[0].dim is True
        assert line[1].bold is False
        assert line[1].dim is False

    def test_disable_italic(self):
        buf = AnsiBuffer()
        buf.feed("\033[3mital\033[23mnot")
        line = buf.get_line(0)
        assert line[0].italic is True
        assert line[1].italic is False

    def test_disable_underline(self):
        buf = AnsiBuffer()
        buf.feed("\033[4mul\033[24mnot")
        line = buf.get_line(0)
        assert line[0].underline is True
        assert line[1].underline is False

    def test_24bit_foreground(self):
        buf = AnsiBuffer()
        buf.feed("\033[38;2;255;128;0mcolored\033[0m")
        line = buf.get_line(0)
        assert line[0].fg == "#ff8000"

    def test_24bit_background(self):
        buf = AnsiBuffer()
        buf.feed("\033[48;2;0;255;0mhighlighted\033[0m")
        line = buf.get_line(0)
        assert line[0].bg == "#00ff00"

    def test_default_foreground_reset(self):
        buf = AnsiBuffer()
        buf.feed("\033[38;2;255;0;0mred\033[39mdefault")
        line = buf.get_line(0)
        assert line[0].fg == "#ff0000"
        assert line[1].fg is None

    def test_default_background_reset(self):
        buf = AnsiBuffer()
        buf.feed("\033[48;2;0;0;255mbg\033[49mno_bg")
        line = buf.get_line(0)
        assert line[0].bg == "#0000ff"
        assert line[1].bg is None

    def test_combined_sgr_params(self):
        buf = AnsiBuffer()
        buf.feed("\033[1;3;4mcombo\033[0m")
        line = buf.get_line(0)
        assert line[0].bold is True
        assert line[0].italic is True
        assert line[0].underline is True


class TestAnsiBufferCarriageReturn:
    """Tests for carriage return and line clearing."""

    def test_carriage_return_resets_cursor(self):
        buf = AnsiBuffer()
        buf.feed("overwrite\rNew")
        text = buf.get_line_text(0)
        assert text.startswith("New")
        assert text == "Newrwrite"

    def test_clear_to_eol(self):
        buf = AnsiBuffer()
        buf.feed("full line\r\033[K")
        text = buf.get_line_text(0)
        assert text == ""

    def test_clear_to_eol_partial(self):
        buf = AnsiBuffer()
        buf.feed("abcdef")
        buf._cursor_col = 3
        buf.feed("\033[K")
        text = buf.get_line_text(0)
        assert text == "abc"


class TestAnsiBufferDirtyTracking:
    """Tests for dirty line tracking."""

    def test_feed_marks_lines_dirty(self):
        buf = AnsiBuffer()
        buf.feed("line0\nline1\nline2")
        assert 0 in buf.dirty_lines
        assert 1 in buf.dirty_lines
        assert 2 in buf.dirty_lines

    def test_clear_resets_dirty(self):
        buf = AnsiBuffer()
        buf.feed("text\nmore")
        buf.clear()
        assert len(buf.dirty_lines) == 0

    def test_carriage_return_marks_dirty(self):
        buf = AnsiBuffer()
        buf.feed("text")
        buf.dirty_lines.clear()
        buf.feed("\r")
        assert 0 in buf.dirty_lines


class TestAnsiBufferGetLine:
    """Tests for line access methods."""

    def test_get_line_valid(self):
        buf = AnsiBuffer()
        buf.feed("hello")
        line = buf.get_line(0)
        assert len(line) >= 1
        assert line[0].text == "hello"

    def test_get_line_out_of_range(self):
        buf = AnsiBuffer()
        assert buf.get_line(-1) == []
        assert buf.get_line(99) == []

    def test_get_line_text_out_of_range(self):
        buf = AnsiBuffer()
        assert buf.get_line_text(99) == ""


class TestAnsiBufferOverwrite:
    """Tests for text overwriting at cursor position."""

    def test_overwrite_middle_of_line(self):
        buf = AnsiBuffer()
        buf.feed("ABCDEF")
        buf._cursor_col = 2
        buf.feed("XY")
        text = buf.get_line_text(0)
        assert text == "ABXYEF"

    def test_append_past_end(self):
        buf = AnsiBuffer()
        buf.feed("AB")
        buf.feed("CD")
        text = buf.get_line_text(0)
        assert text == "ABCD"


class TestAnsiBufferIncrementalFeed:
    """Tests for incremental (chunked) feeding."""

    def test_split_ansi_sequence_across_feeds(self):
        buf = AnsiBuffer()
        buf.feed("\033[1m")
        buf.feed("bold")
        buf.feed("\033[0m")
        buf.feed("normal")
        text = buf.get_text()
        assert text == "boldnormal"
        line = buf.get_line(0)
        assert line[0].bold is True
        assert line[1].bold is False

    def test_split_text_across_feeds(self):
        buf = AnsiBuffer()
        buf.feed("hel")
        buf.feed("lo")
        assert buf.get_text() == "hello"

    def test_newline_in_separate_feed(self):
        buf = AnsiBuffer()
        buf.feed("line1")
        buf.feed("\n")
        buf.feed("line2")
        assert buf.get_line_count() == 2
        assert buf.get_line_text(0) == "line1"
        assert buf.get_line_text(1) == "line2"
