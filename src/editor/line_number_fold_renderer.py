"""
Gutter renderer for code folding.

Provides a unified GutterRenderer that draws both line numbers and fold
chevrons in a single wider gutter column.  Used by FoldManager.
"""

from gi.repository import GLib, Graphene, Gtk, GtkSource, Pango

from fonts import get_font_settings
from icons import ICON_FONT_FAMILY
from shared.utils import hex_to_gdk_rgba
from themes import get_theme

_CHEVRON_SIZE = 7
_CHEVRON_COL_WIDTH = 14  # extra pixels for the chevron area
_NUM_RIGHT_PAD = 6  # gap between number text and chevron area
_NUM_LEFT_PAD = 14  # left padding before line number (matches chevron area)
_FIXED_DIGIT_COUNT = 4  # fixed digit count so the gutter never resizes


# ---------------------------------------------------------------------------
# Unified gutter renderer — line numbers + fold chevrons
# ---------------------------------------------------------------------------


class LineNumberFoldRenderer(GtkSource.GutterRenderer):
    """Replaces the built-in line number renderer.

    Draws the line number left-aligned and a fold chevron (if any)
    right-aligned, all within a single gutter column.
    """

    __gtype_name__ = "LineNumberFoldRenderer"

    def __init__(self, fold_manager, view):
        super().__init__()
        self._fm = fold_manager
        self._view = view
        self._digit_count = _FIXED_DIGIT_COUNT
        self._char_width = 0.0  # cached monospace char width
        self._layout = None  # reusable PangoLayout for number text
        self._icon_layout = None  # reusable PangoLayout for fold icon glyph
        self._hover = False  # chevrons only visible on hover
        self._chevron_opacity = 0.0  # animated opacity (0 = hidden, 1 = full)
        self._fade_tick_id = None  # GLib tick callback id
        self._fade_target = 0.0  # target opacity
        self.set_xpad(0)
        self.set_ypad(0)
        self.set_alignment_mode(GtkSource.GutterRendererAlignmentMode.CELL)

        self.connect("query-activatable", self._on_query_activatable)
        self.connect("activate", self._on_activate)

        # Show chevrons only when mouse is over the gutter
        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", self._on_hover_enter)
        motion.connect("leave", self._on_hover_leave)
        self.add_controller(motion)

    # -- width calculation ------------------------------------------------

    def _ensure_char_width(self):
        if self._char_width > 0:
            return
        pc = self._view.get_pango_context()
        if pc is None:
            return
        font_desc = pc.get_font_description()
        if font_desc is None:
            return
        metrics = pc.get_metrics(font_desc)
        self._char_width = metrics.get_approximate_digit_width() / Pango.SCALE
        if self._char_width <= 0:
            self._char_width = 8.0

    def do_measure(self, _orientation, _for_size):
        self._ensure_char_width()
        num_width = int(self._digit_count * self._char_width)
        total = _NUM_LEFT_PAD + num_width + _NUM_RIGHT_PAD + _CHEVRON_COL_WIDTH
        return total, total, -1, -1

    # -- rendering --------------------------------------------------------

    def do_query_data(self, lines, line):
        pass  # all rendering in do_snapshot_line

    def do_snapshot_line(self, snapshot, lines, line):
        fm = self._fm

        # Skip lines hidden inside a collapsed fold — they are invisible
        # in the buffer and should not be rendered in the gutter either.
        if any(sl < line <= el for sl, el in fm._collapsed.items()):
            return

        theme = get_theme()
        self._ensure_char_width()
        num_col_width = int(self._digit_count * self._char_width)
        total_w = _NUM_LEFT_PAD + num_col_width + _NUM_RIGHT_PAD + _CHEVRON_COL_WIDTH
        line_y, line_h = lines.get_line_yrange(line, Gtk.TextWindowType.WIDGET)

        # --- line number ---
        is_current = lines.is_cursor(line)
        num_fg = hex_to_gdk_rgba(theme.fg_color if is_current else theme.line_number_fg, 1.0)

        if self._layout is None:
            self._layout = self._view.create_pango_layout("")

        self._layout.set_text(str(line + 1), -1)
        _ink, logical = self._layout.get_pixel_extents()
        x = _NUM_LEFT_PAD + (num_col_width - logical.width) / 2
        y = line_y + (line_h - logical.height) / 2

        snapshot.save()
        snapshot.translate(Graphene.Point().init(x, y))
        snapshot.append_layout(self._layout, num_fg)
        snapshot.restore()

        # --- fold chevron (icon font glyph) — visible on hover or when collapsed ---
        if line not in fm._fold_regions:
            return
        collapsed = line in fm._collapsed
        opacity = 1.0 if collapsed else self._chevron_opacity
        if opacity <= 0.01:
            return

        chevron_fg = hex_to_gdk_rgba(theme.line_number_fg, 0.7 * opacity)
        glyph = "\U000f0142" if collapsed else "\U000f0140"

        if self._icon_layout is None:
            self._icon_layout = self._view.create_pango_layout("")
            # Get size from font manager instead of hardcoding
            editor_font = get_font_settings("editor")
            sz = int(editor_font.get("size", 13) * Pango.SCALE * 1.2)
            attrs = Pango.AttrList.new()
            attrs.insert(Pango.attr_family_new(ICON_FONT_FAMILY))
            attrs.insert(Pango.attr_size_new(sz))
            attrs.insert(Pango.attr_weight_new(Pango.Weight.BOLD))
            self._icon_layout.set_attributes(attrs)

        self._icon_layout.set_text(glyph, -1)
        _ink, icon_log = self._icon_layout.get_pixel_extents()
        chevron_zone = _NUM_RIGHT_PAD + _CHEVRON_COL_WIDTH
        ix = _NUM_LEFT_PAD + num_col_width + (chevron_zone - icon_log.width) / 2
        iy = line_y + (line_h - icon_log.height) / 2

        snapshot.save()
        snapshot.translate(Graphene.Point().init(ix, iy))
        snapshot.append_layout(self._icon_layout, chevron_fg)
        snapshot.restore()

    # -- hover handling (fade in/out) -------------------------------------

    _FADE_STEP = 0.08  # opacity change per tick (~16ms)

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
            return  # already running
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
            return False  # stop
        return True  # continue

    # -- click handling ---------------------------------------------------

    def _on_query_activatable(self, renderer, it, area):
        return it.get_line() in self._fm._fold_regions

    def _on_activate(self, renderer, it, area, button, state, n_presses):
        line = it.get_line()
        fm = self._fm
        # Debounce: ignore rapid clicks while a toggle is still pending.
        if fm._toggle_pending:
            return
        fm._toggle_pending = True

        def _do_toggle():
            fm.toggle_fold(line)
            # Re-arm after a short cooldown to absorb double-click bursts.
            GLib.timeout_add(150, fm._clear_toggle_pending)
            return False

        # Use timeout (not idle_add) so GTK finishes all click processing first.
        GLib.timeout_add(30, _do_toggle)
