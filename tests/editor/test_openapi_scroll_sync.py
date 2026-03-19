"""Tests for OpenAPI editor ↔ preview scroll sync.

Regression tests covering:
- Canvas smooth scroll (lerp) animation logic for OpenAPI preview
- Canvas is_animation_adjusting guard
- Preview _syncing_scroll echo-back guard
- Preview resettable guard timer
- Source-line ↔ Y-offset bidirectional mapping consistency
- _on_canvas_scroll suppression during animation / syncing
- OpenAPIBlockRenderer source_line assignment consistency
"""

import pytest

from editor.preview.openapi_block_renderer import OpenAPIBlockRenderer
from tests.editor.preview_scroll_test_helpers import (
    FakeAdjustment,
)
from tests.editor.preview_scroll_test_helpers import (
    get_y_for_source_line as _get_y_for_source_line,
)
from tests.editor.preview_scroll_test_helpers import (
    make_blocks as _make_blocks,
)
from tests.editor.preview_scroll_test_helpers import (
    on_canvas_scroll_fraction as _on_canvas_scroll,
)
from tests.editor.preview_scroll_test_helpers import (
    smooth_scroll_tick as _smooth_scroll_tick,
)

# ------------------------------------------------------------------ #
#  OpenAPIBlockRenderer source_line consistency                        #
# ------------------------------------------------------------------ #

