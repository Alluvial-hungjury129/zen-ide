"""Tests for individual shape types (Rectangle, Arrow, Cloud)."""

from sketch_pad.sketch_model import (
    ArrowShape,
    Board,
    CloudShape,
    Connection,
    RectangleShape,
)


class TestRectangleShape:
    def test_bounds(self):
        s = RectangleShape(left=5, top=3, width=10, height=5)
        assert s.bound == (5, 3, 14, 7)

    def test_contains_point(self):
        s = RectangleShape(left=5, top=3, width=10, height=5)
        assert s.contains(7, 4)
        assert not s.contains(0, 0)

    def test_move(self):
        s = RectangleShape(left=5, top=3, width=10, height=5)
        s.move(3, 2)
        assert s.bound == (8, 5, 17, 9)

    def test_render_box_chars(self):
        s = RectangleShape(left=0, top=0, width=4, height=3)
        grid = {}
        s.render(grid)
        assert grid[(0, 0)] == "┌"
        assert grid[(3, 0)] == "┐"
        assert grid[(0, 2)] == "└"
        assert grid[(3, 2)] == "┘"
        assert grid[(1, 0)] == "─"
        assert grid[(0, 1)] == "│"

    def test_render_with_text(self):
        s = RectangleShape(left=0, top=0, width=10, height=5, text="Hello")
        grid = {}
        s.render(grid)
        s.render_text(grid)
        found = any(grid.get((c, r)) == "H" for r in range(5) for c in range(10))
        assert found

    def test_interior_bounds(self):
        s = RectangleShape(left=5, top=3, width=10, height=5)
        assert s.get_interior_bounds() == (6, 4, 13, 6)

    def test_interior_bounds_too_small(self):
        s = RectangleShape(left=0, top=0, width=2, height=2)
        assert s.get_interior_bounds() is None

    def test_text_preserved_through_move(self):
        s = RectangleShape(left=5, top=2, width=12, height=5, text="Test")
        s.move(10, 5)
        grid = {}
        s.render(grid)
        s.render_text(grid)
        found = any(grid.get((c, r)) == "T" for r in range(20) for c in range(40))
        assert found

    def test_nearest_edge_point(self):
        s = RectangleShape(left=5, top=5, width=10, height=6)
        # Point above → top edge (snaps one cell outside the border)
        edge, ec, er, ratio = s.nearest_edge_point(10, 3)
        assert edge == "top"
        assert er == 4  # one cell above top=5
        # Point to the left → left edge (snaps one cell outside the border)
        edge, ec, er, ratio = s.nearest_edge_point(3, 8)
        assert edge == "left"
        assert ec == 4  # one cell left of left=5

    def test_edge_point_from_connection(self):
        s = RectangleShape(left=10, top=10, width=11, height=6)
        # Connects one cell outside the border, avoiding corners
        assert s.edge_point_from_connection("top", 0.5) == (15, 9)
        assert s.edge_point_from_connection("right", 0.0) == (21, 11)

    def test_interior_fill_masks_lower_z(self):
        """Rectangle interior fills with spaces to mask shapes behind."""
        b = Board()
        s1 = RectangleShape(left=0, top=0, width=8, height=6, text="A")
        s2 = RectangleShape(left=1, top=1, width=6, height=4)  # overlaps interior of s1
        b.add_shape(s1)
        b.add_shape(s2)
        grid = b.render()
        # Text renders in phase 3 (on top of everything), so s1's "A" at (3,2)
        # is visible even though s2's interior fill covers that cell.
        assert grid.get((3, 2)) == "A"


