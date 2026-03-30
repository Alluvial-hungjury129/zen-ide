"""Fold chevron renderer (right column) — click to toggle folds."""

from gi.repository import GLib, Graphene, Gtk, GtkSource, Pango

from icons import get_icon_font_name
from shared.utils import hex_to_gdk_rgba
from themes import get_theme

from .constants import _CHEVRON_COLLAPSED, _CHEVRON_EXPANDED, _ZONE_WIDTH


class FoldChevronRenderer(GtkSource.GutterRenderer):
    __gtype_name__ = "FoldChevronRenderer"

    def __init__(self, view, fold_manager):
        super().__init__()
        self._view = view
        self._fm = fold_manager
        self._hover = False
        self._chevron_opacity = 0.0
        self._fade_tick_id = None
        self._fade_target = 0.0
        self._layout = None
        self._icon_font_desc = None
        self.set_xpad(0)
        self.set_ypad(0)

        self.connect("query-activatable", self._on_query_activatable)
        self.connect("activate", self._on_activate)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", self._on_hover_enter)
        motion.connect("leave", self._on_hover_leave)
        self.add_controller(motion)

    def do_measure(self, _orientation, _for_size):
        return _ZONE_WIDTH, _ZONE_WIDTH, -1, -1

    def do_query_data(self, lines, line):
        pass

    def _ensure_layout(self):
        if self._layout is not None:
            return
        self._layout = self._view.create_pango_layout("")
        icon_font = get_icon_font_name()
        if icon_font:
            self._icon_font_desc = Pango.FontDescription.from_string(f"{icon_font} 14")
        else:
            pc = self._view.get_pango_context()
            if pc:
                self._icon_font_desc = pc.get_font_description().copy()
                self._icon_font_desc.set_size(14 * Pango.SCALE)

    def do_snapshot_line(self, snapshot, lines, line):
        if any(sl < line <= el for sl, el in self._fm._collapsed.items()):
            return

        # Paint editor background so chevron zone blends with the editor, not the gutter
        theme = get_theme()
        line_y, line_h = lines.get_line_yrange(line, Gtk.TextWindowType.WIDGET)
        snapshot.append_color(hex_to_gdk_rgba(theme.main_bg, 1.0), Graphene.Rect().init(0, line_y, _ZONE_WIDTH, line_h))

        fm = self._fm
        if line not in fm._fold_regions:
            return
        collapsed = line in fm._collapsed
        opacity = 1.0 if collapsed else self._chevron_opacity
        if opacity <= 0.01:
            return

        self._ensure_layout()
        theme = get_theme()
        chevron_fg = hex_to_gdk_rgba(theme.line_number_fg, 0.7 * opacity)

        icon = _CHEVRON_COLLAPSED if collapsed else _CHEVRON_EXPANDED
        self._layout.set_text(icon, -1)
        if self._icon_font_desc:
            self._layout.set_font_description(self._icon_font_desc)
        _ink, logical = self._layout.get_pixel_extents()

        line_y, line_h = lines.get_line_yrange(line, Gtk.TextWindowType.WIDGET)
        x = (_ZONE_WIDTH - logical.width) / 2
        y = line_y + (line_h - logical.height) / 2

        snapshot.save()
        snapshot.translate(Graphene.Point().init(x, y))
        snapshot.append_layout(self._layout, chevron_fg)
        snapshot.restore()

    # -- hover handling ---------------------------------------------------

    _FADE_STEP = 0.08

    def _on_hover_enter(self, controller, x, y):
        self._hover = True
        self._fade_target = 1.0
        self._start_fade()

    def _on_hover_leave(self, controller):
        self._hover = False
        self._fade_target = 0.0
        self._start_fade()

    def _start_fade(self):
        if self._fade_tick_id is not None:
            return
        self._fade_tick_id = GLib.timeout_add(16, self._fade_tick)

    def _fade_tick(self):
        if self._chevron_opacity < self._fade_target:
            self._chevron_opacity = min(self._chevron_opacity + self._FADE_STEP, 1.0)
        elif self._chevron_opacity > self._fade_target:
            self._chevron_opacity = max(self._chevron_opacity - self._FADE_STEP, 0.0)

        self.queue_draw()

        if abs(self._chevron_opacity - self._fade_target) < 0.01:
            self._chevron_opacity = self._fade_target
            self._fade_tick_id = None
            return False
        return True

    # -- click handling ---------------------------------------------------

    def _on_query_activatable(self, renderer, it, area):
        return it.get_line() in self._fm._fold_regions

    def _on_activate(self, renderer, it, area, button, state, n_presses):
        line = it.get_line()
        fm = self._fm
        if fm._toggle_pending:
            return
        fm._toggle_pending = True

        def _do_toggle():
            fm.toggle_fold(line)
            GLib.timeout_add(150, fm._clear_toggle_pending)
            return False

        GLib.timeout_add(30, _do_toggle)
