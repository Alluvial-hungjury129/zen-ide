"""Git diff marker renderer — colored bars between line numbers and chevrons."""

from gi.repository import Graphene, Gtk, GtkSource

from shared.utils import hex_to_gdk_rgba
from themes import get_theme

from .constants import _GIT_MARKER_WIDTH


class GitDiffGutterRenderer(GtkSource.GutterRenderer):
    __gtype_name__ = "GitDiffGutterRenderer"

    def __init__(self, fold_manager):
        super().__init__()
        self._fm = fold_manager
        self._diff_lines = {}  # line_num (0-based) -> "add" | "change" | "del"
        self.set_xpad(0)
        self.set_ypad(0)

    def set_diff_lines(self, diff_lines):
        """Update diff data (called from GutterDiffRenderer after recompute)."""
        self._diff_lines = diff_lines
        self.queue_draw()

    def do_measure(self, _orientation, _for_size):
        return _GIT_MARKER_WIDTH, _GIT_MARKER_WIDTH, -1, -1

    def do_query_data(self, lines, line):
        pass

    def do_snapshot_line(self, snapshot, lines, line):
        if any(sl < line <= el for sl, el in self._fm._collapsed.items()):
            return

        # Paint gutter background per-line
        theme = get_theme()
        line_y, line_h = lines.get_line_yrange(line, Gtk.TextWindowType.WIDGET)
        snapshot.append_color(
            hex_to_gdk_rgba(theme.line_number_bg, 1.0),
            Graphene.Rect().init(0, line_y, _GIT_MARKER_WIDTH, line_h),
        )

        dtype = self._diff_lines.get(line)
        if not dtype:
            return

        if dtype == "add":
            color = hex_to_gdk_rgba(theme.git_added, 0.9)
        elif dtype == "change":
            color = hex_to_gdk_rgba(theme.git_modified, 0.9)
        elif dtype == "del":
            color = hex_to_gdk_rgba(theme.git_deleted, 0.9)
        else:
            return

        if dtype == "del":
            snapshot.append_color(color, Graphene.Rect().init(0, line_y, _GIT_MARKER_WIDTH, min(line_h, 4)))
        else:
            snapshot.append_color(color, Graphene.Rect().init(0, line_y, _GIT_MARKER_WIDTH, line_h))
