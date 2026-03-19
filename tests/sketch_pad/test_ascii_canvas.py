"""Tests for Board rendering — character grid output for shapes."""

from sketch_pad.sketch_model import (
    ArrowShape,
    Board,
    RectangleShape,
)


class TestBoardRendering:
    """Verify Board.render() produces correct character grids."""

    def test_rectangle_sharp_border(self):
        board = Board()
        board.add_shape(RectangleShape(left=0, top=0, width=5, height=3))
        grid = board.render()
        assert grid.get((0, 0)) == "┌"
        assert grid.get((4, 0)) == "┐"
        assert grid.get((0, 2)) == "└"
        assert grid.get((4, 2)) == "┘"
        assert grid.get((2, 0)) == "─"
        assert grid.get((0, 1)) == "│"

    def test_rectangle_interior_filled_with_spaces(self):
        board = Board()
        board.add_shape(RectangleShape(left=0, top=0, width=5, height=3))
        grid = board.render()
        # Interior should be space (masks shapes behind)
        assert grid.get((2, 1)) == " "

    def test_empty_board(self):
        board = Board()
        grid = board.render()
        assert len(grid) == 0

    def test_rectangle_with_text(self):
        board = Board()
        board.add_shape(RectangleShape(left=0, top=0, width=10, height=5, text="Hi"))
        grid = board.render()
        found = any(grid.get((c, r)) == "H" for r in range(5) for c in range(10))
        assert found

    def test_overlapping_shapes_z_order(self):
        board = Board()
        r1 = RectangleShape(left=0, top=0, width=5, height=3)
        r2 = RectangleShape(left=2, top=0, width=5, height=3)
        board.add_shape(r1)
        board.add_shape(r2)
        grid = board.render()
        assert grid.get((2, 0)) == "┌"

    def test_hit_test_on_border(self):
        board = Board()
        r = RectangleShape(left=2, top=1, width=10, height=5)
        board.add_shape(r)
        assert r.contains(5, 1) is True

    def test_hit_test_empty_space(self):
        board = Board()
        r = RectangleShape(left=2, top=1, width=10, height=5)
        board.add_shape(r)
        assert r.contains(0, 0) is False

    def test_arrow_rendering(self):
        board = Board()
        board.add_shape(ArrowShape(start_col=0, start_row=0, end_col=5, end_row=0))
        grid = board.render()
        assert grid.get((0, 0)) == "─"
        assert grid.get((5, 0)) == "►"
