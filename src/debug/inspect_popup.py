"""Inspect popup — shows widget introspection info in a NvimPopup."""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup


class InspectPopup(NvimPopup):
    """Displays detailed widget introspection information."""

    def __init__(self, parent: Gtk.Window, info: dict):
        self._info = info
        super().__init__(
            parent,
            title="Inspector",
            width=480,
            height=-1,
            modal=False,
            steal_focus=True,
        )

    def _create_content(self):
        info = self._info

        # --- Widget type header ---
        type_label = Gtk.Label(label=info["full_type"])
        type_label.add_css_class("nvim-popup-title")
        type_label.set_halign(Gtk.Align.START)
        type_label.set_margin_bottom(4)
        type_label.set_selectable(False)
        type_label.set_focusable(False)
        self._content_box.append(type_label)

        css_name_label = Gtk.Label(label=f"CSS element: <{info['css_name']}>")
        css_name_label.add_css_class("nvim-popup-hint")
        css_name_label.set_halign(Gtk.Align.START)
        css_name_label.set_selectable(False)
        css_name_label.set_focusable(False)
        css_name_label.set_margin_bottom(8)
        self._content_box.append(css_name_label)

        # Scrollable area for all the details
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(500)
        scroll.set_propagate_natural_height(True)

        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scroll.set_child(details_box)

        # --- Sections ---

        # Identity
        self._add_section(details_box, "Identity")
        if info.get("widget_name"):
            self._add_row(details_box, "Name", info["widget_name"])
        if info.get("label_text"):
            text = info["label_text"]
            if len(text) > 80:
                text = text[:80] + "…"
            self._add_row(details_box, "Label", text)
        if info.get("tooltip"):
            self._add_row(details_box, "Tooltip", info["tooltip"])

        # CSS Classes
        if info.get("css_classes"):
            self._add_section(details_box, "CSS Classes")
            classes_str = "  ".join(f".{c}" for c in info["css_classes"])
            cls_label = Gtk.Label(label=classes_str)
            cls_label.add_css_class("nvim-popup-message")
            cls_label.set_halign(Gtk.Align.START)
            cls_label.set_wrap(True)
            cls_label.set_margin_start(12)
            cls_label.set_margin_bottom(4)
            details_box.append(cls_label)

        # Size & Position
        self._add_section(details_box, "Geometry")
        alloc = info["allocation"]
        size = info["size"]
        self._add_row(details_box, "Position", f"({alloc['x']}, {alloc['y']})")
        self._add_row(details_box, "Allocation", f"{alloc['width']} × {alloc['height']}")
        self._add_row(details_box, "Rendered", f"{size['width']} × {size['height']}")

        # Layout
        self._add_section(details_box, "Layout")
        self._add_row(details_box, "H-Align", info["halign"])
        self._add_row(details_box, "V-Align", info["valign"])
        self._add_row(details_box, "H-Expand", str(info["hexpand"]))
        self._add_row(details_box, "V-Expand", str(info["vexpand"]))

        margin = info["margin"]
        margin_vals = f"↑{margin['top']}  ↓{margin['bottom']}  ←{margin['start']}  →{margin['end']}"
        self._add_row(details_box, "Margin", margin_vals)

        # State
        self._add_section(details_box, "State")
        self._add_row(details_box, "Visible", str(info["visible"]))
        self._add_row(details_box, "Sensitive", str(info["sensitive"]))
        self._add_row(details_box, "Focusable", str(info["focusable"]))
        self._add_row(details_box, "Has Focus", str(info["has_focus"]))
        if info["opacity"] < 1.0:
            self._add_row(details_box, "Opacity", f"{info['opacity']:.2f}")

        # Theme Hints
        if info.get("theme_hints"):
            self._add_section(details_box, "Theme Colors")
            for prop_name, color_value in info["theme_hints"]:
                self._add_color_row(details_box, prop_name, color_value)

        # Chat Block (when inspecting AI chat content)
        if info.get("chat_block"):
            block = info["chat_block"]
            self._add_section(details_box, "Chat Block")

            block_type = block["type"]
            type_icons = {"user": "💬", "thinking": "🧠", "assistant": "🤖"}
            icon = type_icons.get(block_type, "📄")
            self._add_row(details_box, "Block Type", f"{icon} {block_type}")
            self._add_row(details_box, "Lines", f"{block['start_line']}–{block['end_line']}  ({block['line_count']} lines)")
            self._add_row(details_box, "Cursor Line", str(block["clicked_line"]))
            if block.get("fg_color"):
                self._add_color_row(details_box, "Foreground", block["fg_color"])
            if block.get("bg_color"):
                self._add_color_row(details_box, "Background", block["bg_color"])
            if block.get("preview"):
                preview = block["preview"]
                if len(preview) > 100:
                    preview = preview[:100] + "…"
                self._add_row(details_box, "Preview", preview)

        # Widget Hierarchy
        self._add_section(details_box, "Widget Hierarchy")
        for i, entry in enumerate(info.get("hierarchy", [])):
            indent = "  " * i
            prefix = "▸ " if i > 0 else "● "
            hier_label = Gtk.Label(label=f"{indent}{prefix}{entry}")
            hier_label.add_css_class("nvim-popup-hint")
            hier_label.set_halign(Gtk.Align.START)
            hier_label.set_margin_start(12)
            details_box.append(hier_label)

        self._content_box.append(scroll)

        # Hint bar
        spacer = Gtk.Box()
        spacer.set_margin_top(8)
        self._content_box.append(spacer)

        hint_bar = self._create_hint_bar([("Esc", "close"), ("q", "close")])
        self._content_box.append(hint_bar)

    def _add_section(self, box: Gtk.Box, title: str):
        label = Gtk.Label(label=title)
        label.add_css_class("nvim-popup-title")
        label.set_halign(Gtk.Align.START)
        label.set_margin_top(8)
        label.set_margin_bottom(2)
        box.append(label)

    def _add_row(self, box: Gtk.Box, key: str, value: str):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_start(12)
        row.set_margin_top(1)
        row.set_margin_bottom(1)

        key_label = Gtk.Label(label=f"{key}:")
        key_label.add_css_class("nvim-popup-hint")
        key_label.set_halign(Gtk.Align.START)
        key_label.set_width_chars(14)
        key_label.set_xalign(0)
        row.append(key_label)

        val_label = Gtk.Label(label=value)
        val_label.add_css_class("nvim-popup-message")
        val_label.set_halign(Gtk.Align.START)
        val_label.set_hexpand(True)
        val_label.set_wrap(True)
        row.append(val_label)

        box.append(row)

    def _add_color_row(self, box: Gtk.Box, prop_name: str, color_value: str):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_start(12)
        row.set_margin_top(1)
        row.set_margin_bottom(1)

        key_label = Gtk.Label(label=f"{prop_name}:")
        key_label.add_css_class("nvim-popup-hint")
        key_label.set_halign(Gtk.Align.START)
        key_label.set_width_chars(14)
        key_label.set_xalign(0)
        row.append(key_label)

        # Color swatch (CSS-based, no cairo)
        swatch = Gtk.Box()
        swatch.set_size_request(14, 14)
        swatch.set_valign(Gtk.Align.CENTER)
        swatch_css = Gtk.CssProvider()
        swatch_css.load_from_string(
            f"box {{ background-color: {color_value}; border: 1px solid rgba(255,255,255,0.3); min-width: 14px; min-height: 14px; }}"
        )
        swatch.get_style_context().add_provider(swatch_css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 200)
        row.append(swatch)

        val_label = Gtk.Label(label=color_value)
        val_label.add_css_class("nvim-popup-message")
        val_label.set_halign(Gtk.Align.START)
        row.append(val_label)

        box.append(row)

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        if keyval == Gdk.KEY_q:
            self._result = None
            self.close()
            return True
        return super()._on_key_pressed(controller, keyval, keycode, state)


def show_inspect_popup(parent: Gtk.Window, info: dict):
    """Show the inspect popup with widget info."""
    popup = InspectPopup(parent, info)
    popup.present()
    return popup
