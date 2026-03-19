from ai.chat_canvas import ChatCanvas


class FakeAdjustment:
    def __init__(self):
        self._handlers = {}
        self._next_handler_id = 1
        self.disconnected = []

    def connect(self, signal_name, callback):
        handler_id = self._next_handler_id
        self._next_handler_id += 1
        self._handlers[handler_id] = (signal_name, callback)
        return handler_id

    def disconnect(self, handler_id):
        self.disconnected.append(handler_id)
        self._handlers.pop(handler_id, None)

    def emit_value_changed(self):
        for signal_name, callback in list(self._handlers.values()):
            if signal_name == "value-changed":
                callback(self)


class FakeScrolledWindow:
    def __init__(self, vadjustment, width=0):
        self._vadjustment = vadjustment
        self._width = width
        self._handlers = {}

    def connect(self, signal_name, callback):
        self._handlers[signal_name] = callback
        return len(self._handlers)

    def get_vadjustment(self):
        return self._vadjustment

    def set_vadjustment(self, vadjustment):
        self._vadjustment = vadjustment

    def emit_notify_vadjustment(self):
        self._handlers["notify::vadjustment"](self, None)

    def get_width(self):
        return self._width


class FixedWidthChatCanvas(ChatCanvas):
    def __init__(self, width):
        super().__init__()
        self._width = width

    def get_width(self):
        return self._width


class SpyChatCanvas(ChatCanvas):
    def __init__(self):
        super().__init__()
        self.draw_calls = 0

    def queue_draw(self):
        self.draw_calls += 1

    def _schedule_redraw(self):
        # In tests there is no GLib main loop, so treat a scheduled
        # redraw the same as a synchronous queue_draw for counting.
        self.draw_calls += 1


def test_attach_to_scrolled_window_redraws_on_scroll():
    adjustment = FakeAdjustment()
    scrolled = FakeScrolledWindow(adjustment)
    canvas = SpyChatCanvas()

    canvas.attach_to_scrolled_window(scrolled)
    adjustment.emit_value_changed()

    assert canvas.draw_calls == 1


def test_attach_to_scrolled_window_reconnects_when_adjustment_changes():
    old_adjustment = FakeAdjustment()
    new_adjustment = FakeAdjustment()
    scrolled = FakeScrolledWindow(old_adjustment)
    canvas = SpyChatCanvas()

    canvas.attach_to_scrolled_window(scrolled)
    scrolled.set_vadjustment(new_adjustment)
    scrolled.emit_notify_vadjustment()
    old_adjustment.emit_value_changed()
    new_adjustment.emit_value_changed()

    assert old_adjustment.disconnected == [1, 2]
    assert canvas.draw_calls == 1


def test_pixel_to_pos_uses_canvas_coordinates_after_scroll():
    canvas = ChatCanvas()
    canvas._line_height = 20
    canvas._char_width = 10
    canvas._buffer.feed("line0\nline1\nline2\nline3\nline4\nline5")

    # Event coordinates from Gtk gestures are already in content coordinates.
    # A scroll offset must not be added a second time.
    canvas._get_scroll_y = lambda: 120

    assert canvas._pixel_to_pos(24, 82) == (4, 2)


def test_get_column_count_prefers_scrolled_viewport_width():
    """Column count uses the DrawingArea's own width (the actual rendering area)."""
    canvas = FixedWidthChatCanvas(width=800)
    canvas._char_width = 5
    canvas._measured = True

    adjustment = FakeAdjustment()
    scrolled = FakeScrolledWindow(adjustment, width=200)
    canvas.attach_to_scrolled_window(scrolled)
    canvas.get_parent = lambda: scrolled

    # DrawingArea width (800) is used: (800 - 16) / 5 = 156
    assert canvas.get_column_count() == 156


