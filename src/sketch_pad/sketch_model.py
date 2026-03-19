"""
Sketch Pad data model – ASCII diagram editor.

Shapes: Rectangle (boxes) and Arrow (connections).
Each shape renders to a character grid; the Board composites all shapes in z-order.
"""

from __future__ import annotations

import copy
import json
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


def _clamp_edge_ratio_v(box: AbstractShape, target_y: float) -> float:
    """Compute ratio along a vertical edge (left/right) for a target y."""
    if box.height <= 1:
        return 0.5
    clamped = max(box.top, min(box.bottom, round(target_y)))
    return (clamped - box.top) / (box.height - 1)


def _clamp_edge_ratio_h(box: AbstractShape, target_x: float) -> float:
    """Compute ratio along a horizontal edge (top/bottom) for a target x."""
    if box.width <= 1:
        return 0.5
    clamped = max(box.left, min(box.right, round(target_x)))
    return (clamped - box.left) / (box.width - 1)


def _compute_h_edges(
    box_a: AbstractShape, box_b: AbstractShape, dx: float, ay: float, by: float
) -> tuple[str, float, str, float]:
    """Compute horizontal (left/right) edge pair and ratios."""
    a_edge, b_edge = ("right", "left") if dx >= 0 else ("left", "right")
    overlap_top = max(box_a.top, box_b.top)
    overlap_bot = min(box_a.bottom, box_b.bottom)
    if overlap_top <= overlap_bot:
        target_y = (overlap_top + overlap_bot) / 2
    else:
        # Use gap midpoint so connection points hug the nearest edges
        gap_near = min(box_a.bottom, box_b.bottom)
        gap_far = max(box_a.top, box_b.top)
        target_y = (gap_near + gap_far) / 2
    a_ratio = _clamp_edge_ratio_v(box_a, target_y)
    b_ratio = _clamp_edge_ratio_v(box_b, target_y)
    return a_edge, a_ratio, b_edge, b_ratio


def _compute_v_edges(
    box_a: AbstractShape, box_b: AbstractShape, dy: float, ax: float, bx: float
) -> tuple[str, float, str, float]:
    """Compute vertical (top/bottom) edge pair and ratios."""
    a_edge, b_edge = ("bottom", "top") if dy >= 0 else ("top", "bottom")
    overlap_left = max(box_a.left, box_b.left)
    overlap_right = min(box_a.right, box_b.right)
    if overlap_left <= overlap_right:
        target_x = (overlap_left + overlap_right) / 2
    else:
        # Use gap midpoint so connection points hug the nearest edges
        gap_near = min(box_a.right, box_b.right)
        gap_far = max(box_a.left, box_b.left)
        target_x = (gap_near + gap_far) / 2
    a_ratio = _clamp_edge_ratio_h(box_a, target_x)
    b_ratio = _clamp_edge_ratio_h(box_b, target_x)
    return a_edge, a_ratio, b_edge, b_ratio


def _edges_are_degenerate(
    box_a: AbstractShape, box_b: AbstractShape, a_edge: str, a_ratio: float, b_edge: str, b_ratio: float
) -> bool:
    """Check if edge points produce a degenerate or backwards path.

    Detects when the arrow start is at or past the arrow end in the expected
    travel direction, which would route the path through box borders.
    """
    sc, sr = box_a.edge_point_from_connection(a_edge, a_ratio)
    ec, er = box_b.edge_point_from_connection(b_edge, b_ratio)
    if a_edge in ("left", "right"):
        if a_edge == "right":
            return sc >= ec
        return sc <= ec  # a_edge == "left"
    else:
        if a_edge == "bottom":
            return sr >= er
        return sr <= er  # a_edge == "top"


def _pick_barely_degenerate(
    box_a: AbstractShape,
    box_b: AbstractShape,
    *edge_sets: tuple[str, float, str, float],
) -> tuple[str, float, str, float] | None:
    """Return the best barely-degenerate face-to-face edge pair, if any.

    A pair is "barely degenerate" when start and end land on the same
    row (for top/bottom edges) or same column (for left/right edges)
    but the perpendicular distance is long enough for a visible path.
    Rejects pairs that produce collinear mismatches (e.g. vertical path
    with horizontal arrowhead).
    """
    best: tuple[str, float, str, float] | None = None
    best_dist = 0
    for edges in edge_sets:
        a_edge, a_ratio, b_edge, b_ratio = edges
        sc, sr = box_a.edge_point_from_connection(a_edge, a_ratio)
        ec, er = box_b.edge_point_from_connection(b_edge, b_ratio)
        if a_edge in ("left", "right"):
            if sc != ec:
                continue  # truly backwards, not barely degenerate
            # Vertical path with horizontal arrowhead → collinear mismatch
            if b_edge in ("left", "right"):
                continue
            dist = abs(er - sr)
        else:
            if sr != er:
                continue
            # Horizontal path with vertical arrowhead → collinear mismatch
            if b_edge in ("top", "bottom"):
                continue
            dist = abs(ec - sc)
        if dist > 2 and dist > best_dist:
            best = edges
            best_dist = dist
    return best


def _point_in_box(box: AbstractShape, col: int, row: int) -> bool:
    """Check if a point falls within a box's bounding rectangle (border or interior)."""
    return box.left <= col <= box.right and box.top <= row <= box.bottom


_EDGE_DIR = {"right": (1, 0), "left": (-1, 0), "top": (0, -1), "bottom": (0, 1)}


