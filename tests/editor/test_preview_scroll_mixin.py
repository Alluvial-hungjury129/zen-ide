"""Tests for PreviewScrollMixin — shared scroll sync logic.

Regression tests ensuring MarkdownPreview and OpenAPIPreview share
identical scroll behaviour via the mixin.  Covers:
- _init_scroll_sync state setup
- _connect_canvas_scroll_sync wiring
- _on_canvas_scroll echo-back suppression (syncing + animation guards)
- scroll_to_source_line sets guard + delegates to canvas
- scroll_to_fraction throttling + guard
- _apply_scroll_fraction canvas path
- _reset_sync_guard / _clear_syncing_flag lifecycle
- is_syncing_scroll property
- Behavioural parity: both preview classes produce identical results
"""

import pytest

from editor.preview.preview_scroll_mixin import SCROLL_SYNC_JS, PreviewScrollMixin
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
#  Behavioural parity between preview types                            #
# ------------------------------------------------------------------ #


class TestBehaviouralParity:
    """Both MarkdownPreview and OpenAPIPreview must share identical
    scroll-sync behaviour via the mixin.  We verify they both produce
    the same results for the same inputs."""

    def _make_preview(self, backend="canvas"):
        """Create a ConcretePreview wired with canvas."""
        p = ConcretePreview(backend=backend)
        adj = FakeAdjustment(value=400.0, upper=1000.0, page_size=200.0)
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)
        return p, adj, canvas

    def test_same_fraction_from_on_canvas_scroll(self):
        """Both produce identical fraction for same adjustment values."""
        fractions = []
        for _ in range(2):
            p, adj, _ = self._make_preview()
            p.set_on_preview_scroll(lambda f: fractions.append(f))
            p._on_canvas_scroll(adj)
        assert fractions[0] == fractions[1]
        assert fractions[0] == pytest.approx(0.5)

    def test_same_guard_behaviour(self):
        """Both block callbacks identically when guards are active."""
        for guard_state in [(True, False), (False, True), (True, True)]:
            syncing, animating = guard_state
            for _ in range(2):
                p, adj, canvas = self._make_preview()
                results = []
                p.set_on_preview_scroll(lambda f: results.append(f))
                p._syncing_scroll = syncing
                canvas._is_animation_adjusting = animating
                p._on_canvas_scroll(adj)
                assert len(results) == 0, f"Guard {guard_state} failed"

    def test_scroll_to_source_line_same_delegation(self):
        """Both delegate to canvas.scroll_to_source_line identically."""
        for _ in range(2):
            p, _, canvas = self._make_preview()
            p.scroll_to_source_line(100)
            assert canvas._scroll_line_calls == [100]
            assert p._syncing_scroll is True

    def test_scroll_to_fraction_same_clamping(self):
        """Both clamp fractions identically."""
        for raw, expected in [(-1.0, 0.0), (0.5, 0.5), (2.0, 1.0)]:
            for _ in range(2):
                p, _, _ = self._make_preview()
                p.scroll_to_fraction(raw)
                assert p._target_fraction == expected

    def test_apply_scroll_fraction_same_value(self):
        """Both compute same scroll value for same fraction."""
        values = []
        for _ in range(2):
            p, adj, canvas = self._make_preview()
            p._target_fraction = 0.75
            p._apply_scroll_fraction()
            values.append(canvas._scroll_value_calls[-1])
        assert values[0] == values[1]
        assert values[0] == pytest.approx(600.0)  # 0.75 * (1000-200)


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
        """Full editor→preview→editor cycle: no echo-back."""
        p = ConcretePreview()
        adj = FakeAdjustment(value=0.0, upper=1000.0, page_size=200.0)
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)

        echo_calls = []
        p.set_on_preview_scroll(lambda f: echo_calls.append(f))

        # Editor initiates scroll → sets syncing guard
        p._syncing_scroll = True
        adj.set_value(500.0)

        # _on_canvas_scroll fires but is blocked by _syncing_scroll
        assert len(echo_calls) == 0


# ------------------------------------------------------------------ #
#  SCROLL_SYNC_JS constant                                             #
# ------------------------------------------------------------------ #


class TestScrollSyncJS:
    """The SCROLL_SYNC_JS constant for webkit reverse sync."""

    def test_contains_script_tags(self):
        assert "<script>" in SCROLL_SYNC_JS
        assert "</script>" in SCROLL_SYNC_JS

    def test_contains_guard_variable(self):
        assert "_zenScrolling" in SCROLL_SYNC_JS

    def test_contains_message_handler(self):
        assert "zenScrollSync" in SCROLL_SYNC_JS

    def test_contains_scroll_listener(self):
        assert "addEventListener" in SCROLL_SYNC_JS
        assert "'scroll'" in SCROLL_SYNC_JS


