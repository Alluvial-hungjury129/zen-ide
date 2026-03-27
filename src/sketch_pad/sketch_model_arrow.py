"""
Sketch Pad data model – ArrowShape and arrow routing helpers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

# Re-export routing helpers so they remain importable from this module
from sketch_pad._arrow_routing import (  # noqa: F401
    _best_edges_between,
    _clamp_edge_ratio_h,
    _clamp_edge_ratio_v,
    _compute_diagonal_edges,
    _compute_h_edges,
    _compute_v_edges,
    _edges_are_degenerate,
    _mixed_ratios,
    _pick_barely_degenerate,
    _point_in_box,
    _rate_candidate,
    _would_uturn,
)
from sketch_pad.sketch_model_base import CORNER_CHARS, AbstractShape, ArrowLineStyle
from sketch_pad.sketch_model_connection import Connection

# ─────────────────────── Arrow Shape ───────────────────────


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

    def update_from_connections(self, board):
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