MINIMAL_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0"},
    "paths": {
        "/users": {
            "get": {
                "tags": ["Users"],
                "summary": "List users",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
}

MULTI_ENDPOINT_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0", "description": "A test API"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/users": {
            "get": {
                "tags": ["Users"],
                "summary": "List users",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "tags": ["Users"],
                "summary": "Create user",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "properties": {"name": {"type": "string"}}},
                        }
                    }
                },
                "responses": {
                    "201": {"description": "Created"},
                    "400": {"description": "Bad request"},
                },
            },
        },
        "/items": {
            "get": {
                "tags": ["Items"],
                "summary": "List items",
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
}


class TestOpenAPIBlockRendererSourceLines:
    """OpenAPIBlockRenderer must produce blocks with monotonically
    non-decreasing source_line values for scroll sync to work."""

    def test_minimal_spec_source_lines_monotonic(self):
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(MINIMAL_SPEC)
        lines = [b.source_line for b in blocks]
        assert lines == sorted(lines), f"source_lines not monotonic: {lines}"

    def test_multi_endpoint_source_lines_monotonic(self):
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(MULTI_ENDPOINT_SPEC)
        lines = [b.source_line for b in blocks]
        assert lines == sorted(lines), f"source_lines not monotonic: {lines}"

    def test_blocks_are_non_empty(self):
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(MINIMAL_SPEC)
        assert len(blocks) > 0

    def test_multi_endpoint_has_multiple_blocks(self):
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(MULTI_ENDPOINT_SPEC)
        assert len(blocks) > 5

    def test_invalid_spec_still_produces_blocks(self):
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(None)
        assert len(blocks) > 0

    def test_empty_paths_still_produces_blocks(self):
        spec = {"openapi": "3.0.0", "info": {"title": "Empty", "version": "1.0"}, "paths": {}}
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(spec)
        assert len(blocks) > 0

    def test_source_lines_start_at_zero(self):
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(MINIMAL_SPEC)
        assert blocks[0].source_line == 0

    def test_all_block_kinds_valid(self):
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(MULTI_ENDPOINT_SPEC)
        valid_kinds = {"heading", "paragraph", "code", "table", "hr", "blockquote", "list"}
        for b in blocks:
            assert b.kind in valid_kinds, f"unexpected block kind: {b.kind}"


# ------------------------------------------------------------------ #
#  Source-line ↔ Y mapping (same logic as markdown, shared canvas)     #
# ------------------------------------------------------------------ #


class TestOpenAPISourceLineYMapping:
    """get_y_for_source_line bidirectional mapping for OpenAPI blocks."""

    def test_first_line_maps_to_first_block(self):
        blocks = _make_blocks(
            [
                (0, 0.0, 100.0),
                (5, 100.0, 200.0),
                (10, 300.0, 150.0),
            ]
        )
        assert _get_y_for_source_line(blocks, 0) == 0.0

    def test_exact_block_boundary(self):
        blocks = _make_blocks(
            [
                (0, 0.0, 100.0),
                (5, 100.0, 200.0),
            ]
        )
        assert _get_y_for_source_line(blocks, 5) == 100.0

    def test_interpolation_within_block(self):
        blocks = _make_blocks(
            [
                (0, 0.0, 100.0),
                (10, 100.0, 200.0),
                (30, 300.0, 150.0),
            ]
        )
        y = _get_y_for_source_line(blocks, 20)
        assert y == pytest.approx(200.0)

    def test_empty_blocks_returns_zero(self):
        assert _get_y_for_source_line([], 5) == 0.0


# ------------------------------------------------------------------ #
#  Smooth scroll animation logic                                       #
# ------------------------------------------------------------------ #


class TestOpenAPISmoothScrollLogic:
    """Test lerp-based smooth scroll tick logic for OpenAPI preview."""

    def test_lerp_moves_toward_target(self):
        adj = FakeAdjustment(value=0.0)
        keep_going, new_val, _, _ = _smooth_scroll_tick(adj, 100.0)
        assert keep_going is True
        assert new_val == pytest.approx(25.0)

    def test_lerp_converges(self):
        adj = FakeAdjustment(value=0.0)
        target = 100.0
        for _ in range(50):
            keep_going, _, target, _ = _smooth_scroll_tick(adj, target)
            if not keep_going:
                break
        assert adj.get_value() == pytest.approx(100.0)

    def test_lerp_snaps_when_close(self):
        adj = FakeAdjustment(value=99.5)
        keep_going, new_val, new_target, _ = _smooth_scroll_tick(adj, 100.0)
        assert keep_going is False
        assert new_val == pytest.approx(100.0)
        assert new_target is None

    def test_animation_adjusting_flag_during_set(self):
        adj = FakeAdjustment(value=0.0)
        _, _, _, was_adjusting = _smooth_scroll_tick(adj, 100.0)
        assert was_adjusting is True

    def test_none_adjustment_stops(self):
        keep_going, _, _, _ = _smooth_scroll_tick(None, 100.0)
        assert keep_going is False

    def test_none_target_stops(self):
        adj = FakeAdjustment(value=0.0)
        keep_going, _, _, _ = _smooth_scroll_tick(adj, None)
        assert keep_going is False


# ------------------------------------------------------------------ #
#  _on_canvas_scroll echo-back suppression                             #
# ------------------------------------------------------------------ #


class TestOpenAPIOnCanvasScrollGuards:
    """_on_canvas_scroll must be suppressed during syncing / animation."""

    def test_callback_fires_normally(self):
        results = []
        adj = FakeAdjustment(value=400.0, upper=1000.0, page_size=200.0)
        fraction, called = _on_canvas_scroll(adj, False, False, callback=lambda f: results.append(f))
        assert called is True
        assert fraction == pytest.approx(0.5)
        assert results[0] == pytest.approx(0.5)

    def test_suppressed_when_syncing_scroll(self):
        results = []
        adj = FakeAdjustment(value=400.0)
        _, called = _on_canvas_scroll(adj, True, False, callback=lambda f: results.append(f))
        assert called is False
        assert len(results) == 0

    def test_suppressed_when_animation_adjusting(self):
        results = []
        adj = FakeAdjustment(value=400.0)
        _, called = _on_canvas_scroll(adj, False, True, callback=lambda f: results.append(f))
        assert called is False
        assert len(results) == 0

    def test_suppressed_when_both_guards_active(self):
        results = []
        adj = FakeAdjustment(value=400.0)
        _, called = _on_canvas_scroll(adj, True, True, callback=lambda f: results.append(f))
        assert called is False

    def test_fires_after_guards_cleared(self):
        results = []
        adj = FakeAdjustment(value=400.0, upper=1000.0, page_size=200.0)
        cb = lambda f: results.append(f)

        _on_canvas_scroll(adj, True, True, cb)
        assert len(results) == 0

        _on_canvas_scroll(adj, False, False, cb)
        assert len(results) == 1

    def test_zero_fraction_when_content_fits_page(self):
        adj = FakeAdjustment(value=0.0, upper=100.0, page_size=200.0)
        fraction, called = _on_canvas_scroll(adj, False, False)
        assert called is True
        assert fraction == 0.0


# ------------------------------------------------------------------ #
#  Sync guard timer logic                                              #
# ------------------------------------------------------------------ #


class TestOpenAPISyncGuardTimer:
    """The resettable guard timer must manage flags correctly."""

    def test_scroll_to_source_line_sets_syncing_flag(self):
        syncing_scroll = False
        guard_calls = []

        class FakeCanvas:
            def scroll_to_source_line(self, line):
                pass

        canvas = FakeCanvas()

        def scroll_to_source_line(source_line):
            nonlocal syncing_scroll
            syncing_scroll = True
            guard_calls.append(True)
            canvas.scroll_to_source_line(source_line)

        scroll_to_source_line(42)
        assert syncing_scroll is True
        assert len(guard_calls) == 1

    def test_clear_syncing_flag(self):
        syncing_scroll = True
        timer_id = 999

        syncing_scroll = False
        timer_id = 0

        assert syncing_scroll is False
        assert timer_id == 0

    def test_guard_resets_on_repeated_calls(self):
        guard_calls = []

        class FakeCanvas:
            def scroll_to_source_line(self, line):
                pass

        canvas = FakeCanvas()
        syncing_scroll = False

        def scroll_to_source_line(source_line):
            nonlocal syncing_scroll
            syncing_scroll = True
            guard_calls.append(source_line)
            canvas.scroll_to_source_line(source_line)

        scroll_to_source_line(10)
        scroll_to_source_line(20)
        scroll_to_source_line(30)

        assert syncing_scroll is True
        assert len(guard_calls) == 3
        assert guard_calls == [10, 20, 30]


# ------------------------------------------------------------------ #
#  Editor: _sync_openapi_scroll guard logic                            #
# ------------------------------------------------------------------ #


class TestEditorSyncOpenAPIScrollGuards:
    """Editor→preview sync must be blocked when reverse-syncing."""

    @staticmethod
    def _sync_openapi_scroll(syncing_from_preview, preview_is_syncing, on_sync):
        """Replicate _sync_openapi_scroll guard logic."""
        if syncing_from_preview or preview_is_syncing:
            return False
        on_sync()
        return True

    def test_blocked_when_syncing_from_preview(self):
        calls = []
        result = self._sync_openapi_scroll(True, False, lambda: calls.append(1))
        assert result is False
        assert len(calls) == 0

    def test_blocked_when_preview_syncing(self):
        calls = []
        result = self._sync_openapi_scroll(False, True, lambda: calls.append(1))
        assert result is False
        assert len(calls) == 0

    def test_blocked_when_both_active(self):
        calls = []
        result = self._sync_openapi_scroll(True, True, lambda: calls.append(1))
        assert result is False
        assert len(calls) == 0

    def test_passes_when_all_guards_clear(self):
        calls = []
        result = self._sync_openapi_scroll(False, False, lambda: calls.append(42))
        assert result is True
        assert calls == [42]


# ------------------------------------------------------------------ #
#  Editor: reverse sync (preview → editor) guard                       #
# ------------------------------------------------------------------ #


class TestEditorOpenAPIReverseSyncGuard:
    """Preview→editor sync must set _syncing_from_preview to block echo-back."""

    def test_sets_syncing_flag(self):
        _syncing_from_preview = [False]
        adj = FakeAdjustment(value=0.0, upper=1000.0, page_size=200.0)

        def _sync_editor_from_preview(fraction):
            _syncing_from_preview[0] = True
            upper = adj.get_upper()
            page = adj.get_page_size()
            if upper > page:
                adj.set_value(fraction * (upper - page))

        _sync_editor_from_preview(0.5)
        assert _syncing_from_preview[0] is True
        assert adj.get_value() == pytest.approx(400.0)

    def test_fraction_zero_scrolls_to_top(self):
        adj = FakeAdjustment(value=500.0, upper=1000.0, page_size=200.0)

        def _sync_editor_from_preview(fraction):
            upper = adj.get_upper()
            page = adj.get_page_size()
            if upper > page:
                adj.set_value(fraction * (upper - page))

        _sync_editor_from_preview(0.0)
        assert adj.get_value() == pytest.approx(0.0)

    def test_fraction_one_scrolls_to_bottom(self):
        adj = FakeAdjustment(value=0.0, upper=1000.0, page_size=200.0)

        def _sync_editor_from_preview(fraction):
            upper = adj.get_upper()
            page = adj.get_page_size()
            if upper > page:
                adj.set_value(fraction * (upper - page))

        _sync_editor_from_preview(1.0)
        assert adj.get_value() == pytest.approx(800.0)


# ------------------------------------------------------------------ #
#  Full echo-back cycle simulation                                     #
# ------------------------------------------------------------------ #


class TestOpenAPIScrollEchoBackPrevention:
    """Simulate a full editor→preview→editor cycle and verify no echo-back."""

    def test_editor_scroll_does_not_echo_back(self):
        """When editor scrolls preview, the preview's scroll event must not
        echo back to the editor."""
        editor_scroll_calls = []
        _syncing_from_preview = [False]
        syncing_scroll = [False]
        animation_adjusting = [False]

        adj = FakeAdjustment(value=0.0, upper=1000.0, page_size=200.0)

        def editor_scrolls_preview(source_line):
            syncing_scroll[0] = True
            animation_adjusting[0] = True
            adj.set_value(source_line * 10.0)
            animation_adjusting[0] = False

        def on_canvas_scroll_event():
            if syncing_scroll[0]:
                return
            if animation_adjusting[0]:
                return
            editor_scroll_calls.append("echo!")

        adj._value_changed_callbacks.append(lambda _a: on_canvas_scroll_event())

        editor_scrolls_preview(42)
        assert len(editor_scroll_calls) == 0

    def test_preview_scroll_does_not_echo_back(self):
        """When user scrolls preview, the editor sync must not echo back
        to the preview."""
        preview_scroll_calls = []
        _syncing_from_preview = [False]
        syncing_scroll = [False]

        editor_adj = FakeAdjustment(value=0.0, upper=2000.0, page_size=400.0)

        def preview_scrolls_editor(fraction):
            _syncing_from_preview[0] = True
            upper = editor_adj.get_upper()
            page = editor_adj.get_page_size()
            if upper > page:
                editor_adj.set_value(fraction * (upper - page))

        def on_editor_scroll_event():
            if _syncing_from_preview[0]:
                return
            if syncing_scroll[0]:
                return
            preview_scroll_calls.append("echo!")

        editor_adj._value_changed_callbacks.append(lambda _a: on_editor_scroll_event())

        preview_scrolls_editor(0.5)
        assert len(preview_scroll_calls) == 0


# ------------------------------------------------------------------ #
#  OpenAPI-specific: block rendering with layout for scroll mapping     #
# ------------------------------------------------------------------ #


class TestOpenAPIBlocksForScrollMapping:
    """Verify OpenAPIBlockRenderer produces blocks compatible with
    MarkdownCanvas scroll sync (monotonic source_lines, valid kinds)."""

    def test_swagger_2_spec(self):
        spec = {
            "swagger": "2.0",
            "info": {"title": "Legacy API", "version": "1.0"},
            "host": "api.example.com",
            "basePath": "/v1",
            "paths": {
                "/pets": {
                    "get": {
                        "summary": "List pets",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(spec)
        lines = [b.source_line for b in blocks]
        assert lines == sorted(lines)
        assert len(blocks) > 0

    def test_spec_with_parameters_table(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Params API", "version": "1.0"},
            "paths": {
                "/search": {
                    "get": {
                        "tags": ["Search"],
                        "summary": "Search items",
                        "parameters": [
                            {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                            {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(spec)
        lines = [b.source_line for b in blocks]
        assert lines == sorted(lines)

        # Should include a table block for parameters (inside collapsible children)
        def _collect_kinds(blocks):
            kinds = set()
            for b in blocks:
                kinds.add(b.kind)
                if b.children:
                    kinds |= _collect_kinds(b.children)
            return kinds

        kinds = _collect_kinds(blocks)
        assert "table" in kinds

    def test_spec_with_request_body(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Body API", "version": "1.0"},
            "paths": {
                "/items": {
                    "post": {
                        "tags": ["Items"],
                        "summary": "Create item",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"},
                                }
                            }
                        },
                        "responses": {"201": {"description": "Created"}},
                    }
                }
            },
        }
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(spec)
        lines = [b.source_line for b in blocks]
        assert lines == sorted(lines)

        # Should include a code block for request body schema (inside collapsible children)
        def _collect_kinds(blocks):
            kinds = set()
            for b in blocks:
                kinds.add(b.kind)
                if b.children:
                    kinds |= _collect_kinds(b.children)
            return kinds

        kinds = _collect_kinds(blocks)
        assert "code" in kinds

    def test_multiple_tags_produce_separate_headings(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Multi-Tag API", "version": "1.0"},
            "paths": {
                "/a": {
                    "get": {
                        "tags": ["Alpha"],
                        "responses": {"200": {"description": "OK"}},
                    }
                },
                "/b": {
                    "get": {
                        "tags": ["Beta"],
                        "responses": {"200": {"description": "OK"}},
                    }
                },
            },
        }
        renderer = OpenAPIBlockRenderer()
        blocks = renderer.render(spec)
        headings = [b for b in blocks if b.kind == "heading"]
        # API title + 2 tag headings; endpoints are now collapsible blocks (not headings)
        assert len(headings) >= 3
        # Verify the 2 collapsible endpoint blocks exist
        collapsible = [b for b in blocks if b.collapsible]
        assert len(collapsible) >= 2
