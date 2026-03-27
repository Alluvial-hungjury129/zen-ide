"""
Sketch Pad data model – base types.

Enums, border characters, constants, and AbstractShape base class.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto

# ─────────────────────── Tool Modes ───────────────────────


class ToolMode(Enum):
    SELECT = auto()
    PAN = auto()
    RECTANGLE = auto()
    ARROW = auto()
    ACTOR = auto()
    TOPIC = auto()
    DATABASE = auto()
    CLOUD = auto()


class ArrowLineStyle(Enum):
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


# ─────────────────────── Border Characters ───────────────────────


@dataclass(frozen=True)
class BorderChars:
    tl: str
    tr: str
    bl: str
    br: str
    h: str
    v: str


BORDER = BorderChars("┌", "┐", "└", "┘", "─", "│")

# Unicode box-drawing chars have East Asian Width "Ambiguous" — some editors
# render them double-wide, breaking column alignment.  This table maps every
# ambiguous char we emit to an ASCII equivalent for clipboard text.
_CLIPBOARD_XLAT = str.maketrans(
    "┌┐└┘─│┬┴├┤╭╮╯╰▲▼►◄",
    "++++-|++++++++^v><",
    "",
)

SNAP_DISTANCE = 3

# Arrow corner characters keyed by (incoming_direction, outgoing_direction)
CORNER_CHARS: dict[tuple[tuple[int, int], tuple[int, int]], str] = {
    ((1, 0), (0, 1)): "┐",  # right → down
    ((1, 0), (0, -1)): "┘",  # right → up
    ((-1, 0), (0, 1)): "┌",  # left → down
    ((-1, 0), (0, -1)): "└",  # left → up
    ((0, 1), (1, 0)): "└",  # down → right
    ((0, 1), (-1, 0)): "┘",  # down → left
    ((0, -1), (1, 0)): "┌",  # up → right
    ((0, -1), (-1, 0)): "┐",  # up → left
}


# ─────────────────────── Shapes ───────────────────────


@dataclass
class AbstractShape:
    """Base for all shapes on the board."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0
    z_order: int = 0
    fill_color: str | None = None
    text_color: str | None = None

    @property
    def right(self) -> int:
        return self.left + self.width - 1

    @property
    def bottom(self) -> int:
        return self.top + self.height - 1

    @property
    def bound(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)

    def contains(self, col: int, row: int) -> bool:
        return self.left <= col <= self.right and self.top <= row <= self.bottom

    def get_interior_bounds(self) -> tuple[int, int, int, int] | None:
        """Return (left, top, right, bottom) of interior, or None if too small."""
        inner_w = self.width - 2
        inner_h = self.height - 2
        if inner_w <= 0 or inner_h <= 0:
            return None
        return (self.left + 1, self.top + 1, self.right - 1, self.bottom - 1)

    def move(self, dcol: int, drow: int):
        self.left += dcol
        self.top += drow

    def render(self, grid: dict[tuple[int, int], str]):
        raise NotImplementedError

    def text_contains(self, col: int, row: int) -> bool:
        """Return True if (col, row) hits only the text label area."""
        return False

    def text_bounds(self) -> tuple[int, int, int, int] | None:
        """Return (left, top, right, bottom) of the text label area, or None."""
        return None

    def render_text(self, grid: dict[tuple[int, int], str]):
        """Render only text content. Override in subclasses with text."""
        pass

    def copy(self) -> AbstractShape:
        return copy.deepcopy(self)

    def nearest_edge_point(self, col: int, row: int) -> tuple[str, int, int, float]:
        """Find nearest point one cell outside the border to (col, row).
        Returns (edge_name, snap_col, snap_row, ratio).
        Arrows connect one cell outside the border so they visually touch
        without overwriting border characters.
        """

        def clamp(v, lo, hi):
            return max(lo, min(hi, v))

        # Avoid corner cells when shape is large enough
        h_lo = self.left + 1 if self.width > 2 else self.left
        h_hi = self.right - 1 if self.width > 2 else self.right
        v_lo = self.top + 1 if self.height > 2 else self.top
        v_hi = self.bottom - 1 if self.height > 2 else self.bottom

        candidates = []
        # Top edge (one cell above)
        ec = clamp(col, h_lo, h_hi)
        snap_row = self.top - 1
        dist = abs(col - ec) + abs(row - snap_row)
        ratio = (ec - self.left) / max(1, self.width - 1) if self.width > 1 else 0.5
        candidates.append((dist, "top", ec, snap_row, ratio))
        # Bottom edge (one cell below)
        snap_row = self.bottom + 1
        dist = abs(col - ec) + abs(row - snap_row)
        candidates.append((dist, "bottom", ec, snap_row, ratio))
        # Left edge (one cell left)
        er = clamp(row, v_lo, v_hi)
        snap_col = self.left - 1
        dist = abs(col - snap_col) + abs(row - er)
        ratio_v = (er - self.top) / max(1, self.height - 1) if self.height > 1 else 0.5
        candidates.append((dist, "left", snap_col, er, ratio_v))
        # Right edge (one cell right)
        snap_col = self.right + 1
        dist = abs(col - snap_col) + abs(row - er)
        candidates.append((dist, "right", snap_col, er, ratio_v))

        best = min(candidates, key=lambda c: c[0])
        return best[1], best[2], best[3], best[4]

    def edge_point_from_connection(self, edge: str, ratio: float) -> tuple[int, int]:
        """Get the grid point one cell outside a specific edge for arrow connection."""
        # Avoid corner cells when shape is large enough
        h_lo = self.left + 1 if self.width > 2 else self.left
        h_hi = self.right - 1 if self.width > 2 else self.right
        v_lo = self.top + 1 if self.height > 2 else self.top
        v_hi = self.bottom - 1 if self.height > 2 else self.bottom

        if edge == "top":
            c = self.left + round(ratio * max(0, self.width - 1))
            c = max(h_lo, min(h_hi, c))
            return (c, self.top - 1)
        elif edge == "bottom":
            c = self.left + round(ratio * max(0, self.width - 1))
            c = max(h_lo, min(h_hi, c))
            return (c, self.bottom + 1)
        elif edge == "left":
            r = self.top + round(ratio * max(0, self.height - 1))
            r = max(v_lo, min(v_hi, r))
            return (self.left - 1, r)
        elif edge == "right":
            r = self.top + round(ratio * max(0, self.height - 1))
            r = max(v_lo, min(v_hi, r))
            return (self.right + 1, r)
        return (self.left, self.top)

    def to_dict(self) -> dict:
        raise NotImplementedError

    @staticmethod
    def from_dict(d: dict) -> AbstractShape:
        # Lazy imports to avoid circular dependencies
        from sketch_pad.arrow_shape import ArrowShape
        from sketch_pad.database_shape import ActorShape, CloudShape, DatabaseShape, TopicShape
        from sketch_pad.rectangle_shape import RectangleShape

        t = d.get("type", "rectangle")
        if t == "rectangle":
            return RectangleShape.from_dict(d)
        elif t == "arrow":
            return ArrowShape.from_dict(d)
        elif t == "actor":
            return ActorShape.from_dict(d)
        elif t == "topic":
            return TopicShape.from_dict(d)
        elif t == "database":
            return DatabaseShape.from_dict(d)
        elif t == "cloud":
            return CloudShape.from_dict(d)
        raise ValueError(f"Unknown shape type: {t}")