def _would_uturn(a_edge: str, b_edge: str, sc: int, sr: int, ec: int, er: int) -> bool:
    """Check if the L-path first segment direction opposes the start edge exit."""
    d_exit = _EDGE_DIR[a_edge]
    if sc == ec and sr == er:
        return True
    h_first = b_edge in ("top", "bottom")
    if h_first:
        d_first = ((1 if ec > sc else -1), 0) if ec != sc else (0, (1 if er > sr else -1))
    else:
        d_first = (0, (1 if er > sr else -1)) if er != sr else ((1 if ec > sc else -1), 0)
    return (d_exit[0] != 0 and d_first[0] == -d_exit[0]) or (d_exit[1] != 0 and d_first[1] == -d_exit[1])


def _rate_candidate(
    box_a: AbstractShape,
    box_b: AbstractShape,
    a_edge: str,
    a_ratio: float,
    b_edge: str,
    b_ratio: float,
) -> tuple[int, int]:
    """Score a candidate: (penalty, distance). Lower is better.

    penalty: 0 = ideal, 1 = start hidden, 2 = U-turn or collinear mismatch, 3 = overlapping.
    """
    sc, sr = box_a.edge_point_from_connection(a_edge, a_ratio)
    ec, er = box_b.edge_point_from_connection(b_edge, b_ratio)
    dist = abs(ec - sc) + abs(er - sr)
    if dist == 0:
        return (3, 0)
    # Penalise collinear mismatch: straight path but arrowhead perpendicular.
    # e.g. vertical path (sc==ec) with left/right arrowhead → visually broken.
    if (sc == ec and b_edge in ("left", "right")) or (sr == er and b_edge in ("top", "bottom")):
        return (2, dist)
    if _would_uturn(a_edge, b_edge, sc, sr, ec, er):
        return (2, dist)
    if _point_in_box(box_b, sc, sr):
        return (1, dist)
    # Check if the L-path corner point overlaps either box's border/interior.
    if sc != ec and sr != er:
        if b_edge in ("top", "bottom"):
            corner = (ec, sr)  # h_first path
        else:
            corner = (sc, er)  # v_first path
        if _point_in_box(box_a, *corner) or _point_in_box(box_b, *corner):
            return (1, dist)
    return (0, dist)


def _compute_diagonal_edges(
    box_a: AbstractShape, box_b: AbstractShape, dx: float, dy: float
) -> tuple[str, float, str, float] | None:
    """Compute mixed edge pairs for diagonally-adjacent boxes.

    When both standard face-to-face pairs are degenerate (boxes too close on the
    diagonal), try cross-orientation pairs like top→left or right→bottom.
    Prefers paths where the arrow start is visible and the path doesn't U-turn.
    Returns (a_edge, a_ratio, b_edge, b_ratio) or None if no valid pair found.
    """
    a_h = "right" if dx >= 0 else "left"
    b_h = "left" if dx >= 0 else "right"
    a_v = "bottom" if dy >= 0 else "top"
    b_v = "top" if dy >= 0 else "bottom"

    candidates: list[tuple[str, float, str, float, int]] = []
    for a_edge, b_edge in [(a_v, b_h), (a_h, b_v)]:
        a_ratio, b_ratio = _mixed_ratios(box_a, box_b, a_edge, b_edge)
        sc, sr = box_a.edge_point_from_connection(a_edge, a_ratio)
        ec, er = box_b.edge_point_from_connection(b_edge, b_ratio)
        dist = abs(ec - sc) + abs(er - sr)
        candidates.append((a_edge, a_ratio, b_edge, b_ratio, dist))

    # Collect all viable options: original candidates + nudged variants
    options: list[tuple[tuple[int, int], str, float, str, float]] = []

    for a_edge, a_ratio, b_edge, b_ratio, dist in candidates:
        if dist > 0:
            score = _rate_candidate(box_a, box_b, a_edge, a_ratio, b_edge, b_ratio)
            options.append((score, a_edge, a_ratio, b_edge, b_ratio))

        # Also try nudged variants (handles dist==0 and may improve dist>0)
        if a_edge in ("top", "bottom"):
            step = 1.0 / max(1, box_a.width - 1)
        else:
            step = 1.0 / max(1, box_a.height - 1)
        for direction in (-1, 1):
            nudged = max(0.0, min(1.0, a_ratio + direction * step))
            if nudged == a_ratio:
                continue
            sc, sr = box_a.edge_point_from_connection(a_edge, nudged)
            ec, er = box_b.edge_point_from_connection(b_edge, b_ratio)
            if abs(ec - sc) + abs(er - sr) > 0:
                score = _rate_candidate(box_a, box_b, a_edge, nudged, b_edge, b_ratio)
                options.append((score, a_edge, nudged, b_edge, b_ratio))

    if not options:
        return None
    options.sort(key=lambda o: o[0])
    return options[0][1], options[0][2], options[0][3], options[0][4]


def _mixed_ratios(box_a: AbstractShape, box_b: AbstractShape, a_edge: str, b_edge: str) -> tuple[float, float]:
    """Compute optimal ratios for a mixed (cross-orientation) edge pair."""
    if a_edge in ("top", "bottom") and b_edge in ("left", "right"):
        b_col = box_b.left - 1 if b_edge == "left" else box_b.right + 1
        a_ratio = max(0.0, min(1.0, (b_col - box_a.left) / max(1, box_a.width - 1)))
        a_row = box_a.top - 1 if a_edge == "top" else box_a.bottom + 1
        b_ratio = max(0.0, min(1.0, (a_row - box_b.top) / max(1, box_b.height - 1)))
    elif a_edge in ("left", "right") and b_edge in ("top", "bottom"):
        b_row = box_b.top - 1 if b_edge == "top" else box_b.bottom + 1
        a_ratio = max(0.0, min(1.0, (b_row - box_a.top) / max(1, box_a.height - 1)))
        a_col = box_a.left - 1 if a_edge == "left" else box_a.right + 1
        b_ratio = max(0.0, min(1.0, (a_col - box_b.left) / max(1, box_b.width - 1)))
    else:
        a_ratio, b_ratio = 0.5, 0.5
    return a_ratio, b_ratio