def test_get_column_count_falls_back_to_scrolled_window():
    """When DrawingArea width is 0 (before allocation), falls back to ScrolledWindow."""
    canvas = FixedWidthChatCanvas(width=0)
    canvas._char_width = 5
    canvas._measured = True

    adjustment = FakeAdjustment()
    scrolled = FakeScrolledWindow(adjustment, width=200)
    canvas.attach_to_scrolled_window(scrolled)

    # ScrolledWindow width (200) is used: (200 - 16) / 5 = 36
    assert canvas.get_column_count() == 36


class ScrollableAdjustment:
    """Fake GtkAdjustment with value/upper/page_size tracking."""

    def __init__(self, value=0.0, upper=1000.0, page_size=300.0):
        self.value = value
        self.upper = upper
        self.page_size = page_size
        self._handlers = {}
        self._next_id = 1

    def get_value(self):
        return self.value

    def set_value(self, v):
        self.value = v

    def get_upper(self):
        return self.upper

    def set_upper(self, u):
        self.upper = u

    def get_page_size(self):
        return self.page_size

    def connect(self, signal_name, callback):
        hid = self._next_id
        self._next_id += 1
        self._handlers[hid] = (signal_name, callback)
        return hid

    def disconnect(self, hid):
        self._handlers.pop(hid, None)


