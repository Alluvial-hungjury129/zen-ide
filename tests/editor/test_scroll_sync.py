"""Tests for scroll synchronization in PreviewScrollMixin.

Covers:
- _init_scroll_sync state setup
- _connect_canvas_scroll_sync wiring
- _on_canvas_scroll echo-back suppression (syncing + animation guards)
- scroll_to_source_line sets guard + delegates to canvas
- scroll_to_fraction throttling + guard
- _apply_scroll_fraction canvas path
- _apply_scroll_fraction_throttled clears pending flag
- _clear_syncing_flag lifecycle
- Signal integration: value-changed triggers correct path
"""

import pytest

from editor.preview.preview_scroll_mixin import PreviewScrollMixin
from tests.editor.preview_scroll_test_helpers import FakeAdjustment

# ------------------------------------------------------------------ #
#  Fakes                                                               #
# ------------------------------------------------------------------ #


class FakeScrolledWindow:
    """Minimal Gtk.ScrolledWindow stand-in."""

    def __init__(self, adj=None):
        self._adj = adj or FakeAdjustment()

    def get_vadjustment(self):
        return self._adj

    def set_kinetic_scrolling(self, v):
        self._kinetic = v


class FakeCanvas:
    """Minimal MarkdownCanvas stand-in."""

    def __init__(self):
        self._is_animation_adjusting = False
        self._scroll_line_calls = []
        self._scroll_value_calls = []

    @property
    def is_animation_adjusting(self):
        return self._is_animation_adjusting

    def scroll_to_source_line(self, line):
        self._scroll_line_calls.append(line)

    def scroll_to_value(self, val):
        self._scroll_value_calls.append(val)


class ConcretePreview(PreviewScrollMixin):
    """Concrete subclass for testing the mixin in isolation."""

    def __init__(self, backend="canvas"):
        self._backend = backend
        self._init_scroll_sync()


# ------------------------------------------------------------------ #
#  _init_scroll_sync                                                   #
# ------------------------------------------------------------------ #


class TestInitScrollSync:
    """_init_scroll_sync must set all required state."""

    def test_initial_state(self):
        p = ConcretePreview()
        assert p._on_preview_scroll_callback is None
        assert p._syncing_scroll is False
        assert p._syncing_scroll_timer_id == 0
        assert p._scroll_sync_pending is False
        assert p._target_fraction == 0.0

    def test_is_syncing_scroll_property(self):
        p = ConcretePreview()
        assert p.is_syncing_scroll is False
        p._syncing_scroll = True
        assert p.is_syncing_scroll is True


# ------------------------------------------------------------------ #
#  _connect_canvas_scroll_sync                                         #
# ------------------------------------------------------------------ #


class TestConnectCanvasScrollSync:
    """_connect_canvas_scroll_sync must wire kinetic scrolling + signals."""

    def test_enables_kinetic_scrolling(self):
        p = ConcretePreview()
        sw = FakeScrolledWindow()
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        assert sw._kinetic is True

    def test_stores_references(self):
        p = ConcretePreview()
        sw = FakeScrolledWindow()
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        assert p._canvas_scrolled is sw
        assert p._canvas is canvas

    def test_connects_value_changed(self):
        p = ConcretePreview()
        adj = FakeAdjustment()
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        assert len(adj._cbs) == 1


# ------------------------------------------------------------------ #
#  _on_canvas_scroll                                                   #
# ------------------------------------------------------------------ #


class TestOnCanvasScroll:
    """_on_canvas_scroll echo-back suppression."""

    def _make_wired_preview(self, value=400.0, upper=1000.0, page_size=200.0):
        p = ConcretePreview()
        adj = FakeAdjustment(value=value, upper=upper, page_size=page_size)
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        return p, adj, canvas

    def test_fires_callback_normally(self):
        p, adj, _ = self._make_wired_preview()
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        p._on_canvas_scroll(adj)
        assert len(results) == 1
        assert results[0] == pytest.approx(0.5)  # 400/(1000-200)

    def test_stores_target_fraction(self):
        p, adj, _ = self._make_wired_preview()
        p._on_canvas_scroll(adj)
        assert p._target_fraction == pytest.approx(0.5)

    def test_suppressed_when_syncing(self):
        p, adj, _ = self._make_wired_preview()
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        p._syncing_scroll = True
        p._on_canvas_scroll(adj)
        assert len(results) == 0

    def test_suppressed_when_animation_adjusting(self):
        p, adj, canvas = self._make_wired_preview()
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        canvas._is_animation_adjusting = True
        p._on_canvas_scroll(adj)
        assert len(results) == 0

    def test_suppressed_when_both_guards(self):
        p, adj, canvas = self._make_wired_preview()
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        p._syncing_scroll = True
        canvas._is_animation_adjusting = True
        p._on_canvas_scroll(adj)
        assert len(results) == 0

    def test_fires_after_guards_cleared(self):
        p, adj, canvas = self._make_wired_preview()
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))

        # Blocked
        p._syncing_scroll = True
        canvas._is_animation_adjusting = True
        p._on_canvas_scroll(adj)
        assert len(results) == 0

        # Unblocked
        p._syncing_scroll = False
        canvas._is_animation_adjusting = False
        p._on_canvas_scroll(adj)
        assert len(results) == 1

    def test_zero_fraction_when_content_fits_page(self):
        p, adj, _ = self._make_wired_preview(value=0.0, upper=100.0, page_size=200.0)
        p._on_canvas_scroll(adj)
        assert p._target_fraction == 0.0

    def test_no_callback_when_none(self):
        """No crash when callback is not set."""
        p, adj, _ = self._make_wired_preview()
        p._on_canvas_scroll(adj)  # Should not raise


