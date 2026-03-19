"""Shared helpers for inline completion tests."""

from unittest.mock import MagicMock, patch

from editor.inline_completion.context_gatherer import CompletionContext
from editor.inline_completion.inline_completion_manager import InlineCompletionManager


def make_completion_context(**overrides) -> CompletionContext:
    """Create CompletionContext with sensible defaults."""
    defaults = dict(
        prefix="def hello(",
        suffix=")\n    pass",
        file_path="/tmp/test.py",
        language="python",
        cursor_line=1,
        cursor_col=10,
    )
    defaults.update(overrides)
    return CompletionContext(**defaults)


def make_mock_tab(text="def foo():\n    pass", cursor_offset=10, file_path="/tmp/test.py", language_id="python"):
    """Create a mock EditorTab with buffer for gather_context tests."""
    tab = MagicMock()
    tab.file_path = file_path

    buf = MagicMock()
    tab.buffer = buf

    lang = MagicMock()
    lang.get_id.return_value = language_id
    buf.get_language.return_value = lang if language_id else None

    prefix_text = text[:cursor_offset]
    suffix_text = text[cursor_offset:]

    cursor_iter = MagicMock()
    cursor_iter.get_line.return_value = prefix_text.count("\n")
    last_line = prefix_text.split("\n")[-1]
    cursor_iter.get_line_offset.return_value = len(last_line)

    insert_mark = MagicMock()
    buf.get_insert.return_value = insert_mark
    buf.get_iter_at_mark.return_value = cursor_iter

    start_iter = MagicMock()
    end_iter = MagicMock()
    buf.get_start_iter.return_value = start_iter
    buf.get_end_iter.return_value = end_iter

    def mock_get_text(s, e, include_hidden):
        if s is start_iter and e is cursor_iter:
            return prefix_text
        if s is cursor_iter and e is end_iter:
            return suffix_text
        return ""

    buf.get_text.side_effect = mock_get_text
    return tab


def make_manager(**overrides):
    """Create InlineCompletionManager with mocked dependencies."""
    with patch.object(InlineCompletionManager, "__init__", lambda self, *a, **kw: None):
        manager = InlineCompletionManager.__new__(InlineCompletionManager)

    manager._tab = MagicMock()
    manager._tab.buffer = MagicMock()
    manager._tab.view = MagicMock()
    manager._renderer = MagicMock()
    manager._renderer.is_active = False
    manager._renderer._inserting = False
    manager._provider = MagicMock()
    manager._trigger_timer_id = None
    manager._enabled = True
    manager._changed_handler_id = None
    manager._suggestions = []
    manager._suggestion_index = 0
    manager._debounce = MagicMock()
    manager._debounce.get_delay_ms.return_value = 500

    for key, value in overrides.items():
        setattr(manager, key, value)

    return manager


def setting_side_effect(values: dict[str, object]):
    """Build a get_setting-compatible side effect from a dict."""
    return lambda key, default=None: values.get(key, default)
