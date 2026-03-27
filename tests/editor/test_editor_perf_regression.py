"""Regression tests for editor-open and tab-close performance fixes.

Covers:
- Language detection caching and extension-first ordering
- EditorTab.__init__ does NOT call expensive methods on empty buffer
- Tab close persistence is deferred (not synchronous)
- Semantic highlight visible-range limiting
- IDE state update debouncing
"""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Language detection caching
# ---------------------------------------------------------------------------
class TestLanguageDetectCache:
    """Verify detect_language uses the cache and prefers extension lookup."""

    def setup_method(self):
        from editor.langs.language_detect import _detect_cache

        _detect_cache.clear()

    def teardown_method(self):
        from editor.langs.language_detect import _detect_cache

        _detect_cache.clear()

    def test_cache_hit_skips_gio(self):
        """Second call for same extension should not invoke Gio."""
        from editor.langs.language_detect import detect_language

        # First call populates cache
        lang1 = detect_language("/fake/test.py")

        # Patch Gio to verify it's NOT called on second hit
        with patch("editor.langs.language_detect.Gio") as mock_gio:
            lang2 = detect_language("/other/file.py")
            mock_gio.content_type_guess.assert_not_called()

        assert lang1 is not None
        assert lang2 is not None
        assert lang1.get_id() == lang2.get_id()

    def test_extension_first_before_gio(self):
        """Extensions in _EXT_TO_LANG should resolve without Gio.content_type_guess."""
        from editor.langs.language_detect import detect_language

        with patch("editor.langs.language_detect.Gio") as mock_gio:
            lang = detect_language("/fake/test.json")
            # Gio should NOT be called — extension lookup is first
            mock_gio.content_type_guess.assert_not_called()

        assert lang is not None
        assert lang.get_id() == "json"

    def test_cache_stores_none_as_sentinel(self):
        """Unknown extensions should cache False sentinel, not retry Gio."""
        from editor.langs.language_detect import _detect_cache, detect_language

        # Force a miss with an unknown extension
        with patch("editor.langs.language_detect.Gio") as mock_gio:
            mock_gio.content_type_guess.return_value = (None, False)
            result = detect_language("/fake/file.zzzzz")

        assert result is None
        # Cache should contain the sentinel
        assert any(v is False for v in _detect_cache.values())

        # Second call should NOT invoke Gio again
        with patch("editor.langs.language_detect.Gio") as mock_gio:
            detect_language("/other/file.zzzzz")
            mock_gio.content_type_guess.assert_not_called()

    def test_different_extensions_cached_separately(self):
        from editor.langs.language_detect import _detect_cache, detect_language

        # Clear cache to ensure clean state
        _detect_cache.clear()

        py_lang = detect_language("/a/test.py")
        js_lang = detect_language("/a/test.js")

        assert py_lang.get_id() == "python3"
        assert js_lang is not None
        assert js_lang.get_id() in ("javascript", "js")
        assert len(_detect_cache) >= 2


# ---------------------------------------------------------------------------
# EditorTab.__init__ — no wasted work on empty buffer
# ---------------------------------------------------------------------------
class TestEditorTabInitOptimization:
    """Verify __init__ skips expensive calls that load_file will handle."""

    def test_init_does_not_set_language(self):
        """__init__ should NOT call _set_language_from_file (buffer is empty)."""
        with patch("editor.editor_view.EditorTab._set_language_from_file") as mock_lang:
            from editor.editor_view import EditorTab

            tab = EditorTab(file_path="/fake/test.py")
            mock_lang.assert_not_called()

    def test_init_does_not_set_gutter_diff_path(self):
        """__init__ should NOT call gutter_diff.set_file_path (load_file does it)."""
        from editor.editor_view import EditorTab

        tab = EditorTab(file_path="/fake/test.py")
        # Gutter diff should exist but NOT have fetched HEAD content
        assert tab._gutter_diff is not None
        assert tab._gutter_diff._file_path is None

    def test_autocomplete_is_lazy(self):
        """Autocomplete should NOT be created in __init__."""
        from editor.editor_view import EditorTab

        tab = EditorTab(file_path="/fake/test.py")
        assert tab._autocomplete is None

    def test_ensure_autocomplete_creates_on_demand(self):
        """_ensure_autocomplete should create the Autocomplete on first call."""
        from editor.editor_view import EditorTab

        tab = EditorTab(file_path="/fake/test.py")
        assert tab._autocomplete is None
        ac = tab._ensure_autocomplete()
        assert ac is not None
        assert tab._autocomplete is ac
        # Second call returns same instance
        assert tab._ensure_autocomplete() is ac