class TestArrowShape:
    def test_horizontal(self):
        s = ArrowShape(start_col=0, start_row=0, end_col=5, end_row=0)
        grid = {}
        s.render(grid)
        assert grid[(0, 0)] == "─"
        assert grid[(3, 0)] == "─"
        assert grid[(5, 0)] == "►"

    def test_vertical(self):
        s = ArrowShape(start_col=0, start_row=0, end_col=0, end_row=5)
        grid = {}
        s.render(grid)
        assert grid[(0, 0)] == "│"
        assert grid[(0, 3)] == "│"
        assert grid[(0, 5)] == "▼"

    def test_l_shaped(self):
        s = ArrowShape(start_col=0, start_row=0, end_col=5, end_row=3)
        grid = {}
        s.render(grid)
        assert grid[(5, 0)] == "┐"  # unicode corner

    def test_arrow_head_direction(self):
        # Arrow going left
        s = ArrowShape(start_col=5, start_row=0, end_col=0, end_row=0)
        grid = {}
        s.render(grid)
        assert grid[(0, 0)] == "◄"

        # Arrow going up
        s = ArrowShape(start_col=0, start_row=5, end_col=0, end_row=0)
        grid = {}
        s.render(grid)
        assert grid[(0, 0)] == "▲"

    def test_move(self):
        s = ArrowShape(start_col=0, start_row=0, end_col=5, end_row=5)
        s.move(2, 1)
        assert s.start_col == 2 and s.start_row == 1
        assert s.end_col == 7 and s.end_row == 6

    def test_bounds(self):
        s = ArrowShape(start_col=5, start_row=1, end_col=2, end_row=8)
        assert s.bound == (2, 1, 5, 8)

    def test_contains_on_path(self):
        s = ArrowShape(start_col=0, start_row=0, end_col=5, end_row=0)
        assert s.contains(3, 0)
        assert not s.contains(3, 5)

    def test_connection_update(self):
        b = Board()
        box = RectangleShape(left=10, top=10, width=10, height=6)
        b.add_shape(box)
        arrow = ArrowShape(
            start_col=0,
            start_row=12,
            end_col=10,
            end_row=12,
            end_connection=Connection(box.id, "left", 0.4),
        )
        b.add_shape(arrow)
        # Move the box right by 5
        box.move(5, 0)
        b.update_connections()
        # Re-optimised: left edge still best (start is directly left of box)
        assert arrow.end_connection.edge == "left"
        # One cell outside the left edge: box.left=15, so arrow.end_col=14
        assert arrow.end_col == 14

    def test_single_connected_arrow_preserves_edge_on_box_move(self):
        """Arrow with one end connected should stay on same edge when box moves."""
        b = Board()
        box = RectangleShape(left=0, top=0, width=20, height=5)
        b.add_shape(box)
        # Arrow connected to right edge of box, free end to the right
        arrow = ArrowShape(
            start_col=30,
            start_row=2,
            end_col=21,
            end_row=2,
            end_connection=Connection(box.id, "right", 0.5),
        )
        b.add_shape(arrow)
        # Move box up repeatedly — arrow should stay on right edge
        for _ in range(10):
            box.move(0, -1)
            b.update_connections()
            assert arrow.end_connection.edge == "right", (
                f"Arrow edge flipped to {arrow.end_connection.edge!r} after moving box up"
            )
            assert arrow.end_col == box.right + 1

    def test_arrow_auto_adjusts_when_connected_box_moves_vertically(self):
        """Arrow should re-route when a connected box is moved up/down."""
        b = Board()
        box_a = RectangleShape(id="a", left=0, top=6, width=26, height=12)
        box_b = RectangleShape(id="b", left=31, top=5, width=23, height=6)
        b.add_shape(box_a)
        b.add_shape(box_b)
        arrow = ArrowShape(
            id="arr",
            start_col=27,
            start_row=8,
            end_col=30,
            end_row=8,
            start_connection=Connection("a", "right", 0.2),
            end_connection=Connection("b", "left", 0.6),
        )
        b.add_shape(arrow)
        # Move box_b up by 5 rows
        box_b.move(0, -5)
        b.update_connections()
        # Arrow should still be connected to both boxes
        assert arrow.start_connection is not None
        assert arrow.end_connection is not None
        # Arrow start should be one cell outside box_a right edge
        assert arrow.start_col == box_a.right + 1
        # Arrow end should be one cell outside box_b left edge
        assert arrow.end_col == box_b.left - 1

    def test_no_collinear_mismatch_vertical_right(self):
        """Arrow must not become a vertical line with a sideways arrowhead.

        Regression: moving the top box so that start_col == end_col with
        end_connection on 'right' edge produced a vertical path with '◄'
        arrowhead instead of a proper L-shaped path.
        """
        box_bottom = RectangleShape(id="b", left=0, top=7, width=9, height=6, text="d")
        # At left=9, the naive diagonal candidate would produce
        # start=(9,6), end=(9,7) → straight vertical line with '◄'.
        for left in [9, 8, 7, 6]:
            box_top = RectangleShape(id="a", left=left, top=0, width=9, height=6)
            board = Board()
            board.add_shape(box_bottom.copy())
            board.add_shape(box_top)
            arrow = ArrowShape(
                id="arr",
                start_col=0,
                start_row=0,
                end_col=0,
                end_row=0,
                start_connection=Connection("a", "bottom", 0.5),
                end_connection=Connection("b", "right", 0.5),
            )
            board.add_shape(arrow)
            board.update_connections()
            path = arrow._compute_path()
            sc, sr = path[0]
            ec, er = path[-1]
            edge = arrow.end_connection.edge
            # The arrowhead direction must match the last segment direction.
            if edge in ("left", "right"):
                assert sc != ec, f"left={left}: vertical path with horizontal arrowhead (edge={edge})"
            if edge in ("top", "bottom"):
                assert sr != er, f"left={left}: horizontal path with vertical arrowhead (edge={edge})"

    def test_no_collinear_mismatch_horizontal_bottom(self):
        """Arrow must not become a horizontal line with a vertical arrowhead."""
        box_left = RectangleShape(id="l", left=0, top=0, width=9, height=6)
        box_right = RectangleShape(id="r", left=10, top=6, width=9, height=6)
        board = Board()
        board.add_shape(box_left)
        board.add_shape(box_right)
        arrow = ArrowShape(
            id="arr",
            start_col=0,
            start_row=0,
            end_col=0,
            end_row=0,
            start_connection=Connection("l", "right", 0.5),
            end_connection=Connection("r", "top", 0.5),
        )
        board.add_shape(arrow)
        board.update_connections()
        path = arrow._compute_path()
        sc, sr = path[0]
        ec, er = path[-1]
        edge = arrow.end_connection.edge
        if edge in ("top", "bottom"):
            assert sr != er, "horizontal path with vertical arrowhead"
        if edge in ("left", "right"):
            assert sc != ec, "vertical path with horizontal arrowhead"

    def test_arrow_corner_preserved_across_move(self):
        """Moving a connected box must not collapse a corner into a straight line.

        Regression: arrow from top-box bottom to bottom-box right had a proper
        L-shape at left=10 (with ┘ corner). Moving to left=9 collapsed the
        corner, producing a straight vertical line with mismatched arrowhead.
        """
        box_b = RectangleShape(id="b", left=0, top=7, width=9, height=6, text="d")
        # At left=10 the arrow is a proper L-shape
        box_a = RectangleShape(id="a", left=10, top=0, width=9, height=6)
        board = Board()
        board.add_shape(box_b.copy())
        board.add_shape(box_a)
        arrow = ArrowShape(
            id="arr",
            start_col=0,
            start_row=0,
            end_col=0,
            end_row=0,
            start_connection=Connection("a", "bottom", 0.5),
            end_connection=Connection("b", "right", 0.5),
        )
        board.add_shape(arrow)
        board.update_connections()
        path_before = arrow._compute_path()
        assert len(path_before) >= 3, "Expected L-shaped path at left=10"

        # Simulate moving the top box left by 1 (left=10 → left=9)
        box_a.move(-1, 0)
        board.update_connections()
        path_after = arrow._compute_path()
        # Path must still have at least 2 points and arrowhead must match
        assert len(path_after) >= 2
        edge = arrow.end_connection.edge
        sc, sr = path_after[0]
        ec, er = path_after[-1]
        if edge in ("left", "right"):
            assert sc != ec, "Collinear mismatch after move"
        if edge in ("top", "bottom"):
            assert sr != er, "Collinear mismatch after move"