def _best_edges_between(box_a: AbstractShape, box_b: AbstractShape) -> tuple[str, float, str, float]:
    """Compute optimal (edge, ratio) for both ends of an arrow between two boxes.

    Picks facing edges and aligns connection points to produce the straightest
    possible arrow.  Falls back to the other orientation if the primary choice
    produces a degenerate path, then to diagonal (mixed) edge pairs for
    diagonally-adjacent boxes.
    Returns (a_edge, a_ratio, b_edge, b_ratio).
    """
    ax = (box_a.left + box_a.right) / 2
    ay = (box_a.top + box_a.bottom) / 2
    bx = (box_b.left + box_b.right) / 2
    by = (box_b.top + box_b.bottom) / 2
    dx, dy = bx - ax, by - ay

    # When boxes are clearly separated on one axis (no overlap) but overlap
    # on the other, always prefer the face-to-face connection across the gap.
    h_separated = box_b.left > box_a.right or box_a.left > box_b.right
    v_separated = box_b.top > box_a.bottom or box_a.top > box_b.bottom
    if h_separated and not v_separated:
        primary_h = True
    elif v_separated and not h_separated:
        primary_h = False
    else:
        primary_h = abs(dx) >= abs(dy)

    if primary_h:
        result = _compute_h_edges(box_a, box_b, dx, ay, by)
        if not _edges_are_degenerate(box_a, box_b, *result):
            return result
        # When boxes are clearly h-separated but the gap is so small that
        # the "one cell outside" edge points collide (same column), the
        # degenerate check fires even though horizontal is still correct.
        # Return horizontal edges — renders as a minimal arrowhead in the gap.
        if h_separated and not v_separated:
            return result
        alt = _compute_v_edges(box_a, box_b, dy, ax, bx)
        if not _edges_are_degenerate(box_a, box_b, *alt):
            return alt
        # Both degenerate: prefer a barely-degenerate face-to-face edge pair
        # (same row/col but decent path length) over diagonal mixed edges.
        barely = _pick_barely_degenerate(box_a, box_b, result, alt)
        if barely:
            return barely
        diag = _compute_diagonal_edges(box_a, box_b, dx, dy)
        if diag:
            return diag
        return result
    else:
        result = _compute_v_edges(box_a, box_b, dy, ax, bx)
        if not _edges_are_degenerate(box_a, box_b, *result):
            return result
        alt = _compute_h_edges(box_a, box_b, dx, ay, by)
        if not _edges_are_degenerate(box_a, box_b, *alt):
            return alt
        barely = _pick_barely_degenerate(box_a, box_b, result, alt)
        if barely:
            return barely
        diag = _compute_diagonal_edges(box_a, box_b, dx, dy)
        if diag:
            return diag
        return result


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


# ─────────────────────── Rectangle ───────────────────────


def _word_wrap_into(line: str, width: int, out: list[str]):
    """Word-wrap *line* into chunks of at most *width* chars, appending to *out*."""
    while len(line) > width:
        # Try to break at a space
        brk = line.rfind(" ", 0, width + 1)
        if brk <= 0:
            brk = width
        out.append(line[:brk])
        line = line[brk:].lstrip(" ")
    out.append(line)