# ---------------------------------------------------------------------------
# Tab close — deferred persistence
# ---------------------------------------------------------------------------
class TestTabClosePersistence:
    """Verify tab close doesn't block on sync I/O."""

    def test_on_tab_closed_does_not_call_save_workspace_directly(self):
        """save_workspace should NOT be called synchronously — it's deferred."""
        from main.window_events_mixin import WindowEventsMixin

        obj = MagicMock(spec=WindowEventsMixin)
        obj.editor_view = MagicMock()
        obj.editor_view.tabs = MagicMock()
        obj.editor_view.tabs.values.return_value = []
        obj.editor_view.get_current_file_path.return_value = ""
        obj._update_ide_state_file = MagicMock()

        with patch("shared.settings.save_workspace") as mock_save:
            WindowEventsMixin._on_tab_closed(obj)
            # save_workspace should NOT be called directly (it's deferred via idle_add)
            mock_save.assert_not_called()

    def test_update_ide_state_uses_debounce(self):
        """_update_ide_state_file should create a Debouncer instance."""
        from main.window_state_mixin import WindowStateMixin

        obj = MagicMock(spec=WindowStateMixin)
        obj._ide_state_debouncer = None

        # Call the real method — it should lazily create a Debouncer
        WindowStateMixin._update_ide_state_file(obj)

        assert obj._ide_state_debouncer is not None
        from shared.debouncer import Debouncer

        assert isinstance(obj._ide_state_debouncer, Debouncer)


# ---------------------------------------------------------------------------
# Semantic highlight — visible range limiting
# ---------------------------------------------------------------------------
class TestSemanticHighlightVisibleRange:
    """Verify semantic highlighting is limited to visible viewport."""

    def test_extract_tokens_with_byte_range_prunes(self):
        """extract_semantic_tokens should accept vis_start_byte/vis_end_byte."""
        try:
            from editor.tree_sitter_semantic import extract_semantic_tokens
        except ImportError:
            pytest.skip("tree-sitter not available")

        # Verify the function signature accepts the range parameters
        import inspect

        sig = inspect.signature(extract_semantic_tokens)
        params = list(sig.parameters.keys())
        assert "vis_start_byte" in params
        assert "vis_end_byte" in params

    def test_walk_prunes_nodes_outside_range(self):
        """_walk should skip nodes entirely outside vis byte range."""
        try:
            from editor.tree_sitter_semantic import _walk
        except ImportError:
            pytest.skip("tree-sitter not available")

        import inspect

        sig = inspect.signature(_walk)
        params = list(sig.parameters.keys())
        assert "vis_start_byte" in params
        assert "vis_end_byte" in params

        # Create a mock node outside the visible range
        node = MagicMock()
        node.start_byte = 1000
        node.end_byte = 2000
        node.type = "identifier"
        node.children = []

        tokens = []
        _walk(
            node,
            tokens,
            frozenset(),
            "python",
            lambda *a: None,
            frozenset(),
            lambda _: frozenset(),
            vis_start_byte=0,
            vis_end_byte=500,
        )

        # Node was entirely outside range → should be pruned, no tokens
        assert len(tokens) == 0


# ---------------------------------------------------------------------------
# Color preview — no eager scan on empty buffer
# ---------------------------------------------------------------------------
class TestColorPreviewInit:
    """Verify ColorPreviewRenderer doesn't scan empty buffer on init."""

    def test_no_idle_add_on_init(self):
        """Init should NOT schedule an eager idle_add scan."""
        with patch("editor.color_preview_renderer.GLib") as mock_glib:
            from editor.color_preview_renderer import ColorPreviewRenderer

            view = MagicMock()
            view.get_buffer.return_value = MagicMock()

            renderer = ColorPreviewRenderer(view)

            # idle_add should NOT be called (was removed as optimization)
            mock_glib.idle_add.assert_not_called()
