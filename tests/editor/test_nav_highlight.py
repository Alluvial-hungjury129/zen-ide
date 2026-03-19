"""Tests for editor/nav_highlight.py."""

from editor.nav_highlight import NavigationHighlight


class _FakeTag:
    def __init__(self):
        self.props = type("Props", (), {"background": None})()


class _FakeTagTable:
    def __init__(self):
        self._tag = None

    def lookup(self, _name):
        return self._tag

    def remove(self, _tag):
        self._tag = None


class _FakeIter:
    def __init__(self, buffer_text: str, offset: int):
        self._text = buffer_text
        self._offset = max(0, min(len(buffer_text), offset))

    def copy(self):
        return _FakeIter(self._text, self._offset)

    def get_offset(self):
        return self._offset

    def ends_line(self):
        return self._offset >= len(self._text) or self._text[self._offset] == "\n"

    def forward_to_line_end(self):
        while self._offset < len(self._text) and self._text[self._offset] != "\n":
            self._offset += 1

    def forward_char(self):
        if self._offset < len(self._text):
            self._offset += 1

    def set_line_offset(self, line_offset: int):
        line_start = self._text.rfind("\n", 0, self._offset) + 1
        self._offset = min(len(self._text), line_start + max(0, line_offset))


class _FakeBuffer:
    def __init__(self, text: str):
        self.text = text
        self.tag_table = _FakeTagTable()
        self.applied_range = None

    def get_iter_at_line(self, line_0: int):
        offset = 0
        if line_0 > 0:
            lines_seen = 0
            for idx, ch in enumerate(self.text):
                if ch == "\n":
                    lines_seen += 1
                    if lines_seen == line_0:
                        offset = idx + 1
                        break
        return (True, _FakeIter(self.text, offset))

    def get_iter_at_offset(self, offset: int):
        return (True, _FakeIter(self.text, offset))

    def get_text(self, start_iter, end_iter, _include_hidden):
        return self.text[start_iter.get_offset() : end_iter.get_offset()]

    def get_tag_table(self):
        return self.tag_table

    def create_tag(self, _name, **_kwargs):
        self.tag_table._tag = _FakeTag()
        return self.tag_table._tag

    def apply_tag_by_name(self, _name, start_iter, end_iter):
        self.applied_range = (start_iter.get_offset(), end_iter.get_offset())

    def get_start_iter(self):
        return _FakeIter(self.text, 0)

    def get_end_iter(self):
        return _FakeIter(self.text, len(self.text))

    def remove_tag_by_name(self, _name, _start, _end):
        return None


def test_apply_highlight_rebuilds_iters_from_offsets(monkeypatch):
    nav = NavigationHighlight()
    buf = _FakeBuffer("abcdef")

    monkeypatch.setattr("editor.nav_highlight.get_theme", lambda: type("T", (), {"accent_color": "#112233"})())
    monkeypatch.setattr("editor.nav_highlight.GLib.timeout_add", lambda *_args, **_kwargs: 1)

    nav._apply_highlight(buf, 2, 5, hold_duration_ms=50, fade_step_ms=10)

    assert buf.applied_range == (2, 5)


def test_highlight_symbol_uses_symbol_offsets(monkeypatch):
    nav = NavigationHighlight()
    buf = _FakeBuffer("prefix target suffix\n")
    captured = {}

    def _capture_apply(_buffer, start_offset, end_offset, _hold, _fade):
        captured["range"] = (start_offset, end_offset)

    nav._apply_highlight = _capture_apply
    nav.highlight_symbol(buf, line=1, symbol="target")

    assert captured["range"] == (7, 13)
