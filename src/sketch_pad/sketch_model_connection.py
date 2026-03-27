"""
Sketch Pad data model – Connection and Board (serialisation).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sketch_pad.sketch_model_base import SNAP_DISTANCE, AbstractShape

# ─────────────────────── Connection ───────────────────────


@dataclass
class Connection:
    """Magnetic connection to a box edge."""

    shape_id: str
    edge: str  # 'top', 'bottom', 'left', 'right'
    ratio: float  # 0.0–1.0 along the edge
    pinned: bool = False  # True = manually set, immune to auto-optimization

    def to_dict(self) -> dict:
        d = {"shape_id": self.shape_id, "edge": self.edge, "ratio": self.ratio}
        if self.pinned:
            d["pinned"] = True
        return d

    @staticmethod
    def from_dict(d: dict) -> Connection:
        return Connection(
            shape_id=d["shape_id"],
            edge=d["edge"],
            ratio=d.get("ratio", 0.5),
            pinned=d.get("pinned", False),
        )


def _render_font_size_texts(shapes, grid: dict[tuple[int, int], str]):
    """Render text into grid for shapes with custom font_size (skipped by render())."""
    from sketch_pad.sketch_model_actors import CloudShape, DatabaseShape, TopicShape
    from sketch_pad.sketch_model_arrow import ArrowShape
    from sketch_pad.sketch_model_rectangle import RectangleShape

    for shape in shapes:
        if not getattr(shape, "font_size", None) or not shape.text:
            continue
        if isinstance(shape, (RectangleShape, DatabaseShape, TopicShape, CloudShape)):
            shape._render_text(grid)
        elif isinstance(shape, ArrowShape):
            path = shape._compute_path()
            if path:
                mid = path[len(path) // 2]
                lines = shape.text.split("\n")
                num_lines = len(lines)
                for i, line in enumerate(lines):
                    h_offset = -(len(line) // 2)
                    for j, ch in enumerate(line):
                        grid[(mid[0] + h_offset + j, mid[1] - num_lines + i)] = ch


# ─────────────────────── Board ───────────────────────


class Board:
    """Container for all shapes, managing z-ordering and rendering."""

    def __init__(self):
        self.shapes: dict[str, AbstractShape] = {}
        self._next_z: int = 0

    def add_shape(self, shape: AbstractShape) -> AbstractShape:
        shape.z_order = self._next_z
        self._next_z += 1
        self.shapes[shape.id] = shape
        return shape

    def remove_shape(self, shape_id: str):
        from sketch_pad.sketch_model_arrow import ArrowShape

        self.shapes.pop(shape_id, None)
        # Clean up arrow connections referencing removed shape
        for shape in self.shapes.values():
            if isinstance(shape, ArrowShape):
                if shape.start_connection and shape.start_connection.shape_id == shape_id:
                    shape.start_connection = None
                if shape.end_connection and shape.end_connection.shape_id == shape_id:
                    shape.end_connection = None

    def get_shape(self, shape_id: str) -> AbstractShape | None:
        return self.shapes.get(shape_id)

    def clear(self):
        self.shapes.clear()
        self._next_z = 0

    def is_empty(self) -> bool:
        return len(self.shapes) == 0

    def z_sorted(self) -> list[AbstractShape]:
        return sorted(self.shapes.values(), key=lambda s: s.z_order)

    def get_shape_at(self, col: int, row: int) -> AbstractShape | None:
        from sketch_pad.sketch_model_arrow import ArrowShape

        sorted_shapes = self.z_sorted()
        # Text labels render on top of everything — check them first
        for shape in reversed(sorted_shapes):
            if isinstance(shape, ArrowShape) and shape.text_contains(col, row):
                return shape
        # Then arrow paths
        for shape in reversed(sorted_shapes):
            if isinstance(shape, ArrowShape) and shape.contains(col, row):
                return shape
        # Then other shapes
        for shape in reversed(sorted_shapes):
            if not isinstance(shape, ArrowShape) and shape.contains(col, row):
                return shape
        return None

    def bounding_box(self) -> tuple[int, int, int, int] | None:
        """Return (left, top, right, bottom) enclosing all shapes, or None if empty."""
        if not self.shapes:
            return None
        bounds = [s.bound for s in self.shapes.values()]
        return (
            min(b[0] for b in bounds),
            min(b[1] for b in bounds),
            max(b[2] for b in bounds),
            max(b[3] for b in bounds),
        )

    def shapes_in_region(self, left: int, top: int, right: int, bottom: int) -> list[AbstractShape]:
        """Return all shapes whose bounding box intersects the given region."""
        result = []
        for shape in self.z_sorted():
            sl, st, sr, sb = shape.bound
            if sl <= right and sr >= left and st <= bottom and sb >= top:
                result.append(shape)
        return result

    def update_connections(self):
        """Recalculate all arrow endpoints from their connections."""
        from sketch_pad.sketch_model_arrow import ArrowShape

        for shape in self.shapes.values():
            if isinstance(shape, ArrowShape):
                shape.update_from_connections(self)

    def snap_to_edge(self, col: int, row: int, exclude_id: str | None = None) -> tuple[Connection, int, int] | None:
        """Find nearest shape edge within SNAP_DISTANCE. Returns (Connection, col, row) or None."""
        from sketch_pad.sketch_model_arrow import ArrowShape

        best: tuple[int, Connection, int, int] | None = None
        for shape in self.shapes.values():
            if isinstance(shape, ArrowShape):
                continue
            if shape.id == exclude_id:
                continue
            edge, ec, er, ratio = shape.nearest_edge_point(col, row)
            dist = abs(col - ec) + abs(row - er)
            if dist <= SNAP_DISTANCE:
                if best is None or dist < best[0]:
                    best = (dist, Connection(shape.id, edge, ratio), ec, er)
        if best:
            return best[1], best[2], best[3]
        return None

    def render(self) -> dict[tuple[int, int], str]:
        from sketch_pad.sketch_model_arrow import ArrowShape

        grid: dict[tuple[int, int], str] = {}
        sorted_shapes = self.z_sorted()
        # Phase 1: shape bodies (no text) – boxes, clouds, etc.
        for shape in sorted_shapes:
            if not isinstance(shape, ArrowShape):
                shape.render(grid)
        # Phase 2: arrows on top of shape bodies
        for shape in sorted_shapes:
            if isinstance(shape, ArrowShape):
                shape.render(grid)
        # Phase 3: text on top of everything
        for shape in sorted_shapes:
            shape.render_text(grid)
        return grid

    def to_json(self) -> str:
        self.update_connections()
        return json.dumps(
            {"version": 3, "format": "sketch_pad", "shapes": [s.to_dict() for s in self.z_sorted()]},
            separators=(",", ":"),
        )

    @staticmethod
    def from_json(text: str) -> Board:
        data = json.loads(text)
        board = Board()
        for sd in data.get("shapes", []):
            try:
                shape = AbstractShape.from_dict(sd)
                board.shapes[shape.id] = shape
                board._next_z = max(board._next_z, shape.z_order + 1)
            except ValueError:
                continue
        board.update_connections()
        return board

    def snapshot(self) -> str:
        return self.to_json()

    def restore(self, snapshot: str):
        restored = Board.from_json(snapshot)
        self.shapes = restored.shapes
        self._next_z = restored._next_z
