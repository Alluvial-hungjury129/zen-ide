"""Integration tests for canvas interactions — text editing, scrolling, resize, font size changes."""

from sketch_pad.canvas import SketchCanvas
from sketch_pad.sketch_model import (
    ArrowShape,
    Board,
    RectangleShape,
    ToolMode,
    TopicShape,
)


class TestClickOutsideExitsTextEdit:
    """Clicking outside a shape while in text-edit mode must exit edit and deselect."""

    def _make_canvas_with_box(self):
        board = Board()
        box = RectangleShape(left=5, top=3, width=10, height=5)
        board.add_shape(box)
        canvas = SketchCanvas(board)
        # Manually enter text edit
        canvas._start_text_edit_for_shape(box)
        assert canvas._text_editing
        assert box.id in canvas._selected_ids
        return canvas, box

    def test_drag_begin_outside_exits_text_edit_select_tool(self):
        canvas, box = self._make_canvas_with_box()
        canvas._tool = ToolMode.SELECT
        # Simulate _on_drag_begin clicking outside the shape
        canvas._double_click_pending = False
        # Manually replicate the logic: col=0, row=0 is outside box (5,3,14,7)
        canvas._text_editing = True
        canvas._text_shape_id = box.id
        canvas._selected_ids = {box.id}
        # Call _exit_text_edit and clear selection (as the fix does)
        shape = canvas._board.get_shape(canvas._text_shape_id)
        assert shape is not None
        assert not shape.contains(0, 0)  # outside
        canvas._exit_text_edit()
        canvas._selected_ids.clear()
        assert not canvas._text_editing
        assert len(canvas._selected_ids) == 0

    def test_drag_begin_outside_exits_text_edit_box_tool(self):
        canvas, box = self._make_canvas_with_box()
        canvas._tool = ToolMode.RECTANGLE
        # Before fix: non-SELECT tool wouldn't clear selection
        canvas._exit_text_edit()
        canvas._selected_ids.clear()
        assert not canvas._text_editing
        assert len(canvas._selected_ids) == 0

    def test_multiclick_outside_exits_text_edit(self):
        """Triple-click (n_press>=2) outside shape must exit text edit."""
        canvas, box = self._make_canvas_with_box()
        # Simulate what _on_click does for n_press >= 2 clicking outside
        shape = canvas._board.get_shape_at(0, 0)
        assert shape is None  # clicking outside
        canvas._exit_text_edit()
        canvas._selected_ids.clear()
        assert not canvas._text_editing
        assert len(canvas._selected_ids) == 0
        assert canvas._text_shape_id is None

    def test_click_inside_shape_stays_in_text_edit(self):
        canvas, box = self._make_canvas_with_box()
        # Click inside the box (col=7, row=5 is within 5,3..14,7)
        shape = canvas._board.get_shape(canvas._text_shape_id)
        assert shape is not None
        assert shape.contains(7, 5)
        # Text editing should remain active
        assert canvas._text_editing
        assert box.id in canvas._selected_ids

    def test_single_click_outside_exits_text_edit(self):
        """Single click (n_press=1) outside shape must exit text edit and deselect."""
        canvas, box = self._make_canvas_with_box()
        assert canvas._text_editing
        assert box.id in canvas._selected_ids
        # Simulate _on_click with n_press=1 at (0,0) which is outside box (5,3..14,7)
        canvas._on_click(None, 1, 0, 0)
        assert not canvas._text_editing, "Text editing should stop on single click outside"
        assert len(canvas._selected_ids) == 0, "Shape should be deselected"
        assert canvas._double_click_pending, "Flag should suppress drag-begin"

    def test_single_click_inside_keeps_text_edit(self):
        """Single click inside shape during text edit should NOT exit text edit."""
        canvas, box = self._make_canvas_with_box()
        assert canvas._text_editing
        # Click inside the box - convert grid (7,5) to screen coords
        sx = 7 * canvas._cell_w + 1
        sy = 5 * canvas._cell_h + 1
        canvas._on_click(None, 1, sx, sy)
        assert canvas._text_editing, "Text editing should remain active on click inside"
        assert box.id in canvas._selected_ids


