"""
Arrow routing helpers – edge selection and path optimisation.

Internal module used by sketch_model_arrow.
"""

from __future__ import annotations

from sketch_pad.sketch_model_base import AbstractShape


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
    diagonal), try cross-orientation pairs like top->left or right->bottom.
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
