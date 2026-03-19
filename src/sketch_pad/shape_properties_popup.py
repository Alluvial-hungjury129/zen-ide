"""
Shape properties popup for Sketch Pad.

Right-click a shape to edit its text, fill color, and text color.
"""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup

# Color palette — 4 rows of 8 colors
COLOR_PALETTE = [
    "#ef4444",
    "#f97316",
    "#eab308",
    "#22c55e",
    "#06b6d4",
    "#3b82f6",
    "#8b5cf6",
    "#ec4899",
    "#991b1b",
    "#9a3412",
    "#854d0e",
    "#166534",
    "#155e75",
    "#1e40af",
    "#5b21b6",
    "#9d174d",
    "#ffffff",
    "#d4d4d4",
    "#a3a3a3",
    "#737373",
    "#404040",
    "#262626",
    "#171717",
    "#000000",
]

SWATCH_SIZE = 22
SWATCH_COLS = 8


class ShapePropertiesPopup(NvimPopup):
    """Properties popup for editing shape text, fill color, and text color."""

    def __init__(self, parent: Gtk.Window, shapes, on_apply, *, text_only=False):
        from sketch_pad.sketch_model import ActorShape, ArrowShape

        if not isinstance(shapes, list):
            shapes = [shapes]
        self._shapes = shapes
        self._on_apply = on_apply
        self._text_only = text_only
        self._all_arrows = all(isinstance(s, ArrowShape) for s in shapes)
        # Resizable = single non-arrow, non-actor shape
        self._resizable = len(shapes) == 1 and not isinstance(shapes[0], (ArrowShape, ActorShape))
        # Determine common values for display
        self._current_fill_color = self._common_value("fill_color")
        self._current_text_color = self._common_value("text_color")
        font_sizes = [s.font_size or 14 for s in shapes]
        self._current_font_size = font_sizes[0] if len(set(font_sizes)) == 1 else 14
        # Only show text editing for a single shape with text
        self._show_text = len(shapes) == 1 and hasattr(shapes[0], "text")
        # Original values for rollback on cancel
        self._originals = {}
        for shape in shapes:
            self._originals[shape.id] = {
                "fill_color": shape.fill_color,
                "text_color": shape.text_color,
                "font_size": shape.font_size or 14,
            }
            if hasattr(shape, "text"):
                self._originals[shape.id]["text"] = getattr(shape, "text", None)
            if self._resizable:
                self._originals[shape.id]["width"] = shape.width
                self._originals[shape.id]["height"] = shape.height
        self._committed = False
        title = "Shape Properties" if len(shapes) == 1 else f"Properties ({len(shapes)} shapes)"
        super().__init__(parent, title=title, width=340)

    def _common_value(self, attr):
        """Return common value if all shapes share it, else None."""
        values = [getattr(s, attr, None) for s in self._shapes]
        return values[0] if len(set(values)) == 1 else None

    def _create_content(self):
        # --- Text section (single shape only) ---
        if self._show_text:
            text_label = self._create_section_label("Text")
            self._content_box.append(text_label)

            self._text_view = Gtk.TextView()
            self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            self._text_view.get_buffer().set_text(self._shapes[0].text or "")
            self._text_view.set_size_request(-1, 60)
            self._text_view.add_css_class("nvim-popup-input")
            self._text_view.set_margin_bottom(8)
            self._text_view.get_buffer().connect("changed", self._on_text_changed)
            scroll = Gtk.ScrolledWindow()
            scroll.set_child(self._text_view)
            scroll.set_min_content_height(60)
            scroll.set_max_content_height(100)
            self._content_box.append(scroll)

        if not self._text_only:
            # --- Font Size section ---
            font_size_label = self._create_section_label("Font Size")
            self._content_box.append(font_size_label)

            font_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            font_row.set_margin_bottom(8)
            self._font_spin = Gtk.SpinButton()
            self._font_spin.set_range(6, 72)
            self._font_spin.set_increments(1, 4)
            self._font_spin.set_value(self._current_font_size)
            self._font_spin.set_digits(0)
            self._font_spin.set_width_chars(3)
            self._font_spin.set_tooltip_text("Font size for shape text")
            self._font_spin.connect("value-changed", self._on_font_size_changed)
            font_row.append(self._font_spin)
            self._content_box.append(font_row)

            # --- Size section (resizable shapes only) ---
            if self._resizable:
                size_label = self._create_section_label("Size")
                self._content_box.append(size_label)

                size_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                size_row.set_margin_bottom(8)

                min_w, min_h = self._get_min_size()

                w_label = Gtk.Label(label="W")
                w_label.add_css_class("nvim-popup-message")
                size_row.append(w_label)

                self._width_spin = Gtk.SpinButton()
                self._width_spin.set_range(min_w, 200)
                self._width_spin.set_increments(1, 5)
                self._width_spin.set_value(self._shapes[0].width)
                self._width_spin.set_digits(0)
                self._width_spin.set_width_chars(4)
                self._width_spin.set_tooltip_text("Shape width (grid cells)")
                self._width_spin.connect("value-changed", self._on_width_changed)
                size_row.append(self._width_spin)

                h_label = Gtk.Label(label="H")
                h_label.add_css_class("nvim-popup-message")
                h_label.set_margin_start(8)
                size_row.append(h_label)

                self._height_spin = Gtk.SpinButton()
                self._height_spin.set_range(min_h, 100)
                self._height_spin.set_increments(1, 5)
                self._height_spin.set_value(self._shapes[0].height)
                self._height_spin.set_digits(0)
                self._height_spin.set_width_chars(4)
                self._height_spin.set_tooltip_text("Shape height (grid cells)")
                self._height_spin.connect("value-changed", self._on_height_changed)
                size_row.append(self._height_spin)

                self._content_box.append(size_row)

            # --- Fill Color section (Line Color for arrows) ---
            fill_label = self._create_section_label("Line Color" if self._all_arrows else "Fill Color")
            self._content_box.append(fill_label)
            fill_grid = self._create_color_grid(
                self._current_fill_color,
                self._on_fill_color_selected,
            )
            self._content_box.append(fill_grid)

        # --- Text Color section ---
        text_color_label = self._create_section_label("Text Color")
        self._content_box.append(text_color_label)
        text_color_grid = self._create_color_grid(
            self._current_text_color,
            self._on_text_color_selected,
        )
        self._content_box.append(text_color_grid)

        # --- Action buttons ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(16)

        cancel_btn = self._create_button("Cancel")
        cancel_btn.connect("clicked", lambda _b: self._cancel())
        btn_box.append(cancel_btn)

        apply_btn = self._create_button("Apply", primary=True)
        apply_btn.connect("clicked", lambda _b: self._apply_and_close())
        btn_box.append(apply_btn)

        self._content_box.append(btn_box)

    def _create_section_label(self, text: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.add_css_class("nvim-popup-message")
        label.set_margin_top(4)
        label.set_margin_bottom(4)
        return label

    def _create_color_grid(self, current_color, on_select) -> Gtk.Box:
        """Create a grid of color swatch buttons."""
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        container.set_margin_bottom(8)

        rows = [COLOR_PALETTE[i : i + SWATCH_COLS] for i in range(0, len(COLOR_PALETTE), SWATCH_COLS)]
        for row_colors in rows:
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            for color in row_colors:
                btn = self._create_swatch(color, color == current_color, on_select)
                row_box.append(btn)
            container.append(row_box)

        return container

    def _create_swatch(self, color: str, is_selected: bool, on_select) -> Gtk.Button:
        btn = Gtk.Button()
        btn.set_size_request(SWATCH_SIZE, SWATCH_SIZE)
        btn.set_tooltip_text(color)
        # CSS for background color
        css = f"""
            button {{
                background: {color};
                min-width: {SWATCH_SIZE}px;
                min-height: {SWATCH_SIZE}px;
                padding: 0;
                border-radius: 3px;
                border: 2px solid {("white" if is_selected else "rgba(255,255,255,0.15)")};
            }}
            button:hover {{
                border: 2px solid rgba(255,255,255,0.8);
            }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        btn.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        btn.connect("clicked", lambda _b, c=color: on_select(c))
        return btn

    def _apply_to_all(self, **props):
        """Apply property changes to all shapes."""
        for shape in self._shapes:
            self._on_apply(shape.id, **props)

    def _on_text_changed(self, buf):
        start, end = buf.get_bounds()
        new_text = buf.get_text(start, end, False)
        self._on_apply(self._shapes[0].id, text=new_text)

    def _on_font_size_changed(self, spin):
        self._current_font_size = spin.get_value()
        self._apply_to_all(font_size=self._current_font_size)

    def _get_min_size(self) -> tuple[int, int]:
        """Return (min_width, min_height) for the current resizable shape."""
        from sketch_pad.sketch_model import (
            CLOUD_MIN_HEIGHT,
            CLOUD_MIN_WIDTH,
            DATABASE_MIN_HEIGHT,
            DATABASE_MIN_WIDTH,
            TOPIC_MIN_HEIGHT,
            TOPIC_MIN_WIDTH,
            CloudShape,
            DatabaseShape,
            TopicShape,
        )

        shape = self._shapes[0]
        if isinstance(shape, TopicShape):
            return (TOPIC_MIN_WIDTH, TOPIC_MIN_HEIGHT)
        if isinstance(shape, DatabaseShape):
            return (DATABASE_MIN_WIDTH, DATABASE_MIN_HEIGHT)
        if isinstance(shape, CloudShape):
            return (CLOUD_MIN_WIDTH, CLOUD_MIN_HEIGHT)
        return (2, 2)

    def _on_width_changed(self, spin):
        self._on_apply(self._shapes[0].id, width=int(spin.get_value()))

    def _on_height_changed(self, spin):
        self._on_apply(self._shapes[0].id, height=int(spin.get_value()))

    def _on_fill_color_selected(self, color):
        self._current_fill_color = color
        self._apply_to_all(fill_color=color)
        self._rebuild_content()

    def _on_text_color_selected(self, color):
        self._current_text_color = color
        self._apply_to_all(text_color=color)
        self._rebuild_content()

    def _rebuild_content(self):
        """Rebuild content to update swatch selection indicators."""
        child = self._content_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._content_box.remove(child)
            child = next_child
        self._create_content()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        # Let Enter pass through to the text view for newlines
        if keyval == Gdk.KEY_Return:
            if hasattr(self, "_text_view") and self._text_view.has_focus():
                return False
            self._apply_and_close()
            return True
        return super()._on_key_pressed(controller, keyval, keycode, state)

    def _apply_and_close(self):
        """Commit current state — prevent rollback on close."""
        self._committed = True
        self.close()

    def _cancel(self):
        """Rollback all changes to original values for every shape."""
        for shape in self._shapes:
            orig = self._originals[shape.id]
            rollback = {}
            if shape.fill_color != orig["fill_color"]:
                rollback["fill_color"] = orig["fill_color"]
            if shape.text_color != orig["text_color"]:
                rollback["text_color"] = orig["text_color"]
            if (shape.font_size or 14) != orig["font_size"]:
                rollback["font_size"] = orig["font_size"]
            if "text" in orig and hasattr(shape, "text"):
                if shape.text != orig.get("text"):
                    rollback["text"] = orig["text"]
            if "width" in orig and shape.width != orig["width"]:
                rollback["width"] = orig["width"]
            if "height" in orig and shape.height != orig["height"]:
                rollback["height"] = orig["height"]
            if rollback:
                self._on_apply(shape.id, **rollback)
        self._committed = True
        self.close()

    def close(self):
        """On close (e.g. Escape), rollback unless committed."""
        if not self._committed:
            self._cancel()
            return
        super().close()
