"""
Sketch Pad – ASCII diagram editor.
Provides rectangle, arrow, and select tools on a character grid.
"""

import platform

from gi.repository import Gdk, Gio, GLib, Gtk

from constants import SKETCH_TOOL_BTN_SIZE, SKETCH_TOOL_ICON_SIZE
from fonts.font_manager import get_font_settings
from icons import Icons, get_icon_font_name
from sketch_pad.global_settings_popup import GlobalDiagramSettingsPopup
from sketch_pad.sketch_canvas import SketchCanvas
from sketch_pad.sketch_model import ArrowLineStyle, ArrowShape, Board, ToolMode
from themes import subscribe_theme_change, unsubscribe_theme_change

_MOD = Gdk.ModifierType.META_MASK if platform.system() == "Darwin" else Gdk.ModifierType.CONTROL_MASK


class SketchPad(Gtk.Box):
    """ASCII diagram editor – 3 tools: Select, Rectangle, Arrow."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._board = Board()
        self._syncing_tool = False

        self._setup_ui()
        self._apply_styles()
        self._apply_theme_colors()

        subscribe_theme_change(self._on_theme_change)

    # ───────────────────────── UI setup ─────────────────────────

    @staticmethod
    def _make_btn(icon: str, tooltip: str, toggle: bool = False) -> Gtk.Button:
        """Create a toolbar button with a properly centered icon label."""
        from shared.ui import ZenButton

        btn = ZenButton(
            icon=icon,
            tooltip=tooltip,
            toggle=toggle,
            icon_size=SKETCH_TOOL_ICON_SIZE,
        )
        btn.add_css_class("sketch-tool-btn")
        return btn

    def _setup_ui(self):
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_start(6)
        toolbar.set_margin_end(6)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)
        toolbar.add_css_class("sketch-toolbar")
        self.append(toolbar)

        # Tool buttons grouped: non-shape tools left, shape tools middle
        self._tool_buttons: dict[str, Gtk.ToggleButton] = {}
        non_shape_tools = [
            ("select", "Select (V)", Icons.TOOL_SELECT),
            ("pan", "Pan (H)", Icons.TOOL_PAN),
        ]
        shape_tools = [
            ("rectangle", "Rectangle (B)", Icons.TOOL_RECTANGLE),
            ("arrow", "Arrow (A)", Icons.TOOL_ARROW),
            ("topic", "Topic (T)", Icons.TOOL_TOPIC),
            ("database", "Database (D)", Icons.TOOL_DATABASE),
            ("cloud", "Cloud (C)", Icons.TOOL_CLOUD),
            ("actor", "Actor (P)", Icons.TOOL_ACTOR),
        ]
        for tool_id, tooltip, icon in non_shape_tools:
            btn = self._make_btn(icon, tooltip, toggle=True)
            btn.connect("toggled", self._on_tool_btn, tool_id)
            toolbar.append(btn)
            self._tool_buttons[tool_id] = btn

        # Zoom
        for icon, tip, delta in [
            (Icons.ZOOM_OUT, "Zoom Out", -0.1),
            (Icons.ZOOM_RESET, "Reset View (0,0 / 100%)", 0),
            (Icons.ZOOM_IN, "Zoom In", 0.1),
        ]:
            btn = self._make_btn(icon, tip)
            if delta == 0:
                btn.connect("clicked", lambda b: self._canvas_widget.zoom_reset())
            else:
                btn.connect("clicked", lambda b, d=delta: self._canvas_widget.zoom(d))
            toolbar.append(btn)

        # Delete
        del_btn = self._make_btn(Icons.DELETE, "Delete Selected (Del)")
        del_btn.connect("clicked", lambda b: self._delete_selected())
        toolbar.append(del_btn)

        toolbar.append(Gtk.Separator())

        for tool_id, tooltip, icon in shape_tools:
            btn = self._make_btn(icon, tooltip, toggle=True)
            btn.connect("toggled", self._on_tool_btn, tool_id)
            toolbar.append(btn)
            self._tool_buttons[tool_id] = btn

        self._tool_buttons["select"].set_active(True)

        toolbar.append(Gtk.Separator())

        # Global settings
        global_btn = self._make_btn(Icons.TOOL_SETTINGS, "Global diagram settings (fonts, sizes)")
        global_btn.connect("clicked", self._on_global_settings)
        toolbar.append(global_btn)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        # Export
        export_btn = self._make_btn(Icons.EXPORT, "Export as .zen_sketch, PNG or JPEG")
        export_btn.connect("clicked", self._on_export)
        toolbar.append(export_btn)

        # Import
        import_btn = self._make_btn(Icons.IMPORT, "Import .zen_sketch file")
        import_btn.connect("clicked", self._on_import)
        toolbar.append(import_btn)

        toolbar.append(Gtk.Separator())

        # Clear
        clear_btn = self._make_btn(Icons.ERASER, "Clear All")
        clear_btn.connect("clicked", self._on_clear)
        toolbar.append(clear_btn)

        # Status bar
        self._status_label = Gtk.Label(label="Col 0  Row 0  Zoom 100%")
        self._status_label.add_css_class("sketch-pos-label")

        # Canvas
        self._canvas_widget = SketchCanvas(
            self._board,
            on_status_change=self._on_status_change,
            on_tool_change=self._on_tool_change,
            on_dark_mode_change=self._on_dark_mode_change,
        )
        self._canvas_widget.set_hexpand(True)
        self._canvas_widget.set_vexpand(True)
        self.append(self._canvas_widget)

        # Bottom status bar
        status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_bar.set_margin_start(8)
        status_bar.set_margin_end(8)
        status_bar.set_margin_top(2)
        status_bar.set_margin_bottom(2)
        status_bar.append(self._status_label)
        self.append(status_bar)

        # Expose drawing area for focus tracking (expected by zen_ide.py)
        self._drawing_area = self._canvas_widget

    # ───────────────────────── Toolbar callbacks ─────────────────────────

    def _on_tool_btn(self, btn, tool_id: str):
        if not hasattr(self, "_canvas_widget"):
            return
        if self._syncing_tool:
            return
        # Arrow button re-click: cycle line style instead of deactivating
        if tool_id == "arrow" and not btn.get_active():
            if self._canvas_widget.tool == ToolMode.ARROW:
                btn.set_active(True)
                self._cycle_arrow_line_style()
                return
        if not btn.get_active():
            return
        for tid, tb in self._tool_buttons.items():
            if tid != tool_id:
                tb.set_active(False)
        tool_map = {
            "select": ToolMode.SELECT,
            "pan": ToolMode.PAN,
            "rectangle": ToolMode.RECTANGLE,
            "arrow": ToolMode.ARROW,
            "actor": ToolMode.ACTOR,
            "topic": ToolMode.TOPIC,
            "database": ToolMode.DATABASE,
            "cloud": ToolMode.CLOUD,
        }
        self._canvas_widget.tool = tool_map.get(tool_id, ToolMode.SELECT)

    def _on_tool_change(self, mode: ToolMode):
        """Sync toolbar toggle buttons when the canvas tool changes."""
        self._syncing_tool = True
        reverse_map = {
            ToolMode.SELECT: "select",
            ToolMode.PAN: "pan",
            ToolMode.RECTANGLE: "rectangle",
            ToolMode.ARROW: "arrow",
            ToolMode.ACTOR: "actor",
            ToolMode.TOPIC: "topic",
            ToolMode.DATABASE: "database",
            ToolMode.CLOUD: "cloud",
        }
        tool_id = reverse_map.get(mode, "select")
        for tid, tb in self._tool_buttons.items():
            tb.set_active(tid == tool_id)
        self._syncing_tool = False

    _LINE_STYLE_ICONS = {
        ArrowLineStyle.SOLID: Icons.TOOL_ARROW,
        ArrowLineStyle.DASHED: Icons.TOOL_ARROW,
        ArrowLineStyle.DOTTED: Icons.TOOL_ARROW_DOTTED,
    }
    _LINE_STYLE_TOOLTIPS = {
        ArrowLineStyle.SOLID: "Arrow – Solid ── (click to cycle)",
        ArrowLineStyle.DASHED: "Arrow – Dashed - - (click to cycle)",
        ArrowLineStyle.DOTTED: "Arrow – Dotted ·· (click to cycle)",
    }
    _LINE_STYLE_ORDER = [ArrowLineStyle.SOLID, ArrowLineStyle.DASHED, ArrowLineStyle.DOTTED]

    def _cycle_arrow_line_style(self):
        """Cycle arrow line style and update the arrow button icon."""
        cur = self._canvas_widget._arrow_line_style
        idx = self._LINE_STYLE_ORDER.index(cur)
        nxt = self._LINE_STYLE_ORDER[(idx + 1) % len(self._LINE_STYLE_ORDER)]
        self._canvas_widget._arrow_line_style = nxt
        self._sync_arrow_btn_icon(nxt)
        # Apply to selected arrows
        changed = False
        for shape in self._canvas_widget.selected_shapes:
            if isinstance(shape, ArrowShape):
                shape.line_style = nxt
                changed = True
        if changed:
            self._canvas_widget._snapshot_history()
            self._canvas_widget.queue_draw()

    def _sync_arrow_btn_icon(self, style: ArrowLineStyle):
        """Update the arrow button label and tooltip to reflect the line style."""
        btn = self._tool_buttons.get("arrow")
        if btn:
            btn.set_label(self._LINE_STYLE_ICONS[style])
            btn.set_tooltip_text(self._LINE_STYLE_TOOLTIPS[style])

    def _on_dark_mode_change(self, dark_mode: bool):
        """No-op: dark mode is now toggled via Settings popup or keyboard (M)."""
        pass

    def _on_status_change(self, col: int, row: int, zoom_pct: int):
        self._status_label.set_text(f"Col {col}  Row {row}  Zoom {zoom_pct}%")
        self._update_line_style_from_selection()

    def _update_line_style_from_selection(self):
        """Sync arrow button icon with selected arrow's style."""
        if not hasattr(self, "_canvas_widget"):
            return
        for shape in self._canvas_widget.selected_shapes:
            if isinstance(shape, ArrowShape):
                self._canvas_widget._arrow_line_style = shape.line_style
                self._sync_arrow_btn_icon(shape.line_style)
                return

    def _on_clear(self, *_):
        self._board.clear()
        self._canvas_widget._snapshot_history()
        self._canvas_widget._selected_ids.clear()
        self._canvas_widget.queue_draw()

    def _on_global_settings(self, *_):
        """Open the global diagram settings popup."""
        window = self.get_root()
        popup = GlobalDiagramSettingsPopup(window, self._board, self._canvas_widget, self._on_global_apply)
        popup.present()

    def _on_global_apply(self):
        """Called after global settings are applied."""
        self._canvas_widget._snapshot_history()
        self._canvas_widget.queue_draw()

    def _delete_selected(self):
        for sid in list(self._canvas_widget._selected_ids):
            self._board.remove_shape(sid)
        self._canvas_widget._selected_ids.clear()
        self._canvas_widget._snapshot_history()
        self._canvas_widget.queue_draw()

    def _on_export(self, *_):
        """Export sketch to a .zen_sketch, PNG, or JPEG file."""
        if self._board.is_empty():
            return
        window = self.get_root()
        dialog = Gtk.FileDialog()
        dialog.set_title("Export Sketch")
        dialog.set_initial_name("sketch")
        zen_filter = Gtk.FileFilter()
        zen_filter.set_name("Zen Sketch files (*.zen_sketch)")
        zen_filter.add_pattern("*.zen_sketch")
        png_filter = Gtk.FileFilter()
        png_filter.set_name("PNG images (*.png)")
        png_filter.add_pattern("*.png")
        jpeg_filter = Gtk.FileFilter()
        jpeg_filter.set_name("JPEG images (*.jpg, *.jpeg)")
        jpeg_filter.add_pattern("*.jpg")
        jpeg_filter.add_pattern("*.jpeg")
        all_filter = Gtk.FileFilter()
        all_filter.set_name("All supported (*.zen_sketch, *.png, *.jpg)")
        all_filter.add_pattern("*.zen_sketch")
        all_filter.add_pattern("*.png")
        all_filter.add_pattern("*.jpg")
        all_filter.add_pattern("*.jpeg")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(all_filter)
        filters.append(zen_filter)
        filters.append(png_filter)
        filters.append(jpeg_filter)
        dialog.set_filters(filters)
        dialog.save(window, None, self._on_export_done)

    def _on_export_done(self, dialog, result):
        """Handle export file dialog result."""
        try:
            file = dialog.save_finish(result)
            if file:
                path = file.get_path()
                lower = path.lower()
                if lower.endswith((".png", ".jpg", ".jpeg")):
                    saved = self._canvas_widget.export_to_image(path)
                    if saved:
                        pass
                else:
                    # Strip duplicated extensions (GTK may auto-append filter extension)
                    while path.endswith(".zen_sketch.zen_sketch"):
                        path = path[: -len(".zen_sketch")]
                    if not path.endswith(".zen_sketch"):
                        path += ".zen_sketch"
                    content = self._board.to_json()
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
                    # Log to Dev Pad
                    from dev_pad import log_sketch_activity

                    log_sketch_activity(content=content, file_path=path)
        except GLib.Error as e:
            # User cancelled the native dialog: expected, no action needed.
            if "Dismissed" not in str(e):
                from shared.crash_log import log_message

                log_message(f"Sketch export dialog failed: {e}")
        except OSError as e:
            from shared.crash_log import log_message

            log_message(f"Sketch export failed: {e}")

    def _on_import(self, *_):
        """Import a .zen_sketch file."""
        window = self.get_root()
        dialog = Gtk.FileDialog()
        dialog.set_title("Import Sketch")
        zen_filter = Gtk.FileFilter()
        zen_filter.set_name("Zen Sketch files (*.zen_sketch)")
        zen_filter.add_pattern("*.zen_sketch")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(zen_filter)
        dialog.set_filters(filters)
        dialog.open(window, None, self._on_import_done)

    def _on_import_done(self, dialog, result):
        """Handle import file dialog result."""
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.strip():
                    self.load_content(content)
                    # Log to Dev Pad
                    from dev_pad import log_sketch_activity

                    log_sketch_activity(content=content, file_path=path)
        except GLib.Error as e:
            # User cancelled the native dialog: expected, no action needed.
            if "Dismissed" not in str(e):
                from shared.crash_log import log_message

                log_message(f"Sketch import dialog failed: {e}")
        except OSError as e:
            from shared.crash_log import log_message

            log_message(f"Sketch import failed: {e}")

    # ───────────────────────── Theme ─────────────────────────

    def _on_theme_change(self, theme):
        self._apply_theme_colors()

    def _apply_theme_colors(self):
        if hasattr(self, "_canvas_widget"):
            self._canvas_widget.queue_draw()

    # ───────────────────────── Public API ─────────────────────────

    def get_content(self) -> str:
        return self._board.to_json()

    def load_content(self, text: str):
        text = text.strip()
        if not text:
            return
        if text.startswith("{"):
            try:
                restored = Board.from_json(text)
                self._board.shapes = restored.shapes
                self._board._next_z = restored._next_z
                self._canvas_widget._history.clear()
                self._canvas_widget._hist_idx = -1
                self._canvas_widget._snapshot_history()
                self._canvas_widget.queue_draw()
                return
            except Exception:
                pass

    def is_empty(self) -> bool:
        return self._board.is_empty()

    def undo(self):
        self._canvas_widget.undo()

    def redo(self):
        self._canvas_widget.redo()

    def show_panel(self):
        self.set_visible(True)
        self._canvas_widget.grab_focus()

    def hide_panel(self):
        self.set_visible(False)

    def _zoom(self, delta: float):
        self._canvas_widget.zoom(delta)

    def destroy(self):
        unsubscribe_theme_change(self._on_theme_change)

    # ───────────────────────── Styles ─────────────────────────

    def _apply_styles(self):
        font_settings = get_font_settings("editor")
        editor_family = font_settings["family"]
        editor_size = font_settings.get("size", 13)
        pos_label_size = max(9, editor_size - 2)

        nerd_font = get_icon_font_name()
        font_css = f'font-family: "{nerd_font}", "{editor_family}";'
        css = f"""
        .sketch-toolbar {{
            border-bottom: 1px solid alpha(@theme_fg_color, 0.1);
            padding: 2px 4px;
        }}
        .sketch-toolbar > button.flat.sketch-tool-btn {{
            min-width: {SKETCH_TOOL_BTN_SIZE}px;
            padding: 0;
            margin: 0;
        }}
        .sketch-toolbar separator {{
            min-width: 2px;
            background-color: white;
            margin: 4px 4px;
        }}
        .sketch-pos-label {{
            {font_css}
            font-size: {pos_label_size}px;
            opacity: 0.6;
        }}
        """.encode()
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
