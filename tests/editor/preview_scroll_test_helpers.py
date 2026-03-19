"""Shared test helpers for preview/editor scroll synchronization tests."""

from editor.preview.content_block import ContentBlock
from editor.preview.markdown_canvas import _estimate_block_lines


class FakeAdjustment:
    """Minimal Gtk.Adjustment stand-in for unit tests."""

    def __init__(self, value=0.0, upper=1000.0, page_size=200.0):
        self._value = value
        self._upper = upper
        self._page_size = page_size
        self._value_changed_callbacks = []
        self._cbs = self._value_changed_callbacks

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        for callback in self._value_changed_callbacks:
            callback(self)

    def get_upper(self):
        return self._upper

    def get_page_size(self):
        return self._page_size

    def connect(self, signal, callback):
        if signal == "value-changed":
            self._value_changed_callbacks.append(callback)
        return len(self._value_changed_callbacks)


def make_blocks(specs: list[tuple[int, float, float]]) -> list[ContentBlock]:
    """Create ContentBlock list with source_line, _y_offset, _height."""
    blocks = []
    for source_line, y_offset, height in specs:
        block = ContentBlock(kind="paragraph", source_line=source_line)
        block._y_offset = y_offset
        block._height = height
        blocks.append(block)
    return blocks


def get_y_for_source_line(blocks, source_line):
    """Pure-Python replica of MarkdownCanvas.get_y_for_source_line."""
    if not blocks:
        return 0.0
    best_idx = 0
    for i, block in enumerate(blocks):
        if block.source_line <= source_line:
            best_idx = i
        else:
            break
    block = blocks[best_idx]
    if best_idx + 1 < len(blocks):
        next_line = blocks[best_idx + 1].source_line
    else:
        next_line = block.source_line + _estimate_block_lines(block)
    span = max(next_line - block.source_line, 1)
    frac = (source_line - block.source_line) / span
    return block._y_offset + frac * block._height


def smooth_scroll_tick(adj, smooth_target_y, lerp_factor=0.25):
    """Pure-Python replica of smooth scroll tick logic."""
    if adj is None or smooth_target_y is None:
        return False, None, None, False

    current = adj.get_value()
    target = smooth_target_y
    diff = target - current

    if abs(diff) < 1.0:
        adj.set_value(target)
        return False, target, None, True

    new_val = current + diff * lerp_factor
    adj.set_value(new_val)
    return True, new_val, smooth_target_y, True


def on_canvas_scroll_fraction(adj, syncing_scroll, animation_adjusting, callback=None):
    """Replicate preview _on_canvas_scroll logic in pure Python."""
    if syncing_scroll or animation_adjusting:
        return None, False
    upper = adj.get_upper()
    page = adj.get_page_size()
    if upper > page:
        fraction = adj.get_value() / (upper - page)
    else:
        fraction = 0.0
    if callback:
        callback(fraction)
    return fraction, True
