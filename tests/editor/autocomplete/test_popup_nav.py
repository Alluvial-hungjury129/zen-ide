"""Tests for popup navigation — show/dismiss/suppress, signature preview, escape sequences.

Covers:
- _extract_params: function parameter extraction for auto-insertion
- No popup on deletion: auto-trigger only fires on character insertions
- No popup in comments: auto-trigger skips comment context
- No popup on exact match: suppressed when only suggestion matches typed word
- Auto-dismiss on exact match: live-filtering hides popup when sole match = typed word
- Dot-trigger: typing '.' after an identifier triggers completions
- Docstring in signature preview
"""

from unittest.mock import MagicMock, patch

from editor.autocomplete.autocomplete import Autocomplete, CompletionItem, CompletionKind

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_autocomplete(**overrides):
    """Create an Autocomplete with mocked GTK dependencies for unit testing."""
    with patch.object(Autocomplete, "__init__", lambda self, *a, **kw: None):
        ac = Autocomplete.__new__(Autocomplete)

    ac._completions = []
    ac._filtered = []
    ac._selected_idx = 0
    ac._word_start_offset = 0
    ac._inserting = False
    ac._auto_trigger_timer = None
    ac._last_buffer_len = 0
    ac._changed_handler = None
    ac._dismiss_guard = False
    ac._dismiss_guard_timer = None
    ac._focus_suppress_idle = None

    ac._buffer = MagicMock()
    ac._view = MagicMock()
    ac._popup = MagicMock()
    ac._listbox = MagicMock()
    ac._sig_box = MagicMock()
    ac._sig_sep = MagicMock()
    ac._sig_buffer = MagicMock()
    ac._sig_view = MagicMock()
    ac._hbox = MagicMock()
    ac._tab = MagicMock()
    ac._python_provider = MagicMock()
    ac._js_provider = MagicMock()
    ac._terraform_provider = MagicMock()
    ac._css_provider = None

    for k, v in overrides.items():
        setattr(ac, k, v)
    return ac


def _mock_buffer(char_count, *, in_comment=False, cursor_offset=0, dot_before=False, char_before_dot="_"):
    """Build a mock GtkSource.Buffer for _on_auto_trigger_change tests."""
    buf = MagicMock()
    buf.get_char_count.return_value = char_count
    buf.get_insert.return_value = MagicMock()

    cursor_iter = MagicMock()
    cursor_iter.get_offset.return_value = cursor_offset
    buf.get_iter_at_mark.return_value = cursor_iter
    buf.iter_has_context_class.return_value = in_comment

    if dot_before:
        # cursor_iter.copy() for dot_iter, then backward_char gets '.'
        dot_iter = MagicMock()
        dot_iter.get_char.return_value = "."
        before_dot = MagicMock()
        before_dot.get_char.return_value = char_before_dot
        dot_iter.copy.return_value = before_dot
        cursor_iter.copy.return_value = dot_iter
    return buf


# ---------------------------------------------------------------------------
# _extract_params
# ---------------------------------------------------------------------------


class TestExtractParams:
    """Test _extract_params for function parameter auto-insertion."""

    def test_simple_params(self):
        assert Autocomplete._extract_params("func(a, b, c)") == "a, b, c"

    def test_strips_self(self):
        assert Autocomplete._extract_params("method(self, x, y)") == "x, y"

    def test_strips_cls(self):
        assert Autocomplete._extract_params("create(cls, name)") == "name"

    def test_strips_type_annotations(self):
        assert Autocomplete._extract_params("func(a: int, b: str) → bool") == "a, b"

    def test_preserves_default_values(self):
        assert Autocomplete._extract_params("func(a=1, b='hello')") == "a=1, b='hello'"

    def test_empty_params(self):
        assert Autocomplete._extract_params("func()") == ""

    def test_no_signature(self):
        assert Autocomplete._extract_params("") == ""

    def test_no_parens(self):
        assert Autocomplete._extract_params("my_variable") == ""

    def test_self_only(self):
        assert Autocomplete._extract_params("method(self)") == ""

    def test_complex_signature(self):
        sig = "process(self, name: str, count: int = 0, verbose: bool = False) → list"
        assert Autocomplete._extract_params(sig) == "name, count=0, verbose=False"

    def test_cls_with_annotations(self):
        assert Autocomplete._extract_params("from_config(cls, config: dict) → MyClass") == "config"

    def test_mixed_self_and_defaults(self):
        sig = "run(self, path: str = '/tmp', dry: bool = True)"
        assert Autocomplete._extract_params(sig) == "path='/tmp', dry=True"