class TestCloudShape:
    def test_bounds(self):
        c = CloudShape(left=0, top=0, width=14, height=6)
        assert c.bound == (0, 0, 13, 5)

    def test_min_size_enforced(self):
        """Shapes below minimums are allowed in construction (needed for save/load fidelity)."""
        c = CloudShape(left=0, top=0, width=5, height=2)
        assert c.width == 5
        assert c.height == 2

    def test_contains(self):
        c = CloudShape(left=0, top=0, width=14, height=6)
        assert c.contains(7, 3)
        assert not c.contains(20, 20)

    def test_interior_bounds(self):
        c = CloudShape(left=0, top=0, width=14, height=6)
        interior = c.get_interior_bounds()
        assert interior == (1, 1, 12, 4)

    def test_render_has_cloud_chars(self):
        c = CloudShape(left=0, top=0, width=14, height=6)
        grid: dict[tuple[int, int], str] = {}
        c.render(grid)
        # Top row: space then underscores extending to right edge
        assert grid[(0, 0)] == " "
        assert grid[(1, 0)] == "_"
        assert grid[(12, 0)] == "_"
        assert grid[(13, 0)] == "_"  # underscore at right edge
        # Body parens
        assert grid[(0, 1)] == "("
        assert grid[(13, 1)] == ")"
        assert grid[(0, 2)] == "("
        assert grid[(13, 2)] == ")"
        # Bottom row: parens with underscores
        assert grid[(0, 5)] == "("
        assert grid[(1, 5)] == "_"
        assert grid[(12, 5)] == "_"
        assert grid[(13, 5)] == ")"

    def test_render_with_text(self):
        c = CloudShape(left=0, top=0, width=14, height=6, text="hi")
        grid: dict[tuple[int, int], str] = {}
        c.render(grid)
        c.render_text(grid)
        # Text should be rendered in interior (cols 1-12, rows 1-4)
        chars = [grid.get((col, row), " ") for col in range(1, 13) for row in range(1, 5)]
        assert "h" in chars
        assert "i" in chars

    def test_serialization_roundtrip(self):
        c = CloudShape(left=5, top=3, width=16, height=7, text="test")
        d = c.to_dict()
        assert d["type"] == "cloud"
        c2 = CloudShape.from_dict(d)
        assert c2.left == 5
        assert c2.top == 3
        assert c2.width == 16
        assert c2.height == 7
        assert c2.text == "test"

    def test_board_json_roundtrip(self):
        b = Board()
        c = CloudShape(left=0, top=0, width=14, height=6, text="cloud")
        b.add_shape(c)
        json_str = b.to_json()
        b2 = Board.from_json(json_str)
        assert len(b2.shapes) == 1
        restored = list(b2.shapes.values())[0]
        assert isinstance(restored, CloudShape)
        assert restored.text == "cloud"

    def test_arrow_connects_to_cloud(self):
        b = Board()
        c = CloudShape(left=0, top=0, width=14, height=6)
        b.add_shape(c)
        arrow = ArrowShape(
            start_col=20,
            start_row=3,
            end_col=15,
            end_row=3,
            end_connection=Connection(c.id, "right", 0.5),
        )
        b.add_shape(arrow)
        b.update_connections()
        assert arrow.end_col == c.right + 1


