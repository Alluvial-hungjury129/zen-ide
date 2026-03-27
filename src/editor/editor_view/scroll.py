"""Scroll behaviour, smooth scrolling, and go-to-line for EditorView."""

from gi.repository import GLib

from .core import _iter_at_line


class EditorViewScrollMixin:
    """Mixin providing scroll and go-to-line methods for EditorView."""

    def _go_to_line(self, tab, line_number: int):
        """Go to a specific line in the editor."""
        line_iter = _iter_at_line(tab.buffer, line_number - 1)
        tab.buffer.place_cursor(line_iter)
        tab.view.scroll_to_iter(line_iter, 0.2, False, 0.0, 0.5)

    def go_to_line_smooth(self, line_number: int, duration_ms: int = 300):
        """Scroll the current tab to a line with smooth animation."""
        tab = self._get_current_tab()
        if not tab:
            return
        target_iter = _iter_at_line(tab.buffer, line_number - 1)
        tab.buffer.place_cursor(target_iter)
        vadj = tab.view.get_vadjustment()
        if not vadj:
            self._go_to_line(tab, line_number)
            return
        start_val = vadj.get_value()
        # Compute target scroll position from iter Y coordinate
        iter_loc = tab.view.get_iter_location(target_iter)
        page_size = vadj.get_page_size()
        # Center the target line in viewport
        end_val = iter_loc.y - page_size / 2 + iter_loc.height / 2
        end_val = max(0, min(end_val, vadj.get_upper() - page_size))
        if abs(end_val - start_val) < 1:
            return
        self._animate_editor_scroll(vadj, start_val, end_val, duration_ms)

    def _animate_editor_scroll(self, vadj, start_val: float, end_val: float, duration_ms: int):
        """Animate scroll from start_val to end_val."""
        import time

        start_time = time.monotonic()

        def step():
            elapsed = (time.monotonic() - start_time) * 1000
            t = min(elapsed / duration_ms, 1.0)
            # Ease-out cubic
            t = 1 - (1 - t) ** 3
            vadj.set_value(start_val + (end_val - start_val) * t)
            if t < 1.0:
                return True
            vadj.set_value(end_val)
            return False

        GLib.timeout_add(16, step)
        return False

    def show_go_to_line(self):
        """Show a Go-To-Line dialog."""
        tab = self._get_current_tab()
        if not tab:
            return

        total_lines = tab.buffer.get_line_count()

        def on_submit(text):
            try:
                line = int(text)
                if 1 <= line <= total_lines:
                    self._go_to_line(tab, line)
            except ValueError:
                pass

        def validate(text):
            if not text:
                return None
            try:
                line = int(text)
                if line < 1 or line > total_lines:
                    return f"Line must be between 1 and {total_lines}"
            except ValueError:
                return "Please enter a number"
            return None

        from popups.input_dialog import show_input

        show_input(
            parent=self.get_root(),
            title="Go to Line",
            message=f"Enter line number (1\u2013{total_lines}):",
            placeholder="Line number",
            on_submit=on_submit,
            validate=validate,
        )
