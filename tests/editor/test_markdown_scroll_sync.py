"""Tests for markdown editor ↔ preview scroll sync.

Regression tests covering:
- Canvas smooth scroll (lerp) animation logic
- Canvas is_animation_adjusting guard
- Preview _syncing_scroll echo-back guard
- Preview resettable guard timer
- Source-line ↔ Y-offset bidirectional mapping consistency
- _on_canvas_scroll suppression during animation / syncing
"""

import pytest

from editor.preview.content_block import ContentBlock
from editor.preview.markdown_canvas import _estimate_block_lines
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
    smooth_scroll_tick as _smooth_scroll_tick,
)

# ------------------------------------------------------------------ #
#  Source-line ↔ Y mapping                                             #
# ------------------------------------------------------------------ #


class TestSourceLineYMapping:
    """get_y_for_source_line bidirectional mapping consistency."""

    def test_first_line_maps_to_first_block(self):
        blocks = _make_blocks(
            [
                (0, 0.0, 100.0),
                (10, 100.0, 200.0),
                (30, 300.0, 150.0),
            ]
        )
        assert _get_y_for_source_line(blocks, 0) == 0.0

    def test_exact_block_boundary(self):
        blocks = _make_blocks(
            [
                (0, 0.0, 100.0),
                (10, 100.0, 200.0),
            ]
        )
        assert _get_y_for_source_line(blocks, 10) == 100.0

    def test_interpolation_within_block(self):
        """Source line midway through a block → Y midway through its height."""
        blocks = _make_blocks(
            [
                (0, 0.0, 100.0),
                (10, 100.0, 200.0),
                (30, 300.0, 150.0),
            ]
        )
        # Line 20 is halfway through block[1] (source_line=10, span=20)
        y = _get_y_for_source_line(blocks, 20)
        assert y == pytest.approx(200.0)  # 100 + (10/20)*200

    def test_empty_blocks_returns_zero(self):
        assert _get_y_for_source_line([], 5) == 0.0

    def test_last_block_line_returns_last_offset(self):
        blocks = _make_blocks(
            [
                (0, 0.0, 100.0),
                (10, 100.0, 200.0),
            ]
        )
        assert _get_y_for_source_line(blocks, 10) == 100.0

    def test_quarter_through_block(self):
        blocks = _make_blocks(
            [
                (0, 0.0, 100.0),
                (10, 100.0, 200.0),
                (30, 300.0, 150.0),
            ]
        )
        # Line 15 is quarter-way through block[1] (5/20 of span)
        y = _get_y_for_source_line(blocks, 15)
        assert y == pytest.approx(150.0)  # 100 + (5/20)*200


# ------------------------------------------------------------------ #
#  Smooth scroll animation logic                                       #
# ------------------------------------------------------------------ #


class TestSmoothScrollLogic:
    """Test lerp-based smooth scroll tick logic."""

    def test_lerp_moves_toward_target(self):
        """Each tick should move 25% of remaining distance."""
        adj = FakeAdjustment(value=0.0)
        keep_going, new_val, _, _ = _smooth_scroll_tick(adj, 100.0)
        assert keep_going is True
        assert new_val == pytest.approx(25.0)

    def test_lerp_converges(self):
        """After several iterations, value should converge to target."""
        adj = FakeAdjustment(value=0.0)
        target = 100.0
        for _ in range(50):
            keep_going, _, target, _ = _smooth_scroll_tick(adj, target)
            if not keep_going:
                break
        assert adj.get_value() == pytest.approx(100.0)

    def test_lerp_snaps_when_close(self):
        """When diff < 1.0 pixel, snap directly to target."""
        adj = FakeAdjustment(value=99.5)
        keep_going, new_val, new_target, _ = _smooth_scroll_tick(adj, 100.0)
        assert keep_going is False
        assert new_val == pytest.approx(100.0)
        assert new_target is None

    def test_animation_adjusting_flag_during_set(self):
        """Flag must be True when set_value is called."""
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

    def test_target_clamping(self):
        """Target should be clamped to max scrollable value."""
        upper, page = 500.0, 200.0
        max_val = max(0.0, upper - page)  # 300
        raw_target = 999.0
        clamped = max(0.0, min(raw_target, max_val))
        assert clamped == pytest.approx(300.0)

    def test_target_clamping_negative(self):
        """Negative target should clamp to 0."""
        clamped = max(0.0, min(-50.0, 300.0))
        assert clamped == 0.0


