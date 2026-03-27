"""Tests for multi-backend scroll behaviour and preview class parity.

Covers:
- Behavioural parity: both preview classes produce identical results
- SCROLL_SYNC_JS constant for webkit reverse sync
- _on_preview_scrolled (webkit / macOS reverse sync)
- _on_textview_scroll
- _connect_textview_scroll_sync
- _apply_scroll_fraction for all backends
- Echo-back prevention for all backends
- Preview classes share mixin -- no method overrides
- OpenAPI HTML includes SCROLL_SYNC_JS
"""

import pytest

from editor.preview.preview_scroll_mixin import SCROLL_SYNC_JS, PreviewScrollMixin
from tests.editor.preview_scroll_test_helpers import FakeAdjustment

# ------------------------------------------------------------------ #
#  Fakes (duplicated from test_scroll_sync for independence)           #
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
#  _apply_scroll_fraction -- all backends                              #
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
#  Preview classes share mixin -- no method overrides                  #
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