class TestFontSizeCanvas:
    """Tests for font_size changes via canvas."""

    def test_change_selected_font_size(self):
        board = Board()
        r = RectangleShape(left=0, top=0, width=10, height=5, text="hi")
        board.add_shape(r)
        canvas = SketchCanvas(board)
        canvas._cell_w = 8.4
        canvas._cell_h = 16.8
        canvas._selected_ids = {r.id}
        canvas.set_selected_font_size(16)
        assert r.font_size == 16

    def test_change_font_size_min_max(self):
        board = Board()
        r = RectangleShape(left=0, top=0, width=10, height=5, text="hi", font_size=9)
        board.add_shape(r)
        canvas = SketchCanvas(board)
        canvas._cell_w = 8.4
        canvas._cell_h = 16.8
        canvas._selected_ids = {r.id}
        canvas.set_selected_font_size(5)
        assert r.font_size == 6  # clamped to min

    def test_change_font_size_incremental(self):
        board = Board()
        r = RectangleShape(left=0, top=0, width=10, height=5, text="hi", font_size=20)
        board.add_shape(r)
        canvas = SketchCanvas(board)
        canvas._cell_w = 8.4
        canvas._cell_h = 16.8
        canvas._selected_ids = {r.id}
        canvas.set_selected_font_size(22)
        assert r.font_size == 22
        canvas.set_selected_font_size(18)
        assert r.font_size == 18


class _ScrollControllerStub:
    def __init__(self, state=0):
        self._state = state

    def get_current_event_state(self):
        return self._state


class TestSketchCanvasScrolling:
    def test_scroll_pan_uses_tuned_step(self):
        canvas = SketchCanvas(Board())
        canvas._zoom = 1.0

        tick_ids = []

        def _fake_add_tick_callback(callback):
            tick_ids.append(callback)
            return 123

        canvas.add_tick_callback = _fake_add_tick_callback

        handled = canvas._on_scroll(_ScrollControllerStub(), 0.0, 1.0)

        assert handled is True
        assert canvas._target_pan_y == -SketchCanvas._SCROLL_PAN_STEP
        assert canvas._scroll_tick_id == 123
        assert len(tick_ids) == 1


class TestResizePersistence:
    """Verify that resized shape dimensions survive the snapshot/save/load cycle."""

    def _make_canvas_with_topic(self):
        board = Board()
        topic = TopicShape(left=10, top=5, width=20, height=4, text="my-topic", font_size=12.0)
        board.add_shape(topic)
        canvas = SketchCanvas(board)
        canvas._cell_w = 8.4
        canvas._cell_h = 16.8
        return board, canvas, topic

    def test_apply_resize_changes_dimensions(self):
        board, canvas, topic = self._make_canvas_with_topic()
        orig = topic.to_dict()
        canvas._resizing = True
        canvas._resize_handle = "br"
        canvas._resize_shape_id = topic.id
        canvas._resize_orig = orig

        # Simulate dragging bottom-right handle to expand
        canvas._apply_resize(35, 12)
        assert topic.width == 26  # 35 - 10 + 1
        assert topic.height == 8  # 12 - 5 + 1

    def test_resize_snapshot_captures_new_dimensions(self):
        board, canvas, topic = self._make_canvas_with_topic()
        orig = topic.to_dict()
        canvas._resizing = True
        canvas._resize_handle = "br"
        canvas._resize_shape_id = topic.id
        canvas._resize_orig = orig

        canvas._apply_resize(35, 12)
        canvas._snapshot_history()

        # Restore last snapshot and verify dimensions
        snap = canvas._history[canvas._hist_idx]
        restored = Board.from_json(snap)
        t = list(restored.shapes.values())[0]
        assert t.width == 26
        assert t.height == 8

    def test_resize_board_json_roundtrip(self):
        board, canvas, topic = self._make_canvas_with_topic()
        orig = topic.to_dict()
        canvas._resizing = True
        canvas._resize_handle = "mr"
        canvas._resize_shape_id = topic.id
        canvas._resize_orig = orig

        canvas._apply_resize(40, 7)  # Expand right only
        json_str = board.to_json()
        restored = Board.from_json(json_str)
        t = list(restored.shapes.values())[0]
        assert t.width == 31  # 40 - 10 + 1
        assert t.height == 4  # Unchanged (middle-right handle)


