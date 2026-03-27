"""
Sketch Pad data model – ActorShape, TopicShape, DatabaseShape, CloudShape.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sketch_pad.sketch_model_base import AbstractShape
from sketch_pad.sketch_model_rectangle import _word_wrap_into

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
