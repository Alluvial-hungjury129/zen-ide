"""
Navigation Highlight module for Zen IDE.
Provides temporary line highlighting with fade-out animation
for navigation actions (Cmd+Click go-to-definition).
"""

from gi.repository import GLib, GtkSource

from themes import get_theme


class NavigationHighlight:
    """
    Handles temporary line highlighting with smooth fade-out animation.
    Used when navigating to definitions via Cmd+Click.
    """

    # Fade animation - alpha values from bright to transparent
    FADE_ALPHAS = [0.25, 0.20, 0.15, 0.10, 0.05, 0.0]
    TAG_NAME = "nav_flash_highlight"

    def __init__(self):
        self._active_highlights = {}  # buffer -> highlight info

    @staticmethod
    def _unwrap_iter(result):
        try:
            return result[1]
        except (TypeError, IndexError):
            return result

    def highlight_symbol(
        self,
        buffer: GtkSource.Buffer,
        line: int,
        symbol: str,
        hold_duration_ms: int = 400,
        fade_step_ms: int = 50,
    ):
        """
        Highlight a specific symbol on a line with fade-out animation.

        Args:
            buffer: The GtkSource.Buffer
            line: The line number (1-based)
            symbol: The symbol name to highlight
            hold_duration_ms: How long to hold before fading
            fade_step_ms: Time between fade steps
        """
        try:
            line_0 = max(0, line - 1)
            start_iter = buffer.get_iter_at_line(line_0)
            try:
                start_iter = start_iter[1]
            except (TypeError, IndexError):
                pass

            end_iter = start_iter.copy()
            if not end_iter.ends_line():
                end_iter.forward_to_line_end()

            line_text = buffer.get_text(start_iter, end_iter, True)
            idx = line_text.find(symbol)
            if idx < 0:
                # Fallback to full line highlight
                self.highlight_line(buffer, line, hold_duration_ms, fade_step_ms)
                return

            line_start_offset = start_iter.get_offset()
            sym_start_offset = line_start_offset + idx
            sym_end_offset = sym_start_offset + len(symbol)

            self._apply_highlight(buffer, sym_start_offset, sym_end_offset, hold_duration_ms, fade_step_ms)
        except Exception:
            pass

    def highlight_line(
        self,
        buffer: GtkSource.Buffer,
        line: int,
        hold_duration_ms: int = 400,
        fade_step_ms: int = 50,
    ):
        """
        Highlight a line temporarily with a fade-out effect.

        Args:
            buffer: The GtkSource.Buffer
            line: The line number (1-based, will convert to 0-based)
            hold_duration_ms: How long to hold the full highlight before fading
            fade_step_ms: Time between fade steps
        """
        try:
            line_0 = max(0, line - 1)
            start_iter = buffer.get_iter_at_line(line_0)
            try:
                start_iter = start_iter[1]
            except (TypeError, IndexError):
                pass

            end_iter = start_iter.copy()
            if not end_iter.ends_line():
                end_iter.forward_to_line_end()
            # Include the newline character
            end_iter.forward_char()

            start_offset = start_iter.get_offset()
            end_offset = end_iter.get_offset()
            self._apply_highlight(buffer, start_offset, end_offset, hold_duration_ms, fade_step_ms)
        except Exception:
            pass

    def _apply_highlight(
        self,
        buffer: GtkSource.Buffer,
        start_offset: int,
        end_offset: int,
        hold_duration_ms: int,
        fade_step_ms: int,
    ):
        """Apply animated highlight between two offsets."""
        self._cancel_highlight(buffer)

        theme = get_theme()
        highlight_color = theme.accent_color

        tag_table = buffer.get_tag_table()
        tag = tag_table.lookup(self.TAG_NAME)
        if tag:
            tag_table.remove(tag)

        buffer.create_tag(
            self.TAG_NAME,
            background=highlight_color,
            background_full_height=True,
        )

        # Rebuild iterators from offsets right before applying the tag.
        # This avoids keeping iterators alive across buffer mutations.
        start_iter = self._unwrap_iter(buffer.get_iter_at_offset(max(0, start_offset)))
        end_iter = self._unwrap_iter(buffer.get_iter_at_offset(max(0, end_offset)))
        buffer.apply_tag_by_name(self.TAG_NAME, start_iter, end_iter)

        self._active_highlights[buffer] = {
            "fade_index": 0,
            "timer_id": None,
            "highlight_color": highlight_color,
        }

        timer_id = GLib.timeout_add(
            hold_duration_ms,
            lambda: self._start_fade(buffer, fade_step_ms),
        )
        self._active_highlights[buffer]["timer_id"] = timer_id

    def _cancel_highlight(self, buffer: GtkSource.Buffer):
        """Cancel any active highlight on a buffer"""
        if buffer in self._active_highlights:
            info = self._active_highlights[buffer]

            # Cancel pending timer
            if info.get("timer_id"):
                try:
                    GLib.source_remove(info["timer_id"])
                except Exception:
                    pass

            # Remove tag from buffer
            try:
                start = buffer.get_start_iter()
                end = buffer.get_end_iter()
                buffer.remove_tag_by_name(self.TAG_NAME, start, end)
            except Exception:
                pass

            del self._active_highlights[buffer]

    def _start_fade(self, buffer: GtkSource.Buffer, fade_step_ms: int = 100):
        """Start the fade-out animation"""
        if buffer not in self._active_highlights:
            return False  # Return False to stop GLib timeout

        info = self._active_highlights[buffer]

        # Cancel any existing timer
        if info.get("timer_id"):
            try:
                GLib.source_remove(info["timer_id"])
            except Exception:
                pass

        # Start fade animation
        self._fade_step(buffer, fade_step_ms)
        return False  # Don't repeat this timeout

    def _fade_step(self, buffer: GtkSource.Buffer, fade_step_ms: int):
        """Execute one step of the fade animation"""
        if buffer not in self._active_highlights:
            return

        info = self._active_highlights[buffer]
        fade_index = info["fade_index"]

        if fade_index >= len(self.FADE_ALPHAS):
            # Animation complete
            self._cancel_highlight(buffer)
            return

        alpha = self.FADE_ALPHAS[fade_index]

        if alpha <= 0:
            # Final step - remove highlight
            self._cancel_highlight(buffer)
            return

        try:
            # Update tag color with new alpha
            # For GTK, we need to update the tag's background property
            tag_table = buffer.get_tag_table()
            tag = tag_table.lookup(self.TAG_NAME)
            if tag:
                # Convert alpha to RGBA string
                base_color = info["highlight_color"].lstrip("#")
                r = int(base_color[0:2], 16)
                g = int(base_color[2:4], 16)
                b = int(base_color[4:6], 16)
                rgba_str = f"rgba({r},{g},{b},{alpha})"
                tag.props.background = rgba_str

            # Schedule next step
            info["fade_index"] = fade_index + 1
            info["timer_id"] = GLib.timeout_add(
                fade_step_ms,
                lambda: self._fade_step_callback(buffer, fade_step_ms),
            )
        except Exception:
            self._cancel_highlight(buffer)

    def _fade_step_callback(self, buffer: GtkSource.Buffer, fade_step_ms: int):
        """Callback wrapper for fade step (returns False to not repeat)"""
        self._fade_step(buffer, fade_step_ms)
        return False

    def clear_all(self):
        """Clear all active highlights"""
        for buffer in list(self._active_highlights.keys()):
            self._cancel_highlight(buffer)


# Global singleton instance
nav_highlight = NavigationHighlight()
