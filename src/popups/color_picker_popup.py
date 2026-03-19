"""Color picker popup - NvimPopup-based color editor with hex input, RGB sliders, palette, and live preview."""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup

PALETTE_COLORS = [
    "#000000",
    "#404040",
    "#808080",
    "#c0c0c0",
    "#ffffff",
    "#ff0000",
    "#ff6600",
    "#ffcc00",
    "#ffff00",
    "#ccff00",
    "#00ff00",
    "#00ffcc",
    "#00ffff",
    "#0099ff",
    "#0000ff",
    "#6600ff",
    "#cc00ff",
    "#ff00cc",
    "#ff0066",
    "#993300",
    "#800000",
    "#808000",
    "#008000",
    "#008080",
    "#000080",
    "#800080",
    "#ff6666",
    "#66ff66",
    "#6666ff",
    "#ffff66",
]


class ColorPickerPopup(NvimPopup):
    """Minimalist color picker with hex input, RGB(A) sliders, palette, and a live swatch preview."""

    def __init__(self, parent: Gtk.Window, hex_str: str, with_alpha: bool, on_apply):
        self._initial_hex = hex_str
        self._with_alpha = with_alpha
        self._on_apply = on_apply
        self._updating = False
        self._palette_providers = []
        self._r, self._g, self._b, self._a = self._parse_hex(hex_str)
        super().__init__(parent, title="Color", width=340)

    def _create_content(self):
        self._content_box.set_halign(Gtk.Align.CENTER)

        # --- Preview swatch ---
        self._swatch = Gtk.Box()
        self._swatch.set_size_request(300, 48)
        self._swatch.set_halign(Gtk.Align.CENTER)
        self._swatch.set_margin_bottom(8)
        self._content_box.append(self._swatch)

        # --- Hex entry row ---
        hex_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hex_row.set_halign(Gtk.Align.CENTER)
        hex_row.set_margin_bottom(8)

        hex_label = Gtk.Label(label="Hex")
        hex_label.add_css_class("nvim-popup-message")
        hex_label.set_size_request(28, -1)
        hex_row.append(hex_label)

        self._hex_entry = self._create_input_entry(placeholder="#000000", initial_value=self._initial_hex)
        self._hex_entry.set_size_request(260, -1)
        self._hex_entry.set_max_length(9)
        self._hex_entry_handler = self._hex_entry.connect("changed", self._on_hex_changed)
        hex_row.append(self._hex_entry)

        self._content_box.append(hex_row)

        # --- RGB(A) sliders ---
        channels = [("R", self._r), ("G", self._g), ("B", self._b)]
        if self._with_alpha:
            channels.append(("A", self._a))

        self._sliders = {}
        self._value_labels = {}
        for name, value in channels:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_halign(Gtk.Align.CENTER)
            row.set_size_request(300, -1)

            label = Gtk.Label(label=name)
            label.add_css_class("nvim-popup-message")
            label.set_size_request(28, -1)
            row.append(label)

            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
            scale.set_draw_value(False)
            scale.set_hexpand(True)
            scale.set_value(value)
            scale.connect("value-changed", self._on_slider_changed)
            row.append(scale)
            self._sliders[name] = scale

            val_label = Gtk.Label(label=str(value))
            val_label.add_css_class("nvim-popup-status")
            val_label.set_size_request(32, -1)
            val_label.set_halign(Gtk.Align.END)
            row.append(val_label)
            self._value_labels[name] = val_label

            self._content_box.append(row)

        # --- Palette ---
        palette_label = Gtk.Label(label="Palette")
        palette_label.add_css_class("nvim-popup-message")
        palette_label.set_halign(Gtk.Align.CENTER)
        palette_label.set_margin_top(10)
        palette_label.set_margin_bottom(4)
        self._content_box.append(palette_label)

        palette_grid = Gtk.FlowBox()
        palette_grid.set_halign(Gtk.Align.CENTER)
        palette_grid.set_max_children_per_line(10)
        palette_grid.set_min_children_per_line(10)
        palette_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        palette_grid.set_row_spacing(3)
        palette_grid.set_column_spacing(3)

        display = Gdk.Display.get_default()
        for hex_color in PALETTE_COLORS:
            btn = Gtk.Button()
            btn.set_size_request(24, 24)
            btn.set_has_frame(False)
            css_class = f"palette-{hex_color.lstrip('#')}"
            btn.add_css_class(css_class)
            provider = Gtk.CssProvider()
            provider.load_from_data(
                f"button.{css_class} {{ background: {hex_color}; min-width: 24px; min-height: 24px; padding: 0; border-radius: 3px; }}".encode()
            )
            Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
            self._palette_providers.append(provider)
            btn.connect("clicked", self._on_palette_clicked, hex_color)
            palette_grid.insert(btn, -1)

        self._content_box.append(palette_grid)

        # --- Buttons ---
        button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_row.set_halign(Gtk.Align.CENTER)
        button_row.set_margin_top(12)

        cancel_btn = self._create_button("Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        button_row.append(cancel_btn)

        apply_btn = self._create_button("Apply", primary=True)
        apply_btn.connect("clicked", lambda _: self._apply())
        button_row.append(apply_btn)

        self._content_box.append(button_row)

        # --- Hint ---
        hint = Gtk.Label(label="Enter apply • Esc cancel")
        hint.add_css_class("nvim-popup-hint")
        hint.set_halign(Gtk.Align.CENTER)
        hint.set_margin_top(4)
        self._content_box.append(hint)

        self._update_swatch()

    def _on_palette_clicked(self, _btn, hex_color):
        r, g, b, a = self._parse_hex(hex_color)
        if r < 0:
            return
        self._r, self._g, self._b = r, g, b
        if self._with_alpha:
            self._a = a
        self._updating = True
        self._hex_entry.handler_block(self._hex_entry_handler)
        self._hex_entry.set_text(self._build_hex())
        self._hex_entry.handler_unblock(self._hex_entry_handler)
        self._sliders["R"].set_value(r)
        self._sliders["G"].set_value(g)
        self._sliders["B"].set_value(b)
        if "A" in self._sliders:
            self._sliders["A"].set_value(a)
        self._update_value_labels()
        self._update_swatch()
        self._updating = False

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if keyval == Gdk.KEY_Return:
            self._apply()
            return True
        return False

    def _on_hex_changed(self, entry):
        if self._updating:
            return
        text = entry.get_text().strip()
        r, g, b, a = self._parse_hex(text)
        if r < 0:
            return
        self._r, self._g, self._b, self._a = r, g, b, a
        self._updating = True
        self._sliders["R"].set_value(r)
        self._sliders["G"].set_value(g)
        self._sliders["B"].set_value(b)
        if "A" in self._sliders:
            self._sliders["A"].set_value(a)
        self._update_value_labels()
        self._update_swatch()
        self._updating = False

    def _on_slider_changed(self, scale):
        if self._updating:
            return
        self._r = int(self._sliders["R"].get_value())
        self._g = int(self._sliders["G"].get_value())
        self._b = int(self._sliders["B"].get_value())
        if "A" in self._sliders:
            self._a = int(self._sliders["A"].get_value())
        self._updating = True
        self._hex_entry.handler_block(self._hex_entry_handler)
        self._hex_entry.set_text(self._build_hex())
        self._hex_entry.handler_unblock(self._hex_entry_handler)
        self._update_value_labels()
        self._update_swatch()
        self._updating = False

    def _update_value_labels(self):
        self._value_labels["R"].set_label(str(self._r))
        self._value_labels["G"].set_label(str(self._g))
        self._value_labels["B"].set_label(str(self._b))
        if "A" in self._value_labels:
            self._value_labels["A"].set_label(str(self._a))

    def _update_swatch(self):
        if self._with_alpha:
            css = f"background-color: rgba({self._r},{self._g},{self._b},{self._a / 255.0:.3f});"
        else:
            css = f"background-color: #{self._r:02x}{self._g:02x}{self._b:02x};"
        provider = Gtk.CssProvider()
        provider.load_from_data(f"box.color-swatch {{ {css} }}".encode())
        self._swatch.add_css_class("color-swatch")
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        # Store provider so we can remove the old one next time
        old = getattr(self, "_swatch_css", None)
        if old:
            Gtk.StyleContext.remove_provider_for_display(display, old)
        self._swatch_css = provider

    def _build_hex(self):
        if self._with_alpha:
            return f"#{self._r:02x}{self._g:02x}{self._b:02x}{self._a:02x}"
        return f"#{self._r:02x}{self._g:02x}{self._b:02x}"

    def _apply(self):
        if self._on_apply:
            self._on_apply(self._build_hex())
        self._result = self._build_hex()
        self.close()

    def close(self):
        display = Gdk.Display.get_default()
        old = getattr(self, "_swatch_css", None)
        if old:
            Gtk.StyleContext.remove_provider_for_display(display, old)
            self._swatch_css = None
        for p in self._palette_providers:
            Gtk.StyleContext.remove_provider_for_display(display, p)
        self._palette_providers.clear()
        super().close()

    def present(self):
        super().present()
        self._hex_entry.grab_focus()

    @staticmethod
    def _parse_hex(hex_str):
        """Parse hex to (r, g, b, a) ints 0-255. Returns (-1,...) on failure."""
        h = hex_str.lstrip("#")
        try:
            if len(h) == 3:
                return int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 255
            if len(h) == 6:
                return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255
            if len(h) == 8:
                return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
        except ValueError:
            pass
        return -1, -1, -1, -1