# ---------------------------------------------------------------------------
# No popup on deletion
# ---------------------------------------------------------------------------


class TestNoPopupOnDeletion:
    """Auto-trigger should only fire when characters are inserted, not deleted."""

    def test_deletion_does_not_trigger(self):
        ac = _make_autocomplete(_last_buffer_len=20)
        buf = _mock_buffer(19)  # deletion: 20 → 19
        ac._popup.get_visible.return_value = False

        with patch("editor.autocomplete.autocomplete.get_setting", return_value=True):
            ac._on_auto_trigger_change(buf)

        assert ac._last_buffer_len == 19
        assert ac._auto_trigger_timer is None

    def test_same_length_does_not_trigger(self):
        ac = _make_autocomplete(_last_buffer_len=10)
        buf = _mock_buffer(10)  # replace, same length
        ac._popup.get_visible.return_value = False

        with patch("editor.autocomplete.autocomplete.get_setting", return_value=True):
            ac._on_auto_trigger_change(buf)

        assert ac._auto_trigger_timer is None

    def test_insertion_updates_buffer_len(self):
        ac = _make_autocomplete(_last_buffer_len=10)
        buf = _mock_buffer(11, cursor_offset=11)
        ac._popup.get_visible.return_value = False
        ac._get_word_at_cursor = MagicMock(return_value="ab")  # below threshold

        with patch("editor.autocomplete.autocomplete.get_setting", return_value=True):
            ac._on_auto_trigger_change(buf)

        assert ac._last_buffer_len == 11

    def test_bulk_insertion_does_not_trigger(self):
        """File load / paste of many chars should not trigger autocomplete."""
        ac = _make_autocomplete(_last_buffer_len=0)
        buf = _mock_buffer(500, cursor_offset=500)  # e.g. opening a file
        ac._popup.get_visible.return_value = False

        with patch("editor.autocomplete.autocomplete.get_setting", return_value=True):
            ac._on_auto_trigger_change(buf)

        assert ac._last_buffer_len == 500
        assert ac._auto_trigger_timer is None


# ---------------------------------------------------------------------------
# No popup in comments
# ---------------------------------------------------------------------------


class TestNoPopupInComments:
    """Auto-trigger should skip when cursor is inside a comment."""

    def test_comment_context_skips_trigger(self):
        ac = _make_autocomplete(_last_buffer_len=10)
        buf = _mock_buffer(11, in_comment=True)  # insertion inside comment
        ac._popup.get_visible.return_value = False

        with patch("editor.autocomplete.autocomplete.get_setting", return_value=True):
            ac._on_auto_trigger_change(buf)

        assert ac._auto_trigger_timer is None

    def test_non_comment_allows_trigger(self):
        ac = _make_autocomplete(_last_buffer_len=10)
        buf = _mock_buffer(11, in_comment=False, cursor_offset=11)
        ac._popup.get_visible.return_value = False
        ac._get_word_at_cursor = MagicMock(return_value="onboarding")  # >= 3 chars

        with (
            patch("editor.autocomplete.autocomplete.get_setting", return_value=True),
            patch("editor.autocomplete.autocomplete.GLib") as mock_glib,
        ):
            mock_glib.timeout_add.return_value = 42
            mock_glib.source_remove = MagicMock()
            ac._on_auto_trigger_change(buf)

        assert ac._auto_trigger_timer == 42


# ---------------------------------------------------------------------------
# Dot-trigger
# ---------------------------------------------------------------------------


