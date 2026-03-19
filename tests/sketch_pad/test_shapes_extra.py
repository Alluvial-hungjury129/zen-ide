"""Tests for sketch pad model — extra shape tests and edge cases."""

from sketch_pad.sketch_model import (
    AbstractShape,
    ArrowShape,
    RectangleShape,
)


# ---------------------------------------------------------------------------
# Shape construction & defaults
# ---------------------------------------------------------------------------
class TestShapeDefaults:
    def test_default_rectangle(self):
        s = RectangleShape()
        assert s.text == ""

    def test_unique_ids(self):
        a, b = RectangleShape(), RectangleShape()
        assert a.id != b.id

    def test_id_length(self):
        assert len(RectangleShape().id) == 8


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------------------
class TestShapeSerialization:
    def test_rectangle_round_trip(self):
        s = RectangleShape(left=15, top=10, width=5, height=5, text="hi")
        s2 = RectangleShape.from_dict(s.to_dict())
        assert (s2.left, s2.top) == (15, 10)
        assert s2.text == "hi"

    def test_text_independent(self):
        """Mutating original text should not affect serialized copy."""
        s = RectangleShape(text="ab")
        d = s.to_dict()
        s.text = "abc"
        assert d["text"] == "ab"

    def test_from_dict_with_type(self):
        s = AbstractShape.from_dict({"type": "rectangle", "left": 3, "text": "hi"})
        assert isinstance(s, RectangleShape)
        assert s.left == 3

    def test_arrow_round_trip(self):
        s = ArrowShape(start_col=1, start_row=0, end_col=10, end_row=5, text="label")
        s2 = ArrowShape.from_dict(s.to_dict())
        assert s2.start_col == 1
        assert s2.text == "label"


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------
class TestBoundsExtra:
    def test_arrow_bounds(self):
        s = ArrowShape(start_col=5, start_row=1, end_col=2, end_row=8)
        assert s.bound == (2, 1, 5, 8)

    def test_arrow_bounds_horizontal(self):
        s = ArrowShape(start_col=0, start_row=0, end_col=10, end_row=0)
        assert s.width == 11
        assert s.height == 1


# ---------------------------------------------------------------------------
# Contains point
# ---------------------------------------------------------------------------
class TestContainsPointExtra:
    def test_rectangle_contains(self):
        s = RectangleShape(left=0, top=0, width=10, height=10)
        assert s.contains(5, 5) is True
        assert s.contains(15, 5) is False

    def test_arrow_contains_on_path(self):
        s = ArrowShape(start_col=0, start_row=0, end_col=10, end_row=0)
        assert s.contains(5, 0) is True
        assert s.contains(5, 5) is False


# ---------------------------------------------------------------------------
# Interior bounds edge cases
# ---------------------------------------------------------------------------
class TestInteriorBoundsExtra:
    def test_rect_too_small(self):
        s = RectangleShape(left=0, top=0, width=2, height=2)
        assert s.get_interior_bounds() is None


# ---------------------------------------------------------------------------
# Move
# ---------------------------------------------------------------------------
class TestMoveExtra:
    def test_move_arrow(self):
        s = ArrowShape(start_col=2, start_row=3, end_col=8, end_row=9)
        s.move(1, -1)
        assert (s.start_col, s.start_row) == (3, 2)
        assert (s.end_col, s.end_row) == (9, 8)

    def test_move_preserves_dimensions(self):
        s = RectangleShape(left=5, top=3, width=10, height=6)
        s.move(3, -1)
        assert (s.width, s.height) == (10, 6)


# ---------------------------------------------------------------------------
# Copy
# ---------------------------------------------------------------------------
class TestCopyExtra:
    def test_deep_copy_text(self):
        s = RectangleShape(left=1, top=2, width=5, height=5, text="x")
        c = s.copy()
        c.text = "xy"
        assert s.text == "x"

    def test_copy_preserves_arrow(self):
        s = ArrowShape(start_col=0, start_row=0, end_col=10, end_row=5)
        c = s.copy()
        assert c.start_col == 0 and c.end_col == 10