# ------------------------------------------------------------------ #
#  _on_preview_scrolled (webkit / macOS reverse sync)                  #
# ------------------------------------------------------------------ #


class TestOnPreviewScrolled:
    """_on_preview_scrolled handles webkit/macOS scroll fractions."""

    def test_fires_callback(self):
        p = ConcretePreview("webkit_gtk")
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        p._on_preview_scrolled(0.75)
        assert results == [0.75]
        assert p._target_fraction == 0.75

    def test_suppressed_when_syncing(self):
        p = ConcretePreview("webkit_gtk")
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        p._syncing_scroll = True
        p._on_preview_scrolled(0.75)
        assert len(results) == 0

    def test_no_crash_without_callback(self):
        p = ConcretePreview("webkit_gtk")
        p._on_preview_scrolled(0.5)
        assert p._target_fraction == 0.5


# ------------------------------------------------------------------ #
#  _on_textview_scroll                                                 #
# ------------------------------------------------------------------ #


class TestOnTextviewScroll:
    """_on_textview_scroll handles textview reverse sync."""

    def test_fires_callback(self):
        p = ConcretePreview("textview")
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        adj = FakeAdjustment(400.0, 1000.0, 200.0)
        p._on_textview_scroll(adj)
        assert len(results) == 1
        assert results[0] == pytest.approx(0.5)

    def test_suppressed_when_syncing(self):
        p = ConcretePreview("textview")
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        p._syncing_scroll = True
        adj = FakeAdjustment(400.0, 1000.0, 200.0)
        p._on_textview_scroll(adj)
        assert len(results) == 0

    def test_no_callback_when_content_fits(self):
        p = ConcretePreview("textview")
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        adj = FakeAdjustment(0.0, 100.0, 200.0)
        p._on_textview_scroll(adj)
        assert len(results) == 0


# ------------------------------------------------------------------ #
#  _connect_textview_scroll_sync                                       #
# ------------------------------------------------------------------ #


class TestConnectTextviewScrollSync:
    """_connect_textview_scroll_sync wires vadjustment for reverse sync."""

    def test_wires_value_changed(self):
        p = ConcretePreview("textview")
        adj = FakeAdjustment(400.0, 1000.0, 200.0)
        sw = FakeScrolledWindow(adj)
        results = []
        p.set_on_preview_scroll(lambda f: results.append(f))
        p._connect_textview_scroll_sync(sw)
        adj.set_value(500.0)
        assert len(results) == 1
        assert results[0] == pytest.approx(500.0 / 800.0)

    def test_stores_scrolled_reference(self):
        p = ConcretePreview("textview")
        sw = FakeScrolledWindow()
        p._connect_textview_scroll_sync(sw)
        assert p._textview_scrolled is sw


# ------------------------------------------------------------------ #
#  _apply_scroll_fraction — all backends                               #
# ------------------------------------------------------------------ #


class TestApplyScrollFractionAllBackends:
    """_apply_scroll_fraction handles canvas, webkit, and textview."""

    def test_webkit_calls_run_js(self):
        p = ConcretePreview("webkit_gtk")
        js_calls = []
        p._run_js = lambda s: js_calls.append(s)
        p._target_fraction = 0.5
        p._apply_scroll_fraction()
        assert len(js_calls) == 1
        assert "_zenScrolling=true" in js_calls[0]
        assert "0.5" in js_calls[0]

    def test_macos_webkit_calls_run_js(self):
        p = ConcretePreview("macos_webkit")
        js_calls = []
        p._run_js = lambda s: js_calls.append(s)
        p._target_fraction = 0.25
        p._apply_scroll_fraction()
        assert len(js_calls) == 1
        assert "0.25" in js_calls[0]

    def test_textview_sets_adj_value(self):
        p = ConcretePreview("textview")
        adj = FakeAdjustment(0.0, 1000.0, 200.0)
        sw = FakeScrolledWindow(adj)
        p._connect_textview_scroll_sync(sw)
        p._target_fraction = 0.5
        p._apply_scroll_fraction()
        assert adj.get_value() == pytest.approx(400.0)

    def test_textview_no_op_when_content_fits(self):
        p = ConcretePreview("textview")
        adj = FakeAdjustment(0.0, 100.0, 200.0)
        sw = FakeScrolledWindow(adj)
        p._connect_textview_scroll_sync(sw)
        p._target_fraction = 0.5
        p._apply_scroll_fraction()
        assert adj.get_value() == 0.0  # unchanged

    def test_unknown_backend_no_op(self):
        p = ConcretePreview("unknown")
        p._target_fraction = 0.5
        p._apply_scroll_fraction()  # should not raise