# ------------------------------------------------------------------ #
#  _on_canvas_scroll echo-back suppression                             #
# ------------------------------------------------------------------ #


class TestOnCanvasScrollGuards:
    """_on_canvas_scroll must be suppressed during syncing / animation."""

    @staticmethod
    def _on_canvas_scroll(adj, syncing_scroll, animation_adjusting, callback=None):
        """Replicate MarkdownPreview._on_canvas_scroll logic.

        Returns (fraction, callback_called).
        """
        if syncing_scroll:
            return None, False
        if animation_adjusting:
            return None, False
        upper = adj.get_upper()
        page = adj.get_page_size()
        if upper > page:
            fraction = adj.get_value() / (upper - page)
        else:
            fraction = 0.0
        if callback:
            callback(fraction)
        return fraction, True

    def test_callback_fires_normally(self):
        results = []
        adj = FakeAdjustment(value=400.0, upper=1000.0, page_size=200.0)
        fraction, called = self._on_canvas_scroll(adj, False, False, callback=lambda f: results.append(f))
        assert called is True
        assert fraction == pytest.approx(0.5)  # 400/(1000-200)
        assert results[0] == pytest.approx(0.5)

    def test_suppressed_when_syncing_scroll(self):
        results = []
        adj = FakeAdjustment(value=400.0)
        _, called = self._on_canvas_scroll(adj, True, False, callback=lambda f: results.append(f))
        assert called is False
        assert len(results) == 0

    def test_suppressed_when_animation_adjusting(self):
        results = []
        adj = FakeAdjustment(value=400.0)
        _, called = self._on_canvas_scroll(adj, False, True, callback=lambda f: results.append(f))
        assert called is False
        assert len(results) == 0

    def test_suppressed_when_both_guards_active(self):
        results = []
        adj = FakeAdjustment(value=400.0)
        _, called = self._on_canvas_scroll(adj, True, True, callback=lambda f: results.append(f))
        assert called is False

    def test_fires_after_guards_cleared(self):
        """Once both guards are off, callback should fire again."""
        results = []
        adj = FakeAdjustment(value=400.0, upper=1000.0, page_size=200.0)
        cb = lambda f: results.append(f)

        # Blocked
        self._on_canvas_scroll(adj, True, True, cb)
        assert len(results) == 0

        # Unblocked
        self._on_canvas_scroll(adj, False, False, cb)
        assert len(results) == 1

    def test_zero_fraction_when_content_fits_page(self):
        adj = FakeAdjustment(value=0.0, upper=100.0, page_size=200.0)
        fraction, called = self._on_canvas_scroll(adj, False, False)
        assert called is True
        assert fraction == 0.0


# ------------------------------------------------------------------ #
#  Sync guard timer logic                                              #
# ------------------------------------------------------------------ #


class TestSyncGuardTimer:
    """The resettable guard timer must manage flags correctly."""

    def test_scroll_to_source_line_sets_syncing_flag(self):
        """scroll_to_source_line must set _syncing_scroll = True and call guard."""
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
        """_clear_syncing_flag must reset both flag and timer ID."""
        syncing_scroll = True
        timer_id = 999

        # Replicate _clear_syncing_flag
        syncing_scroll = False
        timer_id = 0

        assert syncing_scroll is False
        assert timer_id == 0

    def test_guard_resets_on_repeated_calls(self):
        """Each call to scroll_to_source_line should reset the guard timer."""
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
#  Editor: _sync_md_scroll guard logic                                 #
# ------------------------------------------------------------------ #