class TestArrowCornerDoesNotOverlapBox:
    """Regression: L-path corner must never land on a box's border."""

    @staticmethod
    def _render_all(board: Board) -> dict[tuple[int, int], str]:
        grid: dict[tuple[int, int], str] = {}
        for shape in board.z_sorted():
            shape.render(grid)
        return grid

    def test_move_box_up_arrow_does_not_overwrite_corner(self):
        """Moving top box up should not place arrow corner on box border."""
        # Box1 (small, top) and Box2 (large, below)
        box1 = RectangleShape(id="b1", left=0, top=0, width=13, height=5)
        box2 = RectangleShape(id="b2", left=0, top=5, width=24, height=10)
        arrow = ArrowShape(
            id="a",
            start_connection=Connection("b2", "top", 0.5),
            end_connection=Connection("b1", "right", 0.5),
        )
        board = Board()
        board.add_shape(box1)
        board.add_shape(box2)
        board.add_shape(arrow)
        board.update_connections()
        # Move box1 up by 1 row, creating a 2-row gap
        box1.move(0, -1)
        board.update_connections()
        # The arrow path should not place any character on box1's border
        path = arrow._compute_path()
        for col, row in path[:-1]:  # exclude arrowhead end point
            assert not box1.contains(col, row), f"Arrow path point ({col},{row}) overlaps box1 border"

    def test_move_box_up_preserves_box_corners(self):
        """After moving box up, the box corner characters must be preserved."""
        box1 = RectangleShape(id="b1", left=0, top=0, width=13, height=5)
        box2 = RectangleShape(id="b2", left=0, top=5, width=24, height=10)
        arrow = ArrowShape(
            id="a",
            start_connection=Connection("b2", "top", 0.5),
            end_connection=Connection("b1", "right", 0.5),
        )
        board = Board()
        board.add_shape(box1)
        board.add_shape(box2)
        board.add_shape(arrow)
        board.update_connections()
        box1.move(0, -1)
        board.update_connections()
        grid = self._render_all(board)
        # Box1 bottom-right corner must still be ┘
        assert grid[(box1.right, box1.bottom)] == "┘", (
            f"Expected ┘ at box1 bottom-right, got {grid.get((box1.right, box1.bottom))!r}"
        )