class TestDotTrigger:
    """Typing '.' after an identifier should schedule auto-trigger."""

    def test_dot_after_identifier_triggers(self):
        ac = _make_autocomplete(_last_buffer_len=15)
        buf = _mock_buffer(16, in_comment=False, cursor_offset=16, dot_before=True, char_before_dot="t")
        ac._popup.get_visible.return_value = False
        ac._get_word_at_cursor = MagicMock(return_value="")  # empty after dot

        with (
            patch("editor.autocomplete.autocomplete.get_setting", return_value=True),
            patch("editor.autocomplete.autocomplete.GLib") as mock_glib,
        ):
            mock_glib.timeout_add.return_value = 99
            mock_glib.source_remove = MagicMock()
            ac._on_auto_trigger_change(buf)

        assert ac._auto_trigger_timer == 99

    def test_dot_after_space_no_trigger(self):
        ac = _make_autocomplete(_last_buffer_len=5)
        buf = _mock_buffer(6, in_comment=False, cursor_offset=6, dot_before=True, char_before_dot=" ")
        ac._popup.get_visible.return_value = False
        ac._get_word_at_cursor = MagicMock(return_value="")

        with patch("editor.autocomplete.autocomplete.get_setting", return_value=True):
            ac._on_auto_trigger_change(buf)

        assert ac._auto_trigger_timer is None

    def test_dot_after_number_triggers(self):
        """Dot after digit (e.g. dict or numeric attr) should also trigger."""
        ac = _make_autocomplete(_last_buffer_len=5)
        buf = _mock_buffer(6, in_comment=False, cursor_offset=6, dot_before=True, char_before_dot="3")
        ac._popup.get_visible.return_value = False
        ac._get_word_at_cursor = MagicMock(return_value="")

        with (
            patch("editor.autocomplete.autocomplete.get_setting", return_value=True),
            patch("editor.autocomplete.autocomplete.GLib") as mock_glib,
        ):
            mock_glib.timeout_add.return_value = 77
            mock_glib.source_remove = MagicMock()
            ac._on_auto_trigger_change(buf)

        assert ac._auto_trigger_timer == 77


# ---------------------------------------------------------------------------
# Skip exact match on show
# ---------------------------------------------------------------------------


class TestSkipExactMatchOnShow:
    """Popup should not appear if the only suggestion is an exact match of typed text."""

    def test_single_exact_match_suppresses_popup(self):
        ac = _make_autocomplete()

        # Simulate what show() does: set completions, run _update_filter, check
        ac._completions = [CompletionItem("onboarding_client", CompletionKind.VARIABLE)]
        ac._update_filter("onboarding_client")

        assert len(ac._filtered) == 1
        assert ac._filtered[0].name == "onboarding_client"
        # This is the condition in show() that suppresses the popup
        should_skip = len(ac._filtered) == 1 and ac._filtered[0].name == "onboarding_client"
        assert should_skip

    def test_partial_match_does_not_suppress(self):
        ac = _make_autocomplete()
        ac._completions = [
            CompletionItem("onboarding_client", CompletionKind.VARIABLE),
            CompletionItem("onboarding_config", CompletionKind.VARIABLE),
        ]
        ac._update_filter("onboarding")

        assert len(ac._filtered) == 2
        should_skip = len(ac._filtered) == 1 and ac._filtered[0].name == "onboarding"
        assert not should_skip

    def test_single_non_exact_match_does_not_suppress(self):
        ac = _make_autocomplete()
        ac._completions = [CompletionItem("onboarding_client", CompletionKind.VARIABLE)]
        ac._update_filter("onboarding")

        assert len(ac._filtered) == 1
        should_skip = len(ac._filtered) == 1 and ac._filtered[0].name == "onboarding"
        assert not should_skip


# ---------------------------------------------------------------------------
# Auto-dismiss on exact match during live filtering
# ---------------------------------------------------------------------------