class TestResizeAnchor:
    """Test live-resize scroll anchor capture/restore in ChatCanvas."""

    def _make_canvas(self, lines, width, scroll_value=0.0, page_size=300.0):
        """Create a ChatCanvas with content and a scrollable adjustment."""
        canvas = FixedWidthChatCanvas(width=width)
        canvas._line_height = 20
        canvas._char_width = 8.0
        canvas._measured = True
        for line in lines:
            canvas._buffer.feed(line + "\n")
        canvas._rebuild_wrap_map(width)
        canvas._update_content_height()
        upper = canvas._total_visual_rows * canvas._line_height + canvas.PAD_TOP * 2
        adj = ScrollableAdjustment(value=scroll_value, upper=upper, page_size=page_size)
        canvas._vadjustment = adj
        canvas._scrolled_window = type("SW", (), {"get_vadjustment": lambda self: adj})()
        # Override _get_scroll_y to use our fake adjustment
        canvas._get_scroll_y = lambda: adj.get_value()
        return canvas, adj

    def test_capture_returns_none_without_adjustment(self):
        canvas = ChatCanvas()
        canvas._vadjustment = None
        assert canvas._capture_resize_anchor() is None

    def test_capture_detects_bottom(self):
        lines = [f"line {i}" for i in range(50)]
        canvas, adj = self._make_canvas(lines, width=600)
        # Scroll to bottom
        max_val = max(adj.upper - adj.page_size, 0)
        adj.set_value(max_val)
        anchor = canvas._capture_resize_anchor()
        assert anchor is not None
        assert anchor["at_bottom"] is True

    def test_capture_detects_middle(self):
        lines = [f"line {i}" for i in range(50)]
        canvas, adj = self._make_canvas(lines, width=600, scroll_value=200.0)
        anchor = canvas._capture_resize_anchor()
        assert anchor is not None
        assert anchor["at_bottom"] is False
        assert anchor["anchor_line"] >= 0

    def test_resize_anchor_persists_across_frames(self):
        """_resize_scroll_anchor persists — not cleared every frame."""
        lines = [f"line {i}" for i in range(50)]
        canvas, adj = self._make_canvas(lines, width=600, scroll_value=200.0)
        anchor = canvas._capture_resize_anchor()
        canvas._resize_scroll_anchor = anchor

        # Simulate second frame: anchor should still be there
        assert canvas._resize_scroll_anchor is anchor
        assert canvas._resize_scroll_anchor["anchor_line"] == anchor["anchor_line"]

    def test_settle_clears_anchor_and_sets_vadjustment(self):
        """_settle_resize_scroll sets vadjustment and clears anchor."""
        lines = [f"line {i}" for i in range(50)]
        canvas, adj = self._make_canvas(lines, width=600, scroll_value=200.0)
        anchor = canvas._capture_resize_anchor()
        canvas._resize_scroll_anchor = anchor

        # Simulate layout having settled: upper is accurate
        _, content_height = canvas.get_size_request()
        adj.upper = float(content_height)

        canvas._settle_resize_scroll()

        assert canvas._resize_scroll_anchor is None
        # vadjustment should be at the correct target
        expected = canvas._line_visual_y(anchor["anchor_line"]) + anchor["anchor_offset"]
        max_val = max(adj.upper - adj.page_size, 0)
        expected = min(expected, max_val)
        assert abs(adj.value - expected) < 1.0

    def test_settle_bottom(self):
        """Bottom-anchored settle scrolls to the new bottom."""
        lines = [f"line {i}" for i in range(50)]
        canvas, adj = self._make_canvas(lines, width=600)
        max_val = max(adj.upper - adj.page_size, 0)
        adj.set_value(max_val)
        anchor = canvas._capture_resize_anchor()

        # Simulate content getting taller
        adj.upper = 1500.0
        adj.set_value(0)
        canvas._resize_scroll_anchor = anchor

        canvas._settle_resize_scroll()

        assert canvas._resize_scroll_anchor is None
        assert adj.value == max(adj.upper - adj.page_size, 0)

    def test_settle_noop_without_adjustment(self):
        canvas = ChatCanvas()
        canvas._vadjustment = None
        canvas._resize_scroll_anchor = {"anchor_line": 0, "anchor_offset": 0, "at_bottom": False}
        # Should not raise, and should clear the anchor
        canvas._settle_resize_scroll()
        assert canvas._resize_scroll_anchor is None

    def test_anchor_survives_width_change(self):
        """After width change, anchor line maps to the correct new Y position."""
        lines = ["x" * 100] * 10 + ["short"] * 40  # First 10 lines will wrap
        canvas, adj = self._make_canvas(lines, width=600, scroll_value=300.0)
        anchor = canvas._capture_resize_anchor()
        anchor_line = anchor["anchor_line"]
        canvas._resize_scroll_anchor = anchor

        # Rebuild at a narrower width (more wrapping → taller content)
        canvas._width = 400
        canvas._rebuild_wrap_map(400)
        canvas._update_content_height()
        _, content_height = canvas.get_size_request()
        adj.upper = float(content_height)

        # Settle
        canvas._settle_resize_scroll()

        # The scroll should land on the same buffer line
        expected_y = canvas._line_visual_y(anchor_line) + anchor["anchor_offset"]
        max_val = max(adj.upper - adj.page_size, 0)
        expected_y = min(expected_y, max_val)
        assert abs(adj.value - expected_y) < 1.0

    def test_get_scroll_anchor_returns_stored_anchor_during_resize(self):
        """When resize anchor is active, get_scroll_anchor returns it."""
        lines = [f"line {i}" for i in range(50)]
        canvas, adj = self._make_canvas(lines, width=600, scroll_value=200.0)

        canvas._resize_scroll_anchor = {
            "anchor_line": 15,
            "anchor_offset": 7.5,
            "at_bottom": False,
        }

        line, offset = canvas.get_scroll_anchor()
        assert line == 15
        assert abs(offset - 7.5) < 0.1

    def test_value_changed_suppressed_during_resize(self):
        """value-changed should not trigger queue_draw during active resize."""
        canvas = SpyChatCanvas()
        canvas._resize_scroll_anchor = {"anchor_line": 0, "anchor_offset": 0, "at_bottom": False}
        canvas.draw_calls = 0

        # Simulate value-changed
        canvas._on_scroll_value_changed(None)

        assert canvas.draw_calls == 0

    def test_value_changed_works_normally_without_resize(self):
        """value-changed triggers queue_draw when not resizing."""
        canvas = SpyChatCanvas()
        canvas._resize_scroll_anchor = None
        canvas.draw_calls = 0

        canvas._on_scroll_value_changed(None)

        assert canvas.draw_calls == 1