@dataclass
class RectangleShape(AbstractShape):
    """A rectangle with Unicode border and optional text content."""

    text: str = ""
    font_size: float | None = None  # None = use canvas default

    def render(self, grid: dict[tuple[int, int], str]):
        if self.width < 2 or self.height < 2:
            return
        bc = BORDER

        # Corners
        grid[(self.left, self.top)] = bc.tl
        grid[(self.right, self.top)] = bc.tr
        grid[(self.left, self.bottom)] = bc.bl
        grid[(self.right, self.bottom)] = bc.br
        # Horizontal edges
        for col in range(self.left + 1, self.right):
            grid[(col, self.top)] = bc.h
            grid[(col, self.bottom)] = bc.h
        # Vertical edges
        for row in range(self.top + 1, self.bottom):
            grid[(self.left, row)] = bc.v
            grid[(self.right, row)] = bc.v

        # Fill interior with spaces to mask shapes behind in z-order
        for row in range(self.top + 1, self.bottom):
            for col in range(self.left + 1, self.right):
                grid[(col, row)] = " "

    def render_text(self, grid: dict[tuple[int, int], str]):
        if self.text and not self.font_size:
            self._render_text(grid)

    def _render_text(self, grid: dict[tuple[int, int], str]):
        inner_left = self.left + 1
        inner_top = self.top + 1
        inner_w = self.width - 2
        inner_h = self.height - 2
        if inner_w <= 0 or inner_h <= 0:
            return
        # Word-wrap lines that exceed inner_w
        wrapped: list[str] = []
        for line in self.text.split("\n"):
            if len(line) <= inner_w:
                wrapped.append(line)
            else:
                _word_wrap_into(line, inner_w, wrapped)
        v_offset = max(0, (inner_h - len(wrapped)) // 2)
        for i, line in enumerate(wrapped):
            row = inner_top + v_offset + i
            if row > self.bottom - 1:
                break
            text = line[:inner_w]
            h_offset = max(0, (inner_w - len(text)) // 2)
            for j, ch in enumerate(text):
                grid[(inner_left + h_offset + j, row)] = ch

    def get_interior_bounds(self) -> tuple[int, int, int, int] | None:
        """Return (left, top, right, bottom) of interior, or None if too small."""
        inner_w = self.width - 2
        inner_h = self.height - 2
        if inner_w <= 0 or inner_h <= 0:
            return None
        return (self.left + 1, self.top + 1, self.right - 1, self.bottom - 1)

    def min_size_for_text(self) -> tuple[int, int]:
        """Return minimum (width, height) to contain the current text."""
        if not self.text:
            return (2, 2)
        lines = self.text.split("\n")
        max_line_len = max((len(l) for l in lines), default=0)
        return (max_line_len + 2, len(lines) + 2)

    def to_dict(self) -> dict:
        d = {
            "type": "rectangle",
            "id": self.id,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "z_order": self.z_order,
            "text": self.text,
        }
        if self.font_size is not None:
            d["font_size"] = self.font_size
        if self.fill_color:
            d["fill_color"] = self.fill_color
        if self.text_color:
            d["text_color"] = self.text_color
        return d

    @staticmethod
    def from_dict(d: dict) -> RectangleShape:
        return RectangleShape(
            id=d.get("id", uuid.uuid4().hex[:8]),
            left=d.get("left", 0),
            top=d.get("top", 0),
            width=d.get("width", 0),
            height=d.get("height", 0),
            z_order=d.get("z_order", 0),
            text=d.get("text", ""),
            font_size=d.get("font_size"),
            fill_color=d.get("fill_color"),
            text_color=d.get("text_color"),
        )


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


# ─────────────────────── Arrow ───────────────────────


@dataclass
class ArrowShape(AbstractShape):
    """An arrow between two points, optionally connected to box edges."""

    start_col: int = 0
    start_row: int = 0
    end_col: int = 0
    end_row: int = 0
    start_connection: Connection | None = None
    end_connection: Connection | None = None
    text: str = ""
    font_size: float | None = None  # None = use canvas default
    line_style: ArrowLineStyle = ArrowLineStyle.SOLID
    text_offset_col: int = 0
    text_offset_row: int = 0

    def __post_init__(self):
        self._update_bounds()

    def _update_bounds(self):
        self.left = min(self.start_col, self.end_col)
        self.top = min(self.start_row, self.end_row)
        self.width = abs(self.end_col - self.start_col) + 1
        self.height = abs(self.end_row - self.start_row) + 1

    def move(self, dcol: int, drow: int):
        # Only move endpoints that are NOT magnetically connected;
        # connected endpoints are repositioned by update_connections().
        if not self.start_connection:
            self.start_col += dcol
            self.start_row += drow
        if not self.end_connection:
            self.end_col += dcol
            self.end_row += drow
        self._update_bounds()

    def contains(self, col: int, row: int) -> bool:
        for pc, pr in self._compute_path():
            if abs(col - pc) + abs(row - pr) <= 1:
                return True
        return self.text_contains(col, row)

    def text_contains(self, col: int, row: int) -> bool:
        if self.text:
            path = self._compute_path()
            if path:
                mid = path[len(path) // 2]
                ox, oy = self.text_offset_col, self.text_offset_row
                lines = self.text.split("\n")
                for i, line in enumerate(lines):
                    if not line:
                        continue
                    h_offset = -(len(line) // 2)
                    text_row = mid[1] - len(lines) + i + oy
                    text_left = mid[0] + h_offset + ox
                    if row == text_row and text_left <= col < text_left + len(line):
                        return True
        return False

    def text_bounds(self) -> tuple[int, int, int, int] | None:
        if not self.text:
            return None
        path = self._compute_path()
        if not path:
            return None
        mid = path[len(path) // 2]
        ox, oy = self.text_offset_col, self.text_offset_row
        lines = self.text.split("\n")
        max_len = max(len(line) for line in lines) if lines else 0
        if max_len == 0:
            return None
        h_offset = -(max_len // 2)
        top_row = mid[1] - len(lines) + oy
        return (mid[0] + h_offset + ox, top_row, mid[0] + h_offset + max_len - 1 + ox, mid[1] - 1 + oy)

    def render_text(self, grid: dict[tuple[int, int], str]):
        if self.text and not self.font_size:
            path = self._compute_path()
            if not path:
                return
            mid = path[len(path) // 2]
            ox, oy = self.text_offset_col, self.text_offset_row
            lines = self.text.split("\n")
            num_lines = len(lines)
            for i, line in enumerate(lines):
                h_offset = -(len(line) // 2)
                for j, ch in enumerate(line):
                    grid[(mid[0] + h_offset + j + ox, mid[1] - num_lines + i + oy)] = ch

    def _compute_path(self) -> list[tuple[int, int]]:
        """Compute L-shaped path from start to end."""
        sc, sr = self.start_col, self.start_row
        ec, er = self.end_col, self.end_row
        points: list[tuple[int, int]] = []

        if sr == er:
            step = 1 if ec >= sc else -1
            for c in range(sc, ec + step, step):
                points.append((c, sr))
        elif sc == ec:
            step = 1 if er >= sr else -1
            for r in range(sr, er + step, step):
                points.append((sc, r))
        else:
            h_first = self._should_go_horizontal_first()
            if h_first:
                step_c = 1 if ec >= sc else -1
                for c in range(sc, ec + step_c, step_c):
                    points.append((c, sr))
                step_r = 1 if er >= sr else -1
                for r in range(sr + step_r, er + step_r, step_r):
                    points.append((ec, r))
            else:
                step_r = 1 if er >= sr else -1
                for r in range(sr, er + step_r, step_r):
                    points.append((sc, r))
                step_c = 1 if ec >= sc else -1
                for c in range(sc + step_c, ec + step_c, step_c):
                    points.append((c, er))
        return points

    def _should_go_horizontal_first(self) -> bool:
        # Prioritise end connection so the arrowhead direction matches the entry edge
        if self.end_connection and self.end_connection.edge in ("top", "bottom"):
            return True  # last segment vertical → arrowhead ▼/▲
        if self.end_connection and self.end_connection.edge in ("left", "right"):
            return False  # last segment horizontal → arrowhead ►/◄
        if self.start_connection and self.start_connection.edge in ("left", "right"):
            return True
        if self.start_connection and self.start_connection.edge in ("top", "bottom"):
            return False
        return True

    def render(self, grid: dict[tuple[int, int], str]):
        path = self._compute_path()
        if not path:
            return

        # Single-point path (boxes almost touching): draw just the arrowhead
        if len(path) == 1:
            pt = path[0]
            if self.end_connection:
                _INWARD = {"left": "►", "right": "◄", "top": "▼", "bottom": "▲"}
                grid[pt] = _INWARD.get(self.end_connection.edge, "►")
            else:
                grid[pt] = "►"
            return

        for i, (col, row) in enumerate(path):
            grid[(col, row)] = self._char_at(i, path)

        # Arrow head at end – always point into the connected shape
        last = path[-1]
        if self.end_connection:
            _INWARD_HEAD = {"left": "►", "right": "◄", "top": "▼", "bottom": "▲"}
            grid[last] = _INWARD_HEAD.get(self.end_connection.edge, "►")
        else:
            prev = path[-2]
            if last[0] > prev[0]:
                grid[last] = "►"
            elif last[0] < prev[0]:
                grid[last] = "◄"
            elif last[1] > prev[1]:
                grid[last] = "▼"
            elif last[1] < prev[1]:
                grid[last] = "▲"

    _EDGE_DIRECTION = {
        "right": (1, 0),
        "left": (-1, 0),
        "top": (0, -1),
        "bottom": (0, 1),
    }

    def _char_at(self, idx: int, path: list[tuple[int, int]]) -> str:
        col, row = path[idx]
        # Start point connected to a box edge: show corner if path turns
        if idx == 0 and self.start_connection and len(path) > 1:
            d_in = self._EDGE_DIRECTION.get(self.start_connection.edge)
            nxt = path[1]
            d_out = (nxt[0] - col, nxt[1] - row)
            if d_in and d_in != d_out:
                return CORNER_CHARS.get((d_in, d_out), "+")
        # Corner: direction changes
        if 0 < idx < len(path) - 1:
            prev = path[idx - 1]
            nxt = path[idx + 1]
            d_in = (col - prev[0], row - prev[1])
            d_out = (nxt[0] - col, nxt[1] - row)
            if d_in != d_out:
                return CORNER_CHARS.get((d_in, d_out), "+")
        # Determine if horizontal or vertical segment
        is_h = True
        if idx > 0:
            is_h = path[idx - 1][1] == row
        elif idx < len(path) - 1:
            is_h = path[idx + 1][1] == row
        # Apply line style
        if self.line_style == ArrowLineStyle.DASHED:
            if idx % 2 == 0:
                return "-" if is_h else ":"
            else:
                return " "
        elif self.line_style == ArrowLineStyle.DOTTED:
            if idx % 2 == 0:
                return "·" if is_h else "·"
            else:
                return " "
        return "─" if is_h else "│"

    def get_text_anchor(self) -> tuple[int, int]:
        """Midpoint of path for text placement, adjusted by text offset."""
        path = self._compute_path()
        if not path:
            return (self.start_col + self.text_offset_col, self.start_row + self.text_offset_row)
        mid = path[len(path) // 2]
        return (mid[0] + self.text_offset_col, mid[1] - 1 + self.text_offset_row)

    def update_from_connections(self, board: Board):
        """Recalculate endpoints from connected shapes, re-optimising edge & ratio.

        Pinned connections keep their stored edge & ratio — only coordinates are
        recomputed from the shape's current position.  Auto-optimisation via
        ``_best_edges_between`` is skipped when any connection is pinned.
        """
        start_box: AbstractShape | None = None
        end_box: AbstractShape | None = None

        if self.start_connection:
            s = board.get_shape(self.start_connection.shape_id)
            if s and not isinstance(s, ArrowShape):
                start_box = s
            else:
                self.start_connection = None

        if self.end_connection:
            s = board.get_shape(self.end_connection.shape_id)
            if s and not isinstance(s, ArrowShape):
                end_box = s
            else:
                self.end_connection = None

        if start_box and end_box:
            any_pinned = (self.start_connection and self.start_connection.pinned) or (
                self.end_connection and self.end_connection.pinned
            )
            if not any_pinned:
                # Full auto-optimisation
                a_edge, a_ratio, b_edge, b_ratio = _best_edges_between(start_box, end_box)
                self.start_connection.edge, self.start_connection.ratio = a_edge, a_ratio
                self.end_connection.edge, self.end_connection.ratio = b_edge, b_ratio
            # Recompute coordinates from (possibly pinned) edge & ratio
            self.start_col, self.start_row = start_box.edge_point_from_connection(
                self.start_connection.edge, self.start_connection.ratio
            )
            self.end_col, self.end_row = end_box.edge_point_from_connection(
                self.end_connection.edge, self.end_connection.ratio
            )
        elif start_box:
            # Preserve the stored edge — only reposition along the same edge
            ec, er = start_box.edge_point_from_connection(self.start_connection.edge, self.start_connection.ratio)
            self.start_col, self.start_row = ec, er
        elif end_box:
            # Preserve the stored edge — only reposition along the same edge
            ec, er = end_box.edge_point_from_connection(self.end_connection.edge, self.end_connection.ratio)
            self.end_col, self.end_row = ec, er

        self._update_bounds()

    def to_dict(self) -> dict:
        d: dict = {
            "type": "arrow",
            "id": self.id,
            "start_col": self.start_col,
            "start_row": self.start_row,
            "end_col": self.end_col,
            "end_row": self.end_row,
            "z_order": self.z_order,
            "text": self.text,
        }
        if self.font_size is not None:
            d["font_size"] = self.font_size
        if self.line_style != ArrowLineStyle.SOLID:
            d["line_style"] = self.line_style.value
        if self.start_connection:
            d["start_connection"] = self.start_connection.to_dict()
        if self.end_connection:
            d["end_connection"] = self.end_connection.to_dict()
        if self.fill_color:
            d["fill_color"] = self.fill_color
        if self.text_color:
            d["text_color"] = self.text_color
        if self.text_offset_col:
            d["text_offset_col"] = self.text_offset_col
        if self.text_offset_row:
            d["text_offset_row"] = self.text_offset_row
        return d

    @staticmethod
    def from_dict(d: dict) -> ArrowShape:
        sc = d.get("start_connection")
        ec = d.get("end_connection")
        ls_val = d.get("line_style", "solid")
        try:
            ls = ArrowLineStyle(ls_val)
        except ValueError:
            ls = ArrowLineStyle.SOLID
        return ArrowShape(
            id=d.get("id", uuid.uuid4().hex[:8]),
            start_col=d.get("start_col", 0),
            start_row=d.get("start_row", 0),
            end_col=d.get("end_col", 0),
            end_row=d.get("end_row", 0),
            z_order=d.get("z_order", 0),
            text=d.get("text", ""),
            font_size=d.get("font_size"),
            line_style=ls,
            start_connection=Connection.from_dict(sc) if sc else None,
            end_connection=Connection.from_dict(ec) if ec else None,
            fill_color=d.get("fill_color"),
            text_color=d.get("text_color"),
            text_offset_col=d.get("text_offset_col", 0),
            text_offset_row=d.get("text_offset_row", 0),
        )


# ─────────────────────── Actor ───────────────────────

# ASCII stick figure (5 cols wide, 6 rows tall):
#   O      <- head (row 0, col 2)
#  /|\     <- arms and torso (row 1, cols 1,2,3)
#   |      <- torso (row 2, col 2)
#  / \     <- legs (row 3, cols 1,3)
ACTOR_CHARS = [
    (2, 0, "O"),  # head
    (1, 1, "/"),  # left arm
    (2, 1, "|"),  # torso
    (3, 1, "\\"),  # right arm
    (2, 2, "|"),  # lower torso
    (1, 3, "/"),  # left leg
    (3, 3, "\\"),  # right leg
]
ACTOR_WIDTH = 5
ACTOR_HEIGHT = 4


@dataclass
class ActorShape(AbstractShape):
    """A stick figure actor for diagrams."""

    text: str = ""  # label below the actor

    def __post_init__(self):
        self.width = ACTOR_WIDTH
        self.height = ACTOR_HEIGHT + (2 if self.text else 0)

    def render(self, grid: dict[tuple[int, int], str]):
        for dc, dr, ch in ACTOR_CHARS:
            grid[(self.left + dc, self.top + dr)] = ch

    def render_text(self, grid: dict[tuple[int, int], str]):
        if self.text:
            text_row = self.top + ACTOR_HEIGHT
            text_start = self.left + (ACTOR_WIDTH - len(self.text)) // 2
            for i, ch in enumerate(self.text[: ACTOR_WIDTH + 4]):
                grid[(text_start + i, text_row)] = ch

    def contains(self, col: int, row: int) -> bool:
        # Hit test against the actor chars
        for dc, dr, _ in ACTOR_CHARS:
            if col == self.left + dc and row == self.top + dr:
                return True
        return False

    def to_dict(self) -> dict:
        d = {
            "type": "actor",
            "id": self.id,
            "left": self.left,
            "top": self.top,
            "z_order": self.z_order,
            "text": self.text,
        }
        if self.fill_color:
            d["fill_color"] = self.fill_color
        if self.text_color:
            d["text_color"] = self.text_color
        return d

    @staticmethod
    def from_dict(d: dict) -> ActorShape:
        return ActorShape(
            id=d.get("id", uuid.uuid4().hex[:8]),
            left=d.get("left", 0),
            top=d.get("top", 0),
            z_order=d.get("z_order", 0),
            text=d.get("text", ""),
            fill_color=d.get("fill_color"),
            text_color=d.get("text_color"),
        )


# ─────────────────────── Topic ───────────────────────

# Topic shape - a box with two vertical dividers:
# ┌─┬────────────────┬─┐
# │ │                │ │
# │ │                │ │
# └─┴────────────────┴─┘
TOPIC_MIN_WIDTH = 8
TOPIC_MIN_HEIGHT = 3


@dataclass
class TopicShape(AbstractShape):
    """A topic box with two vertical dividers near edges."""

    text: str = ""
    font_size: float | None = None

    def render(self, grid: dict[tuple[int, int], str]):
        w, h = self.width, self.height
        left_div = 2  # position of left divider
        right_div = w - 3  # position of right divider

        # Top row
        grid[(self.left, self.top)] = "┌"
        grid[(self.left + w - 1, self.top)] = "┐"
        grid[(self.left + left_div, self.top)] = "┬"
        grid[(self.left + right_div, self.top)] = "┬"
        for c in range(1, w - 1):
            if c != left_div and c != right_div:
                grid[(self.left + c, self.top)] = "─"

        # Bottom row
        grid[(self.left, self.top + h - 1)] = "└"
        grid[(self.left + w - 1, self.top + h - 1)] = "┘"
        grid[(self.left + left_div, self.top + h - 1)] = "┴"
        grid[(self.left + right_div, self.top + h - 1)] = "┴"
        for c in range(1, w - 1):
            if c != left_div and c != right_div:
                grid[(self.left + c, self.top + h - 1)] = "─"

        # Vertical sides and dividers
        for r in range(1, h - 1):
            grid[(self.left, self.top + r)] = "│"
            grid[(self.left + w - 1, self.top + r)] = "│"
            grid[(self.left + left_div, self.top + r)] = "│"
            grid[(self.left + right_div, self.top + r)] = "│"

    def render_text(self, grid: dict[tuple[int, int], str]):
        if self.text and not self.font_size:
            w = self.width
            left_div = 2
            right_div = w - 3
            text_col = self.left + left_div + 1 + (right_div - left_div - 1 - len(self.text)) // 2
            text_row = self.top + self.height // 2
            for i, ch in enumerate(self.text[: right_div - left_div - 1]):
                grid[(text_col + i, text_row)] = ch

    def contains(self, col: int, row: int) -> bool:
        return self.left <= col < self.left + self.width and self.top <= row < self.top + self.height

    def get_interior_bounds(self) -> tuple[int, int, int, int] | None:
        """Return (left, top, right, bottom) of the text area between dividers."""
        left_div = 2
        right_div = self.width - 3
        if right_div - left_div <= 1:
            return None
        return (self.left + left_div + 1, self.top + 1, self.left + right_div - 1, self.top + self.height - 2)

    def _render_text(self, grid: dict[tuple[int, int], str]):
        """Render text into the interior area (used by _render_font_size_texts)."""
        interior = self.get_interior_bounds()
        if not interior or not self.text:
            return
        il, it, ir, ib = interior
        iw = ir - il + 1
        ih = ib - it + 1
        lines = self.text.split("\n")
        v_offset = max(0, (ih - len(lines)) // 2)
        for i, line in enumerate(lines[:ih]):
            row = it + v_offset + i
            h_offset = max(0, (iw - len(line)) // 2)
            for j, ch in enumerate(line[:iw]):
                grid[(il + h_offset + j, row)] = ch

    def to_dict(self) -> dict:
        d = {
            "type": "topic",
            "id": self.id,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "z_order": self.z_order,
            "text": self.text,
        }
        if self.font_size is not None:
            d["font_size"] = self.font_size
        if self.fill_color:
            d["fill_color"] = self.fill_color
        if self.text_color:
            d["text_color"] = self.text_color
        return d

    @staticmethod
    def from_dict(d: dict) -> "TopicShape":
        return TopicShape(
            id=d.get("id", uuid.uuid4().hex[:8]),
            left=d.get("left", 0),
            top=d.get("top", 0),
            width=d.get("width", TOPIC_MIN_WIDTH),
            height=d.get("height", TOPIC_MIN_HEIGHT),
            z_order=d.get("z_order", 0),
            text=d.get("text", ""),
            font_size=d.get("font_size"),
            fill_color=d.get("fill_color"),
            text_color=d.get("text_color"),
        )


# ─────────────────────── Database ───────────────────────

# Database cylinder:
#  ╭─────╮
#  ├─────┤
#  │     │
#  │     │
#  ╰─────╯
DATABASE_DEFAULT_WIDTH = 7
DATABASE_DEFAULT_HEIGHT = 5
DATABASE_MIN_WIDTH = 5
DATABASE_MIN_HEIGHT = 4


@dataclass
class DatabaseShape(AbstractShape):
    """A database cylinder shape with a separator line."""

    text: str = ""
    font_size: float | None = None

    def __post_init__(self):
        if self.width < DATABASE_MIN_WIDTH:
            self.width = DATABASE_DEFAULT_WIDTH
        if self.height < DATABASE_MIN_HEIGHT:
            self.height = DATABASE_DEFAULT_HEIGHT

    def render(self, grid: dict[tuple[int, int], str]):
        w, h = self.width, self.height

        # Top edge (rounded)
        grid[(self.left, self.top)] = "╭"
        grid[(self.left + w - 1, self.top)] = "╮"
        for c in range(1, w - 1):
            grid[(self.left + c, self.top)] = "─"

        # Separator line (row 1) — gives the cylinder "disk" look
        grid[(self.left, self.top + 1)] = "├"
        grid[(self.left + w - 1, self.top + 1)] = "┤"
        for c in range(1, w - 1):
            grid[(self.left + c, self.top + 1)] = "─"

        # Body (vertical sides)
        for r in range(2, h - 1):
            grid[(self.left, self.top + r)] = "│"
            grid[(self.left + w - 1, self.top + r)] = "│"

        # Fill interior with spaces to mask shapes behind in z-order
        for r in range(2, h - 1):
            for c in range(1, w - 1):
                grid[(self.left + c, self.top + r)] = " "

        # Bottom edge (rounded)
        grid[(self.left, self.top + h - 1)] = "╰"
        grid[(self.left + w - 1, self.top + h - 1)] = "╯"
        for c in range(1, w - 1):
            grid[(self.left + c, self.top + h - 1)] = "─"

    def render_text(self, grid: dict[tuple[int, int], str]):
        if self.text and not self.font_size:
            self._render_text(grid)

    def _render_text(self, grid: dict[tuple[int, int], str]):
        """Render text centered in the body area (below separator)."""
        interior = self.get_interior_bounds()
        if not interior:
            return
        inner_left, inner_top, inner_right, inner_bottom = interior
        inner_w = inner_right - inner_left + 1
        inner_h = inner_bottom - inner_top + 1
        if inner_w <= 0 or inner_h <= 0:
            return
        wrapped: list[str] = []
        for line in self.text.split("\n"):
            if len(line) <= inner_w:
                wrapped.append(line)
            else:
                _word_wrap_into(line, inner_w, wrapped)
        v_offset = max(0, (inner_h - len(wrapped)) // 2)
        for i, line in enumerate(wrapped):
            row = inner_top + v_offset + i
            if row > inner_bottom:
                break
            text = line[:inner_w]
            h_offset = max(0, (inner_w - len(text)) // 2)
            for j, ch in enumerate(text):
                grid[(inner_left + h_offset + j, row)] = ch

    def get_interior_bounds(self) -> tuple[int, int, int, int] | None:
        """Return (left, top, right, bottom) of body interior (below separator)."""
        # Body is between separator (row +1) and bottom border
        inner_w = self.width - 2
        inner_h = self.height - 3  # rows between separator and bottom
        if inner_w <= 0 or inner_h <= 0:
            return None
        return (self.left + 1, self.top + 2, self.left + self.width - 2, self.top + self.height - 2)

    def min_size_for_text(self) -> tuple[int, int]:
        """Return minimum (width, height) to contain the current text."""
        if not self.text:
            return (DATABASE_MIN_WIDTH, DATABASE_MIN_HEIGHT)
        lines = self.text.split("\n")
        max_line_len = max((len(l) for l in lines), default=0)
        return (max(DATABASE_MIN_WIDTH, max_line_len + 2), max(DATABASE_MIN_HEIGHT, len(lines) + 3))

    def contains(self, col: int, row: int) -> bool:
        return self.left <= col < self.left + self.width and self.top <= row < self.top + self.height

    def to_dict(self) -> dict:
        d = {
            "type": "database",
            "id": self.id,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "z_order": self.z_order,
            "text": self.text,
        }
        if self.font_size is not None:
            d["font_size"] = self.font_size
        if self.fill_color:
            d["fill_color"] = self.fill_color
        if self.text_color:
            d["text_color"] = self.text_color
        return d

    @staticmethod
    def from_dict(d: dict) -> "DatabaseShape":
        return DatabaseShape(
            id=d.get("id", uuid.uuid4().hex[:8]),
            left=d.get("left", 0),
            top=d.get("top", 0),
            width=d.get("width", 0),
            height=d.get("height", 0),
            z_order=d.get("z_order", 0),
            text=d.get("text", ""),
            font_size=d.get("font_size"),
            fill_color=d.get("fill_color"),
            text_color=d.get("text_color"),
        )


# ─────────────────────── Cloud ───────────────────────

# Cloud shape:
#  _________________
# (                 )
# (                 )
# (_________________)
CLOUD_MIN_WIDTH = 8
CLOUD_MIN_HEIGHT = 3


@dataclass
class CloudShape(AbstractShape):
    """A cloud shape for diagrams."""

    text: str = ""
    font_size: float | None = None

    def render(self, grid: dict[tuple[int, int], str]):
        l, t = self.left, self.top
        r, b = self.right, self.bottom

        # Top row:  _________________
        grid[(l, t)] = " "
        for c in range(l + 1, r + 1):
            grid[(c, t)] = "_"

        # Body rows: (                )
        for row in range(t + 1, b):
            grid[(l, row)] = "("
            for c in range(l + 1, r):
                grid[(c, row)] = " "
            grid[(r, row)] = ")"

        # Bottom row: (________________)
        grid[(l, b)] = "("
        for c in range(l + 1, r):
            grid[(c, b)] = "_"
        grid[(r, b)] = ")"

    def render_text(self, grid: dict[tuple[int, int], str]):
        if self.text and not self.font_size:
            self._render_text(grid)

    def _render_text(self, grid: dict[tuple[int, int], str]):
        interior = self.get_interior_bounds()
        if not interior:
            return
        il, it, ir, ib = interior
        iw = ir - il + 1
        ih = ib - it + 1
        if iw <= 0 or ih <= 0:
            return
        wrapped: list[str] = []
        for line in self.text.split("\n"):
            if len(line) <= iw:
                wrapped.append(line)
            else:
                _word_wrap_into(line, iw, wrapped)
        v_offset = max(0, (ih - len(wrapped)) // 2)
        for i, line in enumerate(wrapped):
            row = it + v_offset + i
            if row > ib:
                break
            text = line[:iw]
            h_offset = max(0, (iw - len(text)) // 2)
            for j, ch in enumerate(text):
                grid[(il + h_offset + j, row)] = ch

    def get_interior_bounds(self) -> tuple[int, int, int, int] | None:
        inner_l = self.left + 1
        inner_r = self.right - 1
        inner_t = self.top + 1
        inner_b = self.bottom - 1
        if inner_r < inner_l or inner_b < inner_t:
            return None
        return (inner_l, inner_t, inner_r, inner_b)

    def min_size_for_text(self) -> tuple[int, int]:
        if not self.text:
            return (CLOUD_MIN_WIDTH, CLOUD_MIN_HEIGHT)
        lines = self.text.split("\n")
        max_line_len = max((len(l) for l in lines), default=0)
        return (max(CLOUD_MIN_WIDTH, max_line_len + 4), max(CLOUD_MIN_HEIGHT, len(lines) + 2))

    def to_dict(self) -> dict:
        d = {
            "type": "cloud",
            "id": self.id,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "z_order": self.z_order,
            "text": self.text,
        }
        if self.font_size is not None:
            d["font_size"] = self.font_size
        if self.fill_color:
            d["fill_color"] = self.fill_color
        if self.text_color:
            d["text_color"] = self.text_color
        return d

    @staticmethod
    def from_dict(d: dict) -> "CloudShape":
        return CloudShape(
            id=d.get("id", uuid.uuid4().hex[:8]),
            left=d.get("left", 0),
            top=d.get("top", 0),
            width=d.get("width", CLOUD_MIN_WIDTH),
            height=d.get("height", CLOUD_MIN_HEIGHT),
            z_order=d.get("z_order", 0),
            text=d.get("text", ""),
            font_size=d.get("font_size"),
            fill_color=d.get("fill_color"),
            text_color=d.get("text_color"),
        )


def _render_font_size_texts(shapes, grid: dict[tuple[int, int], str]):
    """Render text into grid for shapes with custom font_size (skipped by render())."""
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
        for shape in self.shapes.values():
            if isinstance(shape, ArrowShape):
                shape.update_from_connections(self)

    def snap_to_edge(self, col: int, row: int, exclude_id: str | None = None) -> tuple[Connection, int, int] | None:
        """Find nearest shape edge within SNAP_DISTANCE. Returns (Connection, col, row) or None."""
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
