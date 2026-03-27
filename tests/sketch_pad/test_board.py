"""Tests for Board class — add/remove, z-order, connections, arrow rendering on moves, serialization."""

import json

from sketch_pad.sketch_model import (
    AbstractShape,
    ArrowShape,
    Board,
    CloudShape,
    Connection,
    RectangleShape,
    TopicShape,
)


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