class TestAutoDismissOnExactMatch:
    """Popup should auto-dismiss when live-filtering leaves only an exact match."""

    def _setup_buffer_changed(self, ac, partial):
        """Configure mocks for _on_buffer_changed with a given partial word."""
        cursor_iter = MagicMock()
        cursor_iter.get_offset.return_value = ac._word_start_offset + len(partial)

        word_start_iter = MagicMock()
        ac._buffer.get_iter_at_mark.return_value = cursor_iter
        ac._buffer.get_iter_at_offset.return_value = word_start_iter
        ac._buffer.get_text.return_value = partial
        ac._buffer.get_char_count.return_value = ac._word_start_offset + len(partial)

    def test_exact_match_dismisses(self):
        ac = _make_autocomplete(_word_start_offset=0)
        ac._completions = [CompletionItem("onboarding_client", CompletionKind.VARIABLE)]
        ac._popup.get_visible.return_value = True

        self._setup_buffer_changed(ac, "onboarding_client")

        with patch("editor.autocomplete.completion_popup.get_theme"):
            ac._on_buffer_changed(ac._buffer)

        ac._popup.popdown.assert_called()

    def test_partial_does_not_dismiss(self):
        ac = _make_autocomplete(_word_start_offset=0)
        ac._completions = [
            CompletionItem("onboarding_client", CompletionKind.VARIABLE),
            CompletionItem("onboarding_config", CompletionKind.VARIABLE),
        ]
        ac._popup.get_visible.return_value = True

        self._setup_buffer_changed(ac, "onboarding")

        with patch("editor.autocomplete.completion_popup.get_theme"):
            ac._on_buffer_changed(ac._buffer)

        ac._popup.popdown.assert_not_called()

    def test_no_matches_hides_popup(self):
        ac = _make_autocomplete(_word_start_offset=0)
        ac._completions = [CompletionItem("foo", CompletionKind.VARIABLE)]
        ac._popup.get_visible.return_value = True

        self._setup_buffer_changed(ac, "bar")

        with patch("editor.autocomplete.completion_popup.get_theme"):
            ac._on_buffer_changed(ac._buffer)

        # hide() is called which calls popdown
        ac._popup.popdown.assert_called()


# ---------------------------------------------------------------------------
# Docstring in signature preview
# ---------------------------------------------------------------------------


class TestSignaturePreviewDocstring:
    """Test that _update_signature_preview shows docstrings."""

    def test_signature_only(self):
        ac = _make_autocomplete()
        ac._popup.get_visible = MagicMock(return_value=True)
        ac._sig_box.get_visible = MagicMock(return_value=False)
        ac._filtered = [CompletionItem("foo", CompletionKind.FUNCTION, "foo(x, y)")]
        ac._selected_idx = 0
        ac._update_signature_preview()
        ac._sig_buffer.set_text.assert_called_with("foo(x, y)")
        ac._sig_box.set_visible.assert_called_with(True)
        ac._sig_sep.set_visible.assert_called_with(True)

    def test_signature_and_docstring(self):
        ac = _make_autocomplete()
        ac._popup.get_visible = MagicMock(return_value=True)
        ac._sig_box.get_visible = MagicMock(return_value=False)
        ac._filtered = [CompletionItem("foo", CompletionKind.FUNCTION, "foo(x)", "Do something")]
        ac._selected_idx = 0
        ac._update_signature_preview()
        ac._sig_buffer.set_text.assert_called_with("foo(x)\n# Do something")
        ac._sig_box.set_visible.assert_called_with(True)

    def test_docstring_only_no_signature(self):
        ac = _make_autocomplete()
        ac._popup.get_visible = MagicMock(return_value=True)
        ac._sig_box.get_visible = MagicMock(return_value=False)
        ac._filtered = [CompletionItem("MyClass", CompletionKind.PROPERTY, "", "A useful class")]
        ac._selected_idx = 0
        ac._update_signature_preview()
        ac._sig_buffer.set_text.assert_called_with("# A useful class")
        ac._sig_box.set_visible.assert_called_with(True)

    def test_no_signature_no_docstring(self):
        ac = _make_autocomplete()
        ac._popup.get_visible = MagicMock(return_value=True)
        ac._sig_box.get_visible = MagicMock(return_value=True)
        ac._filtered = [CompletionItem("x", CompletionKind.VARIABLE)]
        ac._selected_idx = 0
        ac._update_signature_preview()
        ac._sig_box.set_visible.assert_called_with(False)
        ac._sig_sep.set_visible.assert_called_with(False)