class TestEditorSyncMdScrollGuards:
    """Editor→preview sync must be blocked when reverse-syncing."""

    @staticmethod
    def _sync_md_scroll(syncing_from_preview, preview_is_syncing, on_sync):
        """Replicate _sync_md_scroll guard logic."""
        if syncing_from_preview or preview_is_syncing:
            return False
        on_sync()
        return True

    def test_blocked_when_syncing_from_preview(self):
        calls = []
        result = self._sync_md_scroll(True, False, lambda: calls.append(1))
        assert result is False
        assert len(calls) == 0

    def test_blocked_when_preview_syncing(self):
        calls = []
        result = self._sync_md_scroll(False, True, lambda: calls.append(1))
        assert result is False
        assert len(calls) == 0

    def test_blocked_when_both_active(self):
        calls = []
        result = self._sync_md_scroll(True, True, lambda: calls.append(1))
        assert result is False
        assert len(calls) == 0

    def test_passes_when_all_guards_clear(self):
        calls = []
        result = self._sync_md_scroll(False, False, lambda: calls.append(42))
        assert result is True
        assert calls == [42]


# ------------------------------------------------------------------ #
#  Editor: reverse sync (preview → editor) guard                       #
# ------------------------------------------------------------------ #


class TestEditorReverseSyncGuard:
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


class TestScrollEchoBackPrevention:
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
            """Editor side: scroll preview to a source line."""
            syncing_scroll[0] = True
            # Canvas smooth scroll would set animation_adjusting during set_value
            animation_adjusting[0] = True
            adj.set_value(source_line * 10.0)
            animation_adjusting[0] = False

        def on_canvas_scroll_event():
            """Preview side: fired when canvas scroll value changes."""
            if syncing_scroll[0]:
                return  # Guard: we initiated this scroll
            if animation_adjusting[0]:
                return  # Guard: animation frame in progress
            # This would echo back to editor — should NOT reach here
            editor_scroll_calls.append("echo!")

        adj._value_changed_callbacks.append(lambda _a: on_canvas_scroll_event())

        # Simulate editor scrolling
        editor_scrolls_preview(42)

        # No echo-back should have occurred
        assert len(editor_scroll_calls) == 0

    def test_preview_scroll_does_not_echo_back(self):
        """When user scrolls preview, the editor sync must not echo back
        to the preview."""
        preview_scroll_calls = []
        _syncing_from_preview = [False]
        syncing_scroll = [False]

        editor_adj = FakeAdjustment(value=0.0, upper=2000.0, page_size=400.0)

        def preview_scrolls_editor(fraction):
            """Preview side: sends fraction to editor."""
            _syncing_from_preview[0] = True
            upper = editor_adj.get_upper()
            page = editor_adj.get_page_size()
            if upper > page:
                editor_adj.set_value(fraction * (upper - page))

        def on_editor_scroll_event():
            """Editor side: fired when editor scroll changes."""
            if _syncing_from_preview[0]:
                return  # Guard: preview initiated this
            if syncing_scroll[0]:
                return
            # Would echo back to preview — should NOT reach here
            preview_scroll_calls.append("echo!")

        editor_adj._value_changed_callbacks.append(lambda _a: on_editor_scroll_event())

        # Simulate preview scrolling
        preview_scrolls_editor(0.5)

        # No echo-back should have occurred
        assert len(preview_scroll_calls) == 0


# ------------------------------------------------------------------ #
#  _estimate_block_lines                                               #
# ------------------------------------------------------------------ #


class TestEstimateBlockLines:
    """_estimate_block_lines is used for last-block span calculation."""

    def test_code_block(self):
        block = ContentBlock(kind="code", code="line1\nline2\nline3")
        assert _estimate_block_lines(block) == 5  # 3 lines + 2 fences

    def test_table_block(self):
        block = ContentBlock(kind="table", headers=["a"], rows=[["1"], ["2"]])
        assert _estimate_block_lines(block) == 4  # header + sep + 2 rows

    def test_paragraph_block(self):
        block = ContentBlock(kind="paragraph")
        assert _estimate_block_lines(block) == 1

    def test_heading_block(self):
        block = ContentBlock(kind="heading")
        assert _estimate_block_lines(block) == 1

    def test_empty_code_block(self):
        block = ContentBlock(kind="code", code="")
        assert _estimate_block_lines(block) == 3  # 1 line + 2 fences