# ------------------------------------------------------------------ #
#  scroll_to_source_line                                               #
# ------------------------------------------------------------------ #


class TestScrollToSourceLine:
    """scroll_to_source_line must set guard + delegate to canvas."""

    def test_delegates_to_canvas(self):
        p = ConcretePreview()
        sw = FakeScrolledWindow()
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        p.scroll_to_source_line(42)
        assert canvas._scroll_line_calls == [42]

    def test_sets_syncing_flag(self):
        p = ConcretePreview()
        sw = FakeScrolledWindow()
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        p.scroll_to_source_line(42)
        assert p._syncing_scroll is True

    def test_noop_when_not_canvas_backend(self):
        p = ConcretePreview(backend="webkit_gtk")
        p.scroll_to_source_line(42)
        assert not hasattr(p, "_canvas") or not hasattr(p._canvas, "_scroll_line_calls")

    def test_noop_when_no_canvas_attr(self):
        p = ConcretePreview()
        # Don't connect canvas
        p.scroll_to_source_line(42)
        # Should not raise


# ------------------------------------------------------------------ #
#  scroll_to_fraction                                                  #
# ------------------------------------------------------------------ #


class TestScrollToFraction:
    """scroll_to_fraction must clamp, set guard, and throttle."""

    def test_clamps_to_range(self):
        p = ConcretePreview()
        p.scroll_to_fraction(-0.5)
        assert p._target_fraction == 0.0
        p.scroll_to_fraction(1.5)
        assert p._target_fraction == 1.0

    def test_sets_syncing_flag(self):
        p = ConcretePreview()
        p.scroll_to_fraction(0.5)
        assert p._syncing_scroll is True

    def test_sets_pending_flag(self):
        p = ConcretePreview()
        p.scroll_to_fraction(0.5)
        assert p._scroll_sync_pending is True


# ------------------------------------------------------------------ #
#  _apply_scroll_fraction                                              #
# ------------------------------------------------------------------ #


class TestApplyScrollFraction:
    """_apply_scroll_fraction canvas path."""

    def test_scrolls_canvas_to_correct_value(self):
        p = ConcretePreview()
        adj = FakeAdjustment(value=0.0, upper=1000.0, page_size=200.0)
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        p._target_fraction = 0.5
        p._apply_scroll_fraction()
        # 0.5 * (1000 - 200) = 400
        assert canvas._scroll_value_calls == [400.0]

    def test_noop_when_no_scrolled_window(self):
        p = ConcretePreview()
        p._target_fraction = 0.5
        p._apply_scroll_fraction()  # Should not raise

    def test_noop_when_content_fits_page(self):
        p = ConcretePreview()
        adj = FakeAdjustment(value=0.0, upper=100.0, page_size=200.0)
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        p._target_fraction = 0.5
        p._apply_scroll_fraction()
        assert canvas._scroll_value_calls == []


# ------------------------------------------------------------------ #
#  _apply_scroll_fraction_throttled                                    #
# ------------------------------------------------------------------ #


class TestApplyScrollFractionThrottled:
    """Throttled wrapper clears pending flag."""

    def test_clears_pending_flag(self):
        p = ConcretePreview()
        adj = FakeAdjustment()
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        p._scroll_sync_pending = True
        p._target_fraction = 0.3
        result = p._apply_scroll_fraction_throttled()
        assert p._scroll_sync_pending is False
        assert result is False  # GLib.idle_add expects False to stop


# ------------------------------------------------------------------ #
#  _clear_syncing_flag                                                 #
# ------------------------------------------------------------------ #


class TestClearSyncingFlag:
    """_clear_syncing_flag lifecycle."""

    def test_resets_flag_and_timer(self):
        p = ConcretePreview()
        p._syncing_scroll = True
        p._syncing_scroll_timer_id = 999
        result = p._clear_syncing_flag()
        assert p._syncing_scroll is False
        assert p._syncing_scroll_timer_id == 0
        assert result is False  # GLib.timeout_add expects False to stop


# ------------------------------------------------------------------ #
#  Integration: value-changed signal triggers correct path             #
# ------------------------------------------------------------------ #


class TestSignalIntegration:
    """When adj.set_value fires value-changed, _on_canvas_scroll runs."""

    def test_value_changed_triggers_callback(self):
        p = ConcretePreview()
        adj = FakeAdjustment(value=0.0, upper=1000.0, page_size=200.0)
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)

        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))

        adj.set_value(400.0)
        assert len(results) == 1
        assert results[0] == pytest.approx(0.5)

    def test_value_changed_suppressed_during_animation(self):
        p = ConcretePreview()
        adj = FakeAdjustment(value=0.0, upper=1000.0, page_size=200.0)
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)

        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        canvas._is_animation_adjusting = True

        adj.set_value(400.0)
        assert len(results) == 0

    def test_echo_back_cycle_prevented(self):
        """Full editor->preview->editor cycle: no echo-back."""
        p = ConcretePreview()
        adj = FakeAdjustment(value=0.0, upper=1000.0, page_size=200.0)
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)

        echo_calls = []
        p.set_on_preview_scroll(lambda f: echo_calls.append(f))

        # Editor initiates scroll -> sets syncing guard
        p._syncing_scroll = True
        adj.set_value(500.0)

        # _on_canvas_scroll fires but is blocked by _syncing_scroll
        assert len(echo_calls) == 0
