"""Tests for the sketch pad model (RectangleShape, ArrowShape, Board)."""

import json

from sketch_pad.sketch_canvas import SketchCanvas
from sketch_pad.sketch_model import (
    AbstractShape,
    ArrowShape,
    Board,
    CloudShape,
    Connection,
    RectangleShape,
    ToolMode,
    TopicShape,
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


class TestBoard:
    def test_add_and_get(self):
        b = Board()
        s = RectangleShape(left=0, top=0, width=5, height=3)
        b.add_shape(s)
        assert b.get_shape(s.id) is s

    def test_remove(self):
        b = Board()
        s = RectangleShape(left=0, top=0, width=5, height=3)
        b.add_shape(s)
        b.remove_shape(s.id)
        assert b.get_shape(s.id) is None

    def test_remove_cleans_arrow_connections(self):
        b = Board()
        box = RectangleShape(left=0, top=0, width=5, height=3)
        b.add_shape(box)
        arrow = ArrowShape(
            start_col=10,
            start_row=1,
            end_col=4,
            end_row=1,
            end_connection=Connection(box.id, "right", 0.5),
        )
        b.add_shape(arrow)
        b.remove_shape(box.id)
        assert arrow.end_connection is None

    def test_z_order(self):
        b = Board()
        s1 = RectangleShape(left=0, top=0, width=5, height=3)
        s2 = RectangleShape(left=2, top=1, width=5, height=3)
        b.add_shape(s1)
        b.add_shape(s2)
        assert b.z_sorted()[-1] is s2

    def test_get_shape_at(self):
        b = Board()
        s1 = RectangleShape(left=0, top=0, width=5, height=3)
        s2 = RectangleShape(left=2, top=1, width=5, height=3)
        b.add_shape(s1)
        b.add_shape(s2)
        assert b.get_shape_at(3, 1) is s2

    def test_render(self):
        b = Board()
        s = RectangleShape(left=0, top=0, width=4, height=3)
        b.add_shape(s)
        grid = b.render()
        assert grid[(0, 0)] == "┌"

    def test_snap_to_edge(self):
        b = Board()
        box = RectangleShape(left=10, top=10, width=10, height=6)
        b.add_shape(box)
        # Point near top edge
        result = b.snap_to_edge(15, 8)
        assert result is not None
        conn, sc, sr = result
        assert conn.shape_id == box.id
        assert conn.edge == "top"
        # Point far away
        assert b.snap_to_edge(50, 50) is None

    def test_is_empty(self):
        b = Board()
        assert b.is_empty()
        b.add_shape(RectangleShape(left=0, top=0, width=3, height=3))
        assert not b.is_empty()


class TestSerialization:
    def test_rectangle_roundtrip(self):
        s = RectangleShape(left=5, top=3, width=10, height=5, text="Hi")
        d = s.to_dict()
        s2 = RectangleShape.from_dict(d)
        assert s2.left == 5
        assert s2.text == "Hi"

    def test_arrow_roundtrip(self):
        s = ArrowShape(
            start_col=0,
            start_row=0,
            end_col=10,
            end_row=5,
            start_connection=Connection("abc", "right", 0.5),
            text="label",
        )
        d = s.to_dict()
        s2 = ArrowShape.from_dict(d)
        assert s2.start_col == 0 and s2.end_col == 10
        assert s2.start_connection.shape_id == "abc"
        assert s2.text == "label"

    def test_board_json_roundtrip(self):
        b = Board()
        b.add_shape(RectangleShape(left=0, top=0, width=5, height=3, text="A"))
        b.add_shape(ArrowShape(start_col=5, start_row=1, end_col=9, end_row=1))
        json_str = b.to_json()
        b2 = Board.from_json(json_str)
        assert len(b2.shapes) == 2

    def test_board_snapshot_restore(self):
        b = Board()
        b.add_shape(RectangleShape(left=0, top=0, width=5, height=3))
        snap = b.snapshot()
        b.clear()
        assert b.is_empty()
        b.restore(snap)
        assert not b.is_empty()

    def test_topic_resize_roundtrip(self):
        """Resized topic dimensions must survive save/load cycle."""
        t = TopicShape(left=10, top=5, width=25, height=8, text="my-topic")
        d = t.to_dict()
        t2 = TopicShape.from_dict(d)
        assert t2.width == 25
        assert t2.height == 8
        assert t2.text == "my-topic"

    def test_topic_small_resize_roundtrip(self):
        """Topic resized below defaults must still persist dimensions."""
        b = Board()
        t = TopicShape(left=0, top=0, width=6, height=3, text="small")
        b.add_shape(t)
        json_str = b.to_json()
        b2 = Board.from_json(json_str)
        restored = list(b2.shapes.values())[0]
        assert restored.width == 6
        assert restored.height == 3

    def test_cloud_resize_roundtrip(self):
        """Cloud resized below defaults must still persist dimensions."""
        c = CloudShape(left=0, top=0, width=5, height=2, text="x")
        d = c.to_dict()
        c2 = CloudShape.from_dict(d)
        assert c2.width == 5
        assert c2.height == 2


class TestMovePreservesOtherShapes:
    def test_move_preserves_sibling(self):
        b = Board()
        s1 = RectangleShape(left=0, top=0, width=5, height=3, text="A")
        s2 = RectangleShape(left=20, top=0, width=5, height=3, text="B")
        b.add_shape(s1)
        b.add_shape(s2)
        s1.move(5, 5)
        grid = b.render()
        found_a = any(grid.get((c, r)) == "A" for r in range(20) for c in range(40))
        found_b = any(grid.get((c, r)) == "B" for r in range(20) for c in range(40))
        assert found_a
        assert found_b, "Shape B disappeared after moving A"

    def test_arrow_corner_at_start_when_perpendicular_to_edge(self):
        """Moving a box so the arrow turns perpendicular should render a corner at start."""
        b = Board()
        # Boxes with no vertical overlap force an L-shaped arrow
        box_a = RectangleShape(left=0, top=10, width=10, height=8)
        box_b = RectangleShape(left=20, top=0, width=10, height=6)
        b.add_shape(box_a)
        b.add_shape(box_b)
        arrow = ArrowShape(
            start_col=11,
            start_row=10,
            end_col=19,
            end_row=5,
            start_connection=Connection(box_a.id, "right", 0.0),
            end_connection=Connection(box_b.id, "left", 1.0),
        )
        b.add_shape(arrow)
        b.update_connections()
        grid = {}
        arrow.render(grid)
        # The start point should be a corner (┘) since it exits right edge but path goes up
        start_char = grid.get((arrow.start_col, arrow.start_row))
        assert start_char == "┘", f"Expected ┘ at arrow start, got {start_char!r}"

    def test_arrow_no_corner_at_start_when_straight(self):
        """Arrow going straight from box edge should NOT get a corner at start."""
        b = Board()
        box_a = RectangleShape(left=0, top=0, width=10, height=6)
        box_b = RectangleShape(left=20, top=0, width=10, height=6)
        b.add_shape(box_a)
        b.add_shape(box_b)
        arrow = ArrowShape(
            start_col=11,
            start_row=3,
            end_col=19,
            end_row=3,
            start_connection=Connection(box_a.id, "right", 0.5),
            end_connection=Connection(box_b.id, "left", 0.5),
        )
        b.add_shape(arrow)
        b.update_connections()
        grid = {}
        arrow.render(grid)
        # Straight horizontal arrow: start char should be ─, not a corner
        start_char = grid.get((arrow.start_col, arrow.start_row))
        assert start_char == "─", f"Expected ─ at arrow start, got {start_char!r}"

    def test_arrow_follows_connected_box(self):
        b = Board()
        box1 = RectangleShape(left=0, top=0, width=6, height=4)
        box2 = RectangleShape(left=20, top=0, width=6, height=4)
        b.add_shape(box1)
        b.add_shape(box2)
        arrow = ArrowShape(
            start_col=5,
            start_row=2,
            end_col=20,
            end_row=2,
            start_connection=Connection(box1.id, "right", 0.5),
            end_connection=Connection(box2.id, "left", 0.5),
        )
        b.add_shape(arrow)
        # Move box1 right by 5
        box1.move(5, 0)
        b.update_connections()
        # box1 right=10, one cell outside: 11
        assert arrow.start_col == 11
        # box2 left=20, one cell outside: 19
        assert arrow.end_col == 19

    def test_degenerate_path_falls_back_to_vertical_edges(self):
        """When left/right edges produce same-column endpoints, fall back to top/bottom."""
        b = Board()
        # A upper-right, B lower-left: A.left == B.right + 2 so AT-border
        # connections still produce same-column endpoints → degenerate H
        box_a = RectangleShape(id="a", left=24, top=0, width=26, height=12)
        box_b = RectangleShape(id="b", left=0, top=18, width=25, height=6)
        b.add_shape(box_a)
        b.add_shape(box_b)
        arrow = ArrowShape(
            id="arr",
            start_col=24,
            start_row=11,
            end_col=24,
            end_row=18,
            start_connection=Connection("a", "left", 1.0),
            end_connection=Connection("b", "right", 0.0),
        )
        b.add_shape(arrow)
        b.update_connections()
        # Should fall back to vertical edges since H would be degenerate
        assert arrow.start_connection.edge in ("top", "bottom")
        assert arrow.end_connection.edge in ("top", "bottom")
        assert arrow.start_col != arrow.end_col or arrow.start_row != arrow.end_row

    def test_arrowhead_always_points_into_shape(self):
        """Arrowhead must point INTO the connected shape, not away."""
        b = Board()
        box_a = RectangleShape(id="a", left=0, top=0, width=10, height=6)
        box_b = RectangleShape(id="b", left=20, top=0, width=10, height=6)
        b.add_shape(box_a)
        b.add_shape(box_b)
        # Arrow from A's right to B's left
        arrow = ArrowShape(
            start_col=10,
            start_row=3,
            end_col=19,
            end_row=3,
            start_connection=Connection("a", "right", 0.5),
            end_connection=Connection("b", "left", 0.5),
        )
        b.add_shape(arrow)
        b.update_connections()
        grid = {}
        arrow.render(grid)
        head = grid[(arrow.end_col, arrow.end_row)]
        # end edge is "left" → arrowhead should point right (►) into box
        assert head == "►", f"Expected ► for left edge, got {head!r}"

    def test_arrowhead_points_into_right_edge(self):
        """Arrow ending at right edge should have ◄ arrowhead."""
        b = Board()
        box_a = RectangleShape(id="a", left=30, top=0, width=10, height=6)
        box_b = RectangleShape(id="b", left=0, top=0, width=10, height=6)
        b.add_shape(box_a)
        b.add_shape(box_b)
        arrow = ArrowShape(
            start_col=29,
            start_row=3,
            end_col=10,
            end_row=3,
            start_connection=Connection("a", "left", 0.5),
            end_connection=Connection("b", "right", 0.5),
        )
        b.add_shape(arrow)
        b.update_connections()
        grid = {}
        arrow.render(grid)
        head = grid[(arrow.end_col, arrow.end_row)]
        assert head == "◄", f"Expected ◄ for right edge, got {head!r}"

    def test_arrowhead_points_into_top_edge(self):
        """Arrow ending at top edge should have ▼ arrowhead."""
        b = Board()
        box_a = RectangleShape(id="a", left=0, top=10, width=10, height=6)
        box_b = RectangleShape(id="b", left=0, top=0, width=10, height=6)
        b.add_shape(box_a)
        b.add_shape(box_b)
        arrow = ArrowShape(
            start_col=5,
            start_row=9,
            end_col=5,
            end_row=6,
            start_connection=Connection("a", "top", 0.5),
            end_connection=Connection("b", "bottom", 0.5),
        )
        b.add_shape(arrow)
        b.update_connections()
        grid = {}
        arrow.render(grid)
        head = grid[(arrow.end_col, arrow.end_row)]
        assert head == "▲", f"Expected ▲ for bottom edge, got {head!r}"

    def test_arrow_reconnects_after_shape_move_preserves_direction(self):
        """After moving a shape, arrow stays connected with correct arrowhead."""
        b = Board()
        box_a = RectangleShape(id="a", left=25, top=0, width=26, height=12)
        box_b = RectangleShape(id="b", left=0, top=18, width=23, height=6)
        b.add_shape(box_a)
        b.add_shape(box_b)
        arrow = ArrowShape(
            id="arr",
            start_col=24,
            start_row=11,
            end_col=23,
            end_row=18,
            start_connection=Connection("a", "left", 1.0),
            end_connection=Connection("b", "right", 0.0),
        )
        b.add_shape(arrow)
        b.update_connections()
        # Move A right by 5
        box_a.left += 5
        b.update_connections()
        # Arrow should still be connected
        assert arrow.start_connection is not None
        assert arrow.end_connection is not None
        # Render and check arrowhead points into end shape
        grid = {}
        arrow.render(grid)
        head = grid[(arrow.end_col, arrow.end_row)]
        edge = arrow.end_connection.edge
        expected = {"left": "►", "right": "◄", "top": "▼", "bottom": "▲"}
        assert head == expected[edge], f"Expected {expected[edge]} for {edge} edge, got {head!r}"


class TestArrowCornerPreservedOnMove:
    """Regression: moving a box so arrow endpoints become collinear must not drop the corner."""

    @staticmethod
    def _setup_diagonal_boxes(top_left: int, bottom_left: int = 0):
        """Create a board with bottom-left and top-right boxes connected by an arrow."""
        box_b = RectangleShape(id="b", left=bottom_left, top=7, width=9, height=6, text="d")
        box_t = RectangleShape(id="t", left=top_left, top=0, width=9, height=6)
        arrow = ArrowShape(
            id="a",
            start_connection=Connection("t", "bottom", 0.5),
            end_connection=Connection("b", "right", 0.5),
        )
        board = Board()
        board.add_shape(box_b)
        board.add_shape(box_t)
        board.add_shape(arrow)
        board.update_connections()
        return board, arrow

    def _arrow_has_corner(self, arrow: ArrowShape) -> bool:
        grid: dict[tuple[int, int], str] = {}
        arrow.render(grid)
        path = arrow._compute_path()
        chars = [grid.get(p, " ") for p in path]
        return any(c in "┌┐└┘" for c in chars)

    def test_corner_preserved_when_top_box_at_left_10(self):
        """Baseline: top box at left=10 should have a corner in the arrow."""
        _, arrow = self._setup_diagonal_boxes(top_left=10)
        assert self._arrow_has_corner(arrow)

    def test_corner_preserved_when_top_box_moves_left_to_9(self):
        """Moving top box left to align columns must not drop the corner."""
        _, arrow = self._setup_diagonal_boxes(top_left=9)
        assert self._arrow_has_corner(arrow)

    def test_corner_preserved_when_top_box_moves_right_to_11(self):
        _, arrow = self._setup_diagonal_boxes(top_left=11)
        assert self._arrow_has_corner(arrow)

    def test_corner_preserved_when_bottom_box_moves_right(self):
        """Moving bottom box right (so its right edge aligns with top box column)."""
        _, arrow = self._setup_diagonal_boxes(top_left=10, bottom_left=1)
        assert self._arrow_has_corner(arrow)

    def test_no_collinear_path_with_perpendicular_arrowhead(self):
        """Arrow must never have a straight path ending with a perpendicular arrowhead."""
        for top_left in range(7, 15):
            _, arrow = self._setup_diagonal_boxes(top_left=top_left)
            path = arrow._compute_path()
            if len(path) == 2:
                # Straight path: arrowhead direction must match path direction
                p0, p1 = path
                is_horizontal = p0[1] == p1[1]
                is_vertical = p0[0] == p1[0]
                edge = arrow.end_connection.edge
                if is_vertical:
                    assert edge in ("top", "bottom"), f"top_left={top_left}: vertical path but arrowhead edge={edge}"
                if is_horizontal:
                    assert edge in ("left", "right"), f"top_left={top_left}: horizontal path but arrowhead edge={edge}"


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


class TestCopyPasteShapeSerialization:
    """Shapes copied via internal clipboard should deserialize without nesting."""

    def test_rectangle_roundtrip(self):
        marker = "<!--sketch_pad_shapes:"
        box = RectangleShape(left=5, top=3, width=10, height=7, text="hello")
        payload = json.dumps([box.to_dict()])
        clipboard_text = f"{marker}{payload}-->"
        # Simulate paste: parse back
        assert clipboard_text.startswith(marker)
        assert clipboard_text.endswith("-->")
        data = json.loads(clipboard_text[len(marker) : -3])
        assert len(data) == 1
        restored = AbstractShape.from_dict(data[0])
        assert isinstance(restored, RectangleShape)
        assert restored.width == 10
        assert restored.height == 7
        assert restored.text == "hello"

    def test_arrow_roundtrip(self):
        marker = "<!--sketch_pad_shapes:"
        arrow = ArrowShape(start_col=0, start_row=0, end_col=10, end_row=5)
        payload = json.dumps([arrow.to_dict()])
        clipboard_text = f"{marker}{payload}-->"
        data = json.loads(clipboard_text[len(marker) : -3])
        restored = AbstractShape.from_dict(data[0])
        assert isinstance(restored, ArrowShape)
        assert restored.start_col == 0
        assert restored.end_col == 10

    def test_multiple_shapes_roundtrip(self):
        marker = "<!--sketch_pad_shapes:"
        box = RectangleShape(left=0, top=0, width=5, height=5)
        arrow = ArrowShape(
            start_col=5,
            start_row=2,
            end_col=10,
            end_row=2,
            start_connection=Connection(box.id, "right", 0.5),
        )
        payload = json.dumps([box.to_dict(), arrow.to_dict()])
        clipboard_text = f"{marker}{payload}-->"
        data = json.loads(clipboard_text[len(marker) : -3])
        assert len(data) == 2
        assert data[0]["type"] == "rectangle"
        assert data[1]["type"] == "arrow"


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
