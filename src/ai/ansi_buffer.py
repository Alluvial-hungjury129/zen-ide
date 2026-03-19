"""AnsiBuffer — parses ANSI-escaped text into styled lines for DrawingArea rendering."""


class StyledSpan:
    """A run of text with consistent styling."""

    __slots__ = ("text", "fg", "bg", "bold", "dim", "italic", "underline")

    def __init__(self, text, fg=None, bg=None, bold=False, dim=False, italic=False, underline=False):
        self.text = text
        self.fg = fg
        self.bg = bg
        self.bold = bold
        self.dim = dim
        self.italic = italic
        self.underline = underline

    def copy_style(self):
        """Return a new StyledSpan with the same style but empty text."""
        return StyledSpan("", self.fg, self.bg, self.bold, self.dim, self.italic, self.underline)


class AnsiBuffer:
    """Parses ANSI-escaped text and stores styled lines.

    Handles the limited ANSI subset produced by TerminalMarkdownRenderer:
    - SGR: reset(0), bold(1), dim(2), italic(3), underline(4)
    - 24-bit foreground: 38;2;R;G;B
    - 24-bit background: 48;2;R;G;B
    - Carriage return (\\r) — cursor to start of line
    - Clear to end of line (\\033[K)
    """

    def __init__(self):
        self.lines: list[list[StyledSpan]] = [[]]
        self._cursor_col = 0
        # Dirty line tracking for incremental rendering
        self.dirty_lines: set[int] = set()
        # Current style state
        self._fg = None
        self._bg = None
        self._bold = False
        self._dim = False
        self._italic = False
        self._underline = False

    def feed(self, text: str):
        """Parse text with ANSI codes and append to buffer."""
        i = 0
        buf = []  # accumulate plain chars

        while i < len(text):
            ch = text[i]

            if ch == "\033" and i + 1 < len(text) and text[i + 1] == "[":
                # Flush accumulated text
                if buf:
                    self._emit("".join(buf))
                    buf.clear()
                # Parse CSI sequence
                i = self._parse_csi(text, i)
                continue

            if ch == "\r":
                if buf:
                    self._emit("".join(buf))
                    buf.clear()
                self._cursor_col = 0
                self.dirty_lines.add(len(self.lines) - 1)
                i += 1
                continue

            if ch == "\n":
                if buf:
                    self._emit("".join(buf))
                    buf.clear()
                self.lines.append([])
                self._cursor_col = 0
                self.dirty_lines.add(len(self.lines) - 1)
                i += 1
                continue

            buf.append(ch)
            i += 1

        if buf:
            self._emit("".join(buf))

    def feed_bytes(self, data: bytes):
        """Feed raw bytes (convenience wrapper — decodes UTF-8)."""
        self.feed(data.decode("utf-8", errors="replace"))

    def clear(self):
        """Clear all content."""
        self.lines = [[]]
        self._cursor_col = 0
        self.dirty_lines.clear()
        self._reset_style()

    def get_text(self) -> str:
        """Get plain text content (all lines joined by newlines)."""
        return "\n".join("".join(s.text for s in line) for line in self.lines)

    def get_line_count(self) -> int:
        return len(self.lines)

    def get_line(self, n: int) -> list[StyledSpan]:
        if 0 <= n < len(self.lines):
            return self.lines[n]
        return []

    def get_line_text(self, n: int) -> str:
        """Get plain text of a single line."""
        return "".join(s.text for s in self.get_line(n))

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _parse_csi(self, text: str, start: int) -> int:
        """Parse CSI escape sequence starting at \\033[. Returns index past the sequence."""
        i = start + 2  # skip \033[
        params = []
        current_param = ""

        while i < len(text):
            ch = text[i]
            if ch.isdigit():
                current_param += ch
                i += 1
            elif ch == ";":
                params.append(int(current_param) if current_param else 0)
                current_param = ""
                i += 1
            elif ch.isalpha():
                params.append(int(current_param) if current_param else 0)
                i += 1  # consume the command letter
                self._handle_csi(ch, params)
                return i
            else:
                # Unknown char — bail out
                i += 1
                return i

        return i  # reached end of text without closing the sequence

    def _handle_csi(self, command: str, params: list[int]):
        if command == "m":
            self._handle_sgr(params)
        elif command == "K":
            mode = params[0] if params else 0
            if mode == 0:
                self._clear_to_eol()

    def _handle_sgr(self, params: list[int]):
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                self._reset_style()
            elif p == 1:
                self._bold = True
            elif p == 2:
                self._dim = True
            elif p == 3:
                self._italic = True
            elif p == 4:
                self._underline = True
            elif p == 22:
                self._bold = False
                self._dim = False
            elif p == 23:
                self._italic = False
            elif p == 24:
                self._underline = False
            elif p == 38 and i + 1 < len(params) and params[i + 1] == 2:
                # 24-bit foreground: 38;2;R;G;B
                if i + 4 < len(params):
                    r, g, b = params[i + 2], params[i + 3], params[i + 4]
                    self._fg = f"#{r:02x}{g:02x}{b:02x}"
                    i += 4
                else:
                    i = len(params)
                    break
            elif p == 48 and i + 1 < len(params) and params[i + 1] == 2:
                # 24-bit background: 48;2;R;G;B
                if i + 4 < len(params):
                    r, g, b = params[i + 2], params[i + 3], params[i + 4]
                    self._bg = f"#{r:02x}{g:02x}{b:02x}"
                    i += 4
                else:
                    i = len(params)
                    break
            elif p == 39:
                self._fg = None
            elif p == 49:
                self._bg = None
            i += 1

    def _reset_style(self):
        self._fg = None
        self._bg = None
        self._bold = False
        self._dim = False
        self._italic = False
        self._underline = False

    def _emit(self, text: str):
        """Append styled text at the current cursor position."""
        if not text:
            return

        span = StyledSpan(
            text=text,
            fg=self._fg,
            bg=self._bg,
            bold=self._bold,
            dim=self._dim,
            italic=self._italic,
            underline=self._underline,
        )

        line_idx = len(self.lines) - 1
        line = self.lines[line_idx]
        text_len = len(text)

        if self._cursor_col == 0:
            if not line:
                line.append(span)
            else:
                self._overwrite_at(0, span)
        else:
            existing_len = sum(len(s.text) for s in line)
            if self._cursor_col >= existing_len:
                line.append(span)
            else:
                self._overwrite_at(self._cursor_col, span)

        self._cursor_col += text_len
        self.dirty_lines.add(line_idx)

    def _overwrite_at(self, col: int, new_span: StyledSpan):
        """Overwrite content starting at `col` with new_span's text."""
        line = self.lines[-1]
        new_len = len(new_span.text)
        end_col = col + new_len

        # Collect spans before, at, and after the overwrite range
        before = []
        after = []
        pos = 0

        for span in line:
            span_end = pos + len(span.text)

            if span_end <= col:
                # Entirely before overwrite
                before.append(span)
            elif pos >= end_col:
                # Entirely after overwrite
                after.append(span)
            else:
                # Overlaps with overwrite
                if pos < col:
                    # Keep the part before col
                    keep = span.text[: col - pos]
                    before.append(StyledSpan(keep, span.fg, span.bg, span.bold, span.dim, span.italic, span.underline))
                if span_end > end_col:
                    # Keep the part after end_col
                    keep = span.text[end_col - pos :]
                    after.append(StyledSpan(keep, span.fg, span.bg, span.bold, span.dim, span.italic, span.underline))

            pos = span_end

        self.lines[-1] = before + [new_span] + after

    def _clear_to_eol(self):
        """Clear from cursor to end of line."""
        line_idx = len(self.lines) - 1
        self.dirty_lines.add(line_idx)
        if self._cursor_col == 0:
            self.lines[-1] = []
            return

        line = self.lines[-1]
        new_line = []
        pos = 0
        for span in line:
            span_end = pos + len(span.text)
            if span_end <= self._cursor_col:
                new_line.append(span)
            elif pos < self._cursor_col:
                keep_len = self._cursor_col - pos
                new_line.append(
                    StyledSpan(
                        span.text[:keep_len],
                        span.fg,
                        span.bg,
                        span.bold,
                        span.dim,
                        span.italic,
                        span.underline,
                    )
                )
            pos = span_end
        self.lines[-1] = new_line
