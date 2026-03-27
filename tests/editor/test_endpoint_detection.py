"""Tests for OpenAPI endpoint detection and block rendering.

Covers:
- OpenAPIBlockRenderer source_line assignment consistency
- Source-line to Y-offset bidirectional mapping
- Smooth scroll animation logic (lerp)
- _on_canvas_scroll suppression during animation / syncing
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
#  Source-line to Y mapping (same logic as markdown, shared canvas)     #
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
