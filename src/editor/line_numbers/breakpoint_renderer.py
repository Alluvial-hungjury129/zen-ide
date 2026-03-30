"""Breakpoint gutter renderer (left column) — red dots for breakpoints."""

from gi.repository import Gdk, Graphene, Gtk, GtkSource

from shared.ui.rounded_rect import RoundedRect
from shared.utils import hex_to_gdk_rgba
from themes import get_theme

from .constants import _BP_DIAMETER, _BP_LEFT_PAD, _ZONE_WIDTH


class BreakpointGutterRenderer(GtkSource.GutterRenderer):
    __gtype_name__ = "BreakpointGutterRenderer"

    def __init__(self, view):
        super().__init__()
        self._view = view
        self._breakpoint_mgr = None
        self._file_path = ""
        self._hover_line = -1
        self._current_line: int | None = None  # 1-based execution pointer line
        self.set_xpad(0)
        self.set_ypad(0)

        self.connect("query-activatable", self._on_query_activatable)
        self.connect("activate", self._on_activate)

        self._pointer_cursor = Gdk.Cursor.new_from_name("pointer")
        self._default_cursor = Gdk.Cursor.new_from_name("default")

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

    def set_breakpoint_source(self, breakpoint_mgr, file_path=""):
        self._breakpoint_mgr = breakpoint_mgr
        self._file_path = file_path

    def set_file_path(self, file_path):
        self._file_path = file_path

    def set_current_line(self, line: int | None):
        """Set/clear the execution pointer line (1-based)."""
        self._current_line = line
        self.queue_draw()

    def do_measure(self, _orientation, _for_size):
        return _ZONE_WIDTH, _ZONE_WIDTH, -1, -1

    def do_query_data(self, lines, line):
        pass

    def do_snapshot_line(self, snapshot, lines, line):
        # Paint gutter background per-line (so it doesn't extend past last line)
        theme = get_theme()
        line_y, line_h = lines.get_line_yrange(line, Gtk.TextWindowType.WIDGET)
        snapshot.append_color(
            hex_to_gdk_rgba(theme.line_number_bg, 1.0), Graphene.Rect().init(0, line_y, _ZONE_WIDTH, line_h)
        )

        is_execution_line = self._current_line is not None and line == self._current_line - 1

        if self._breakpoint_mgr and self._file_path:
            bp = None
            for b in self._breakpoint_mgr.get_for_file(self._file_path):
                if b.line - 1 == line:
                    bp = b
                    break

            if bp is not None and not is_execution_line:
                if not bp.enabled:
                    color = hex_to_gdk_rgba("#808080", 0.5)
                elif bp.is_conditional:
                    color = hex_to_gdk_rgba("#FF8C00", 1.0)
                elif bp.is_logpoint:
                    color = hex_to_gdk_rgba("#3CB371", 1.0)
                else:
                    color = hex_to_gdk_rgba("#E51400", 1.0)
                cx = _BP_LEFT_PAD + (_ZONE_WIDTH - _BP_LEFT_PAD - _BP_DIAMETER) / 2
                cy = line_y + (line_h - _BP_DIAMETER) / 2
                rect = Graphene.Rect().init(cx, cy, _BP_DIAMETER, _BP_DIAMETER)
                rounded = RoundedRect.build(cx, cy, _BP_DIAMETER, _BP_DIAMETER, _BP_DIAMETER // 2)
                snapshot.push_rounded_clip(rounded)
                snapshot.append_color(color, rect)
                snapshot.pop()
            elif not is_execution_line and line == self._hover_line:
                color = hex_to_gdk_rgba("#E51400", 0.25)
                cx = _BP_LEFT_PAD + (_ZONE_WIDTH - _BP_LEFT_PAD - _BP_DIAMETER) / 2
                cy = line_y + (line_h - _BP_DIAMETER) / 2
                rect = Graphene.Rect().init(cx, cy, _BP_DIAMETER, _BP_DIAMETER)
                rounded = RoundedRect.build(cx, cy, _BP_DIAMETER, _BP_DIAMETER, _BP_DIAMETER // 2)
                snapshot.push_rounded_clip(rounded)
                snapshot.append_color(color, rect)
                snapshot.pop()

        # Execution pointer — yellow dot drawn on top, same position as breakpoint dot
        if is_execution_line:
            color = hex_to_gdk_rgba("#FFCC00", 1.0)
            cx = _BP_LEFT_PAD + (_ZONE_WIDTH - _BP_LEFT_PAD - _BP_DIAMETER) / 2
            cy = line_y + (line_h - _BP_DIAMETER) / 2
            rect = Graphene.Rect().init(cx, cy, _BP_DIAMETER, _BP_DIAMETER)
            rounded = RoundedRect.build(cx, cy, _BP_DIAMETER, _BP_DIAMETER, _BP_DIAMETER // 2)
            snapshot.push_rounded_clip(rounded)
            snapshot.append_color(color, rect)
            snapshot.pop()

    def _on_motion(self, controller, x, y):
        alloc = self.get_allocation()
        view_y = int(y) + alloc.y
        bx, by = self._view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, 0, view_y)
        _, it = self._view.get_iter_at_location(bx, by)
        new_line = it.get_line()
        if new_line != self._hover_line:
            self._hover_line = new_line
            self.set_cursor(self._pointer_cursor)
            self.queue_draw()

    def _on_leave(self, controller):
        self._hover_line = -1
        self.set_cursor(self._default_cursor)
        self.queue_draw()

    def _on_query_activatable(self, renderer, it, area):
        return True

    def _on_activate(self, renderer, it, area, button, state, n_presses):
        line = it.get_line() + 1
        if self._breakpoint_mgr and self._file_path:
            self._breakpoint_mgr.toggle(self._file_path, line)
            self.queue_draw()
            self._view.queue_draw()
