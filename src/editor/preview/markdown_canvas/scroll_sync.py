"""Scroll-sync mapping mixin for MarkdownCanvas.

Provides source-line <-> scroll-position mapping and smooth scroll animation.
"""

from __future__ import annotations


def _estimate_block_lines(block) -> int:
    """Estimate how many source lines a block spans."""
    if block.kind == "code":
        return max(len(block.code.split("\n")), 1) + 2  # +2 for fences
    if block.kind == "table":
        return 2 + len(block.rows)  # header + separator + rows
    return 1


class ScrollSyncMixin:
    """Mixin providing scroll-sync mapping between editor lines and preview position."""

    def get_block_at_y(self, y: float):
        """Return the block at the given Y coordinate (for scroll sync)."""
        for block in self._blocks:
            if block._y_offset <= y < block._y_offset + block._height:
                return block
        return self._blocks[-1] if self._blocks else None

    def get_y_for_source_line(self, source_line: int) -> float:
        """Return the Y offset for a given source line (for editor->preview sync).

        Interpolates within blocks so that scrolling through a large block
        produces proportional movement in the preview rather than snapping
        to block boundaries.
        """
        if not self._blocks:
            return 0.0

        # Find the block that contains this source line
        best_idx = 0
        for i, block in enumerate(self._blocks):
            if block.source_line <= source_line:
                best_idx = i
            else:
                break

        block = self._blocks[best_idx]

        # Calculate line span: how many source lines this block covers
        if best_idx + 1 < len(self._blocks):
            next_line = self._blocks[best_idx + 1].source_line
        else:
            # Last block -- estimate span from content lines
            next_line = block.source_line + _estimate_block_lines(block)

        span = max(next_line - block.source_line, 1)
        frac = (source_line - block.source_line) / span

        return block._y_offset + frac * block._height

    def scroll_to_source_line(self, source_line: int):
        """Scroll the preview to show the block for the given editor line.

        Uses smooth exponential interpolation (lerp) so the preview glides
        to the target position instead of jumping between block boundaries.
        """
        y = self.get_y_for_source_line(source_line)
        self._smooth_scroll_to(y)

    def scroll_to_value(self, value: float):
        """Set scroll position with smooth interpolation (editor->preview sync)."""
        self._smooth_scroll_to(value)

    def _smooth_scroll_to(self, target_y: float):
        """Start or update smooth scroll animation toward target_y."""
        vadj = self._get_vadjustment()
        if not vadj:
            return
        upper = vadj.get_upper()
        page = vadj.get_page_size()
        max_val = max(0.0, upper - page)
        self._smooth_target_y = max(0.0, min(target_y, max_val))

        if not self._smooth_tick_id:
            self._smooth_tick_id = self.add_tick_callback(self._smooth_scroll_tick)

    def _smooth_scroll_tick(self, widget, frame_clock):
        """Frame-clock tick callback: lerp toward target each frame."""
        vadj = self._get_vadjustment()
        if vadj is None or self._smooth_target_y is None:
            self._smooth_tick_id = 0
            return False  # remove callback

        current = vadj.get_value()
        target = self._smooth_target_y
        diff = target - current

        if abs(diff) < 1.0:
            self._animation_adjusting = True
            vadj.set_value(target)
            self._animation_adjusting = False
            self._smooth_target_y = None
            self._smooth_tick_id = 0
            return False  # remove callback

        self._animation_adjusting = True
        vadj.set_value(current + diff * self._LERP_FACTOR)
        self._animation_adjusting = False
        return True  # keep ticking

    def _set_scroll_value(self, target_y: float):
        """Clamp and apply a scroll Y value immediately (no animation)."""
        vadj = self._get_vadjustment()
        if not vadj:
            return
        upper = vadj.get_upper()
        page = vadj.get_page_size()
        max_val = max(0.0, upper - page)
        vadj.set_value(max(0.0, min(target_y, max_val)))

    def get_source_line_at_scroll(self) -> int:
        """Return the interpolated source line at the current scroll position.

        Uses the same proportional mapping as get_y_for_source_line so the
        forward and reverse mappings are consistent.
        """
        if not self._blocks:
            return 0
        scroll_y = self._get_scroll_y() + self.PAD_TOP
        block = self.get_block_at_y(scroll_y)
        if not block:
            return 0

        # Find block index for span calculation
        idx = 0
        for i, b in enumerate(self._blocks):
            if b is block:
                idx = i
                break

        if idx + 1 < len(self._blocks):
            next_line = self._blocks[idx + 1].source_line
        else:
            next_line = block.source_line + _estimate_block_lines(block)

        span = max(next_line - block.source_line, 1)

        # Interpolate within block
        if block._height > 0:
            frac = max(0.0, min(1.0, (scroll_y - block._y_offset) / block._height))
        else:
            frac = 0.0

        return block.source_line + int(frac * span)
