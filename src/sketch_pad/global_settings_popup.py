"""
Global Diagram Settings popup for Sketch Pad.
Allows changing all font sizes, font family, and all shape sizes at once.
"""

from gi.repository import Gtk

from fonts import get_font_manager
from popups.nvim_popup import NvimPopup
from shared.ui import ZenButton
from sketch_pad.sketch_model import (
    ArrowShape,
    CloudShape,
    DatabaseShape,
    RectangleShape,
    TopicShape,
)


class GlobalDiagramSettingsPopup(NvimPopup):
    """Popup to globally adjust font sizes and shape sizes in the diagram."""

    def __init__(self, parent, board, canvas, on_apply):
        self._board = board
        self._canvas = canvas
        self._on_apply = on_apply
        super().__init__(parent, title="Global Diagram Settings", width=440)

    def _create_content(self):
        # --- Dark mode toggle row ---
        dark_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dark_label = Gtk.Label(label="Dark mode (M):")
        dark_label.set_hexpand(True)
        dark_label.set_halign(Gtk.Align.START)
        dark_box.append(dark_label)

        self._dark_switch = Gtk.Switch()
        self._dark_switch.set_active(self._canvas._dark_mode)
        self._dark_switch.connect("state-set", self._on_dark_mode_toggled)
        dark_box.append(self._dark_switch)

        self._content_box.append(dark_box)

        # --- Grid toggle row ---
        grid_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        grid_label = Gtk.Label(label="Show grid (G):")
        grid_label.set_hexpand(True)
        grid_label.set_halign(Gtk.Align.START)
        grid_box.append(grid_label)

        self._grid_switch = Gtk.Switch()
        self._grid_switch.set_active(self._canvas._show_grid)
        self._grid_switch.connect("state-set", self._on_grid_toggled)
        grid_box.append(self._grid_switch)

        self._content_box.append(grid_box)

        # --- Separator ---
        sep_dark = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._content_box.append(sep_dark)

        # --- Font family row ---
        family_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        family_label = Gtk.Label(label="Font family:")
        family_label.set_hexpand(True)
        family_label.set_halign(Gtk.Align.START)
        family_box.append(family_label)

        fm = get_font_manager()
        fonts = fm.get_all_system_fonts()
        self._font_combo = Gtk.DropDown.new_from_strings(fonts)
        self._font_combo.set_enable_search(True)
        current_family = self._canvas._font_family
        try:
            idx = fonts.index(current_family)
        except ValueError:
            idx = 0
        self._font_combo.set_selected(idx)
        self._fonts_list = fonts
        family_box.append(self._font_combo)

        family_apply = ZenButton(label="Apply")
        family_apply.connect("clicked", self._on_apply_family)
        family_box.append(family_apply)

        self._content_box.append(family_box)

        # --- Separator ---
        sep0 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._content_box.append(sep0)

        # --- Font size row ---
        font_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        font_label = Gtk.Label(label="Set all font sizes:")
        font_label.set_hexpand(True)
        font_label.set_halign(Gtk.Align.START)
        font_box.append(font_label)

        self._font_spin = Gtk.SpinButton()
        self._font_spin.set_range(6, 72)
        self._font_spin.set_increments(1, 4)
        self._font_spin.set_value(self._get_avg_font_size())
        self._font_spin.set_digits(0)
        self._font_spin.set_width_chars(3)
        font_box.append(self._font_spin)

        font_apply = ZenButton(label="Apply")
        font_apply.connect("clicked", self._on_apply_font)
        font_box.append(font_apply)

        self._content_box.append(font_box)

        # --- Separator ---
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._content_box.append(sep)

        # --- Shape size row (absolute pixels) ---
        avg_w, avg_h = self._get_avg_shape_size()

        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        size_label = Gtk.Label(label="Set all shape sizes (px):")
        size_label.set_hexpand(True)
        size_label.set_halign(Gtk.Align.START)
        size_box.append(size_label)

        w_label = Gtk.Label(label="W:")
        size_box.append(w_label)
        self._width_spin = Gtk.SpinButton()
        self._width_spin.set_range(3, 200)
        self._width_spin.set_increments(1, 5)
        self._width_spin.set_value(avg_w)
        self._width_spin.set_digits(0)
        self._width_spin.set_width_chars(4)
        size_box.append(self._width_spin)

        h_label = Gtk.Label(label="H:")
        size_box.append(h_label)
        self._height_spin = Gtk.SpinButton()
        self._height_spin.set_range(3, 200)
        self._height_spin.set_increments(1, 5)
        self._height_spin.set_value(avg_h)
        self._height_spin.set_digits(0)
        self._height_spin.set_width_chars(4)
        size_box.append(self._height_spin)

        size_apply = ZenButton(label="Apply")
        size_apply.connect("clicked", self._on_apply_size)
        size_box.append(size_apply)

        self._content_box.append(size_box)

    def _on_dark_mode_toggled(self, switch, state):
        self._canvas._dark_mode = state
        self._canvas.queue_draw()
        return False

    def _on_grid_toggled(self, switch, state):
        self._canvas._show_grid = state
        self._canvas.queue_draw()
        return False

    def _on_apply_family(self, _btn):
        idx = self._font_combo.get_selected()
        if 0 <= idx < len(self._fonts_list):
            family = self._fonts_list[idx]
            self._canvas.set_font_family(family)
            self._on_apply()
        self.close()

    def _get_avg_font_size(self):
        """Get the average font size across all shapes that have one."""
        sizes = []
        for s in self._board.shapes.values():
            if isinstance(s, (RectangleShape, DatabaseShape, ArrowShape, TopicShape, CloudShape)):
                if s.font_size is not None:
                    sizes.append(s.font_size)
        return round(sum(sizes) / len(sizes)) if sizes else 14

    def _on_apply_font(self, _btn):
        size = self._font_spin.get_value()
        changed = False
        for s in self._board.shapes.values():
            if isinstance(s, (RectangleShape, DatabaseShape, ArrowShape, TopicShape, CloudShape)):
                s.font_size = max(6, min(72, size))
                changed = True
        if changed:
            self._on_apply()
        self.close()

    def _get_avg_shape_size(self):
        """Get the average width and height across all resizable shapes."""
        widths, heights = [], []
        for s in self._board.shapes.values():
            if isinstance(s, (RectangleShape, TopicShape, DatabaseShape, CloudShape)):
                widths.append(s.width)
                heights.append(s.height)
        avg_w = round(sum(widths) / len(widths)) if widths else 10
        avg_h = round(sum(heights) / len(heights)) if heights else 6
        return avg_w, avg_h

    def _on_apply_size(self, _btn):
        new_w = max(3, int(self._width_spin.get_value()))
        new_h = max(3, int(self._height_spin.get_value()))
        changed = False
        for s in self._board.shapes.values():
            if isinstance(s, (RectangleShape, TopicShape, DatabaseShape, CloudShape)):
                s.width = new_w
                s.height = new_h
                changed = True
        if changed:
            self._on_apply()
        self.close()