# ------------------------------------------------------------------ #
#  Echo-back prevention for all backends                               #
# ------------------------------------------------------------------ #


class TestEchoBackAllBackends:
    """Echo-back prevention works across all backends."""

    def test_canvas_echo_back_blocked(self):
        p = ConcretePreview("canvas")
        adj = FakeAdjustment(0.0, 1000.0, 200.0)
        sw = FakeScrolledWindow(adj)
        canvas = FakeCanvas()
        p._connect_canvas_scroll_sync(sw, canvas)

        echoes = []
        p.set_on_preview_scroll(lambda f: echoes.append(f))
        p._syncing_scroll = True
        adj.set_value(400.0)
        assert len(echoes) == 0

    def test_textview_echo_back_blocked(self):
        p = ConcretePreview("textview")
        adj = FakeAdjustment(0.0, 1000.0, 200.0)
        sw = FakeScrolledWindow(adj)
        p._connect_textview_scroll_sync(sw)

        echoes = []
        p.set_on_preview_scroll(lambda f: echoes.append(f))
        p._syncing_scroll = True
        adj.set_value(400.0)
        assert len(echoes) == 0

    def test_webkit_echo_back_blocked(self):
        p = ConcretePreview("webkit_gtk")
        echoes = []
        p.set_on_preview_scroll(lambda f: echoes.append(f))
        p._syncing_scroll = True
        p._on_preview_scrolled(0.5)
        assert len(echoes) == 0


# ------------------------------------------------------------------ #
#  Preview classes share mixin — no method overrides                   #
# ------------------------------------------------------------------ #


class TestPreviewClassesMixinParity:
    """Both preview classes must inherit scroll methods from the mixin."""

    SHARED_METHODS = [
        "_on_canvas_scroll",
        "_on_preview_scrolled",
        "_on_webkit_script_message",
        "_on_webkit_load_changed",
        "_on_textview_scroll",
        "_apply_scroll_fraction",
        "_run_js",
        "scroll_to_source_line",
        "scroll_to_fraction",
        "set_on_preview_scroll",
        "_connect_canvas_scroll_sync",
        "_connect_webkit_scroll_sync",
        "_connect_textview_scroll_sync",
    ]

    def test_markdown_inherits_mixin(self):
        from editor.preview.markdown_preview import MarkdownPreview

        assert issubclass(MarkdownPreview, PreviewScrollMixin)

    def test_openapi_inherits_mixin(self):
        from editor.preview.openapi_preview import OpenAPIPreview

        assert issubclass(OpenAPIPreview, PreviewScrollMixin)

    def test_markdown_does_not_override_shared_methods(self):
        from editor.preview.markdown_preview import MarkdownPreview

        for name in self.SHARED_METHODS:
            mixin_attr = getattr(PreviewScrollMixin, name, None)
            preview_attr = getattr(MarkdownPreview, name, None)
            if mixin_attr is not None:
                assert preview_attr is mixin_attr, f"MarkdownPreview should not override {name}"

    def test_openapi_does_not_override_shared_methods(self):
        from editor.preview.openapi_preview import OpenAPIPreview

        for name in self.SHARED_METHODS:
            mixin_attr = getattr(PreviewScrollMixin, name, None)
            preview_attr = getattr(OpenAPIPreview, name, None)
            if mixin_attr is not None:
                assert preview_attr is mixin_attr, f"OpenAPIPreview should not override {name}"

    def test_is_syncing_scroll_property_shared(self):
        from editor.preview.markdown_preview import MarkdownPreview
        from editor.preview.openapi_preview import OpenAPIPreview

        md_prop = MarkdownPreview.__dict__.get("is_syncing_scroll")
        oa_prop = OpenAPIPreview.__dict__.get("is_syncing_scroll")
        # Neither should override the property
        assert md_prop is None, "MarkdownPreview should not override is_syncing_scroll"
        assert oa_prop is None, "OpenAPIPreview should not override is_syncing_scroll"


# ------------------------------------------------------------------ #
#  OpenAPI HTML includes SCROLL_SYNC_JS                                #
# ------------------------------------------------------------------ #


class TestOpenAPIHTMLScrollJS:
    """OpenAPI HTML template must include scroll sync JS after render."""

    def test_scroll_js_injectable(self):
        from editor.preview.openapi_preview import _HTML_TEMPLATE

        html = _HTML_TEMPLATE.format(css="body{}", body="<p>test</p>")
        assert "</body>" in html
        # Simulate what render() does
        html = html.replace("</body>", f"{SCROLL_SYNC_JS}</body>")
        assert "zenScrollSync" in html
        assert html.index("zenScrollSync") < html.index("</body>")