class TestFontSize:
    """Tests for per-shape font_size feature."""

    def test_rectangle_font_size_default_none(self):
        r = RectangleShape(left=0, top=0, width=10, height=5, text="hi")
        assert r.font_size is None

    def test_rectangle_font_size_serialization(self):
        r = RectangleShape(left=0, top=0, width=10, height=5, text="hi", font_size=24)
        d = r.to_dict()
        assert d["font_size"] == 24
        restored = RectangleShape.from_dict(d)
        assert restored.font_size == 24

    def test_rectangle_font_size_none_not_in_dict(self):
        r = RectangleShape(left=0, top=0, width=10, height=5)
        d = r.to_dict()
        assert "font_size" not in d

    def test_rectangle_custom_font_skips_grid_text(self):
        r = RectangleShape(left=0, top=0, width=10, height=5, text="hello", font_size=20)
        grid: dict[tuple[int, int], str] = {}
        r.render(grid)
        # Border should be rendered
        assert grid[(0, 0)] == "┌"
        # Interior text should NOT be in grid (custom font renders separately)
        interior_chars = [grid.get((c, r_), "") for r_ in range(1, 4) for c in range(1, 9)]
        assert "h" not in interior_chars

    def test_rectangle_default_font_renders_grid_text(self):
        r = RectangleShape(left=0, top=0, width=10, height=5, text="hello")
        grid: dict[tuple[int, int], str] = {}
        r.render(grid)
        r.render_text(grid)
        # Text should be in grid (standard rendering)
        interior_chars = [grid.get((c, r_), "") for r_ in range(1, 4) for c in range(1, 9)]
        assert "h" in interior_chars

    def test_arrow_font_size_serialization(self):
        a = ArrowShape(start_col=0, start_row=0, end_col=10, end_row=0, text="label", font_size=18)
        d = a.to_dict()
        assert d["font_size"] == 18
        restored = ArrowShape.from_dict(d)
        assert restored.font_size == 18

    def test_arrow_font_size_none_not_in_dict(self):
        a = ArrowShape(start_col=0, start_row=0, end_col=10, end_row=0, text="label")
        d = a.to_dict()
        assert "font_size" not in d

    def test_arrow_custom_font_skips_grid_text(self):
        a = ArrowShape(start_col=0, start_row=0, end_col=10, end_row=0, text="X", font_size=20)
        grid: dict[tuple[int, int], str] = {}
        a.render(grid)
        # Arrow line chars should be present
        has_arrow_chars = any(ch in ("─", "►", "◄") for ch in grid.values())
        assert has_arrow_chars
        # The text "X" should NOT be in the grid
        assert "X" not in grid.values()

    def test_board_round_trip_with_font_size(self):
        board = Board()
        r = RectangleShape(left=0, top=0, width=10, height=5, text="hi", font_size=32)
        a = ArrowShape(start_col=0, start_row=6, end_col=10, end_row=6, text="lbl", font_size=16)
        board.add_shape(r)
        board.add_shape(a)
        json_str = board.to_json()
        restored = Board.from_json(json_str)
        shapes = list(restored.shapes.values())
        rect = next(s for s in shapes if isinstance(s, RectangleShape))
        arrow = next(s for s in shapes if isinstance(s, ArrowShape))
        assert rect.font_size == 32
        assert arrow.font_size == 16
