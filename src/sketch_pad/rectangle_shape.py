"""
Sketch Pad data model – RectangleShape.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sketch_pad.abstract_shape import BORDER, AbstractShape

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
