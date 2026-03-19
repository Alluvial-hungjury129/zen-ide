"""Tests for context_gatherer — building FIM context from editor state."""

from editor.inline_completion.context_gatherer import (
    _MAX_PREFIX_CHARS,
    _MAX_SUFFIX_CHARS,
    CompletionContext,
    gather_context,
)
from tests.editor.inline_completion.test_helpers import make_mock_tab as _make_mock_tab

# ---------------------------------------------------------------------------
# CompletionContext dataclass
# ---------------------------------------------------------------------------


class TestCompletionContext:
    def test_creation(self):
        ctx = CompletionContext(
            prefix="def foo(",
            suffix="):\n    pass",
            file_path="/tmp/test.py",
            language="python",
            cursor_line=1,
            cursor_col=8,
        )
        assert ctx.prefix == "def foo("
        assert ctx.suffix == "):\n    pass"
        assert ctx.language == "python"
        assert ctx.cursor_line == 1
        assert ctx.cursor_col == 8

    def test_empty_context(self):
        ctx = CompletionContext(
            prefix="",
            suffix="",
            file_path="",
            language="",
            cursor_line=0,
            cursor_col=0,
        )
        assert ctx.prefix == ""
        assert ctx.file_path == ""


# ---------------------------------------------------------------------------
# gather_context
# ---------------------------------------------------------------------------


class TestGatherContext:
    def test_basic_context(self):
        tab = _make_mock_tab("def foo():\n    pass", cursor_offset=10)
        ctx = gather_context(tab)

        assert ctx.prefix == "def foo():"
        assert ctx.suffix == "\n    pass"
        assert ctx.language == "python"
        assert ctx.file_path == "/tmp/test.py"

    def test_cursor_position(self):
        # "abc\nd" — cursor at offset 5 means line 1 (second line), col 1 ('d')
        tab = _make_mock_tab("abc\ndef", cursor_offset=5)
        ctx = gather_context(tab)
        # get_line returns 1 (0-based), gather_context adds 1 → cursor_line=2
        assert ctx.cursor_line == 2
        assert ctx.cursor_col == 1

    def test_no_language(self):
        tab = _make_mock_tab(language_id=None)
        ctx = gather_context(tab)
        assert ctx.language == ""

    def test_python3_normalized(self):
        tab = _make_mock_tab(language_id="python3")
        ctx = gather_context(tab)
        assert ctx.language == "python"

    def test_no_file_path(self):
        tab = _make_mock_tab(file_path=None)
        ctx = gather_context(tab)
        assert ctx.file_path == ""

    def test_prefix_truncated(self):
        long_text = "a" * (_MAX_PREFIX_CHARS + 500) + "CURSOR_HERE"
        tab = _make_mock_tab(long_text, cursor_offset=len(long_text) - len("CURSOR_HERE"))
        ctx = gather_context(tab)
        assert len(ctx.prefix) <= _MAX_PREFIX_CHARS

    def test_suffix_truncated(self):
        suffix_text = "b" * (_MAX_SUFFIX_CHARS + 500)
        text = "prefix" + suffix_text
        tab = _make_mock_tab(text, cursor_offset=6)
        ctx = gather_context(tab)
        assert len(ctx.suffix) <= _MAX_SUFFIX_CHARS
