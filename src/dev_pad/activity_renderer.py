"""
Activity renderer mixin for Dev Pad.

Contains UI setup, styling, and rendering methods used by the DevPad widget.
"""

from datetime import datetime

from gi.repository import Gdk, GLib, Gtk, Pango

from constants import DEFAULT_FONT_SIZE
from dev_pad.activity_store import _get_activity_icon, _get_sketch_preview
from dev_pad.dev_pad_storage import DevPadActivity
from fonts import get_font_settings
from icons import Icons, apply_icon_font, get_icon_font_name
from shared.settings import get_setting
from shared.ui import ZenButton
from shared.ui.zen_entry import ZenEntry
from themes import get_theme


class ActivityRendererMixin:
    """Mixin providing UI setup, styling, and rendering for DevPad."""

    def _get_font_settings(self):
        """Get font settings from config (uses editor fonts)."""
        settings = get_font_settings("editor")
        family = settings["family"]
        size = settings.get("size", DEFAULT_FONT_SIZE)
        weight = settings.get("weight", "normal")
        return family, size, weight

    @staticmethod
    def _apply_nerd_font(label: Gtk.Label, size_pt: int | None = None) -> None:
        """Apply icon font family to a label via Pango attributes."""
        apply_icon_font(label, size_pt)

    def apply_font_settings(self):
        """Re-apply font settings (called after zoom changes)."""
        self._apply_styles()

    def _setup_ui(self):
        """Create the Dev Pad UI."""
        family, size, weight = self._get_font_settings()

        # Row 1: search box with filters inside on the right
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        search_row.set_margin_start(10)
        search_row.set_margin_end(10)
        search_row.set_margin_top(10)
        search_row.set_margin_bottom(5)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        search_box.set_hexpand(True)
        search_box.add_css_class("dev-pad-search-box")

        search_icon = Gtk.Label(label=Icons.SEARCH)
        search_icon.add_css_class("dev-pad-icon")
        search_icon.add_css_class("dev-pad-search-icon")
        self._apply_nerd_font(search_icon, size)
        search_box.append(search_icon)

        self.search_entry = ZenEntry(placeholder="Search recent activities and quick links")
        self.search_entry.set_hexpand(True)
        self.search_entry.add_css_class("dev-pad-search")
        self.search_entry.connect("changed", self._on_search_change)
        search_box.append(self.search_entry)

        # Filter buttons inside search box (right side)
        self._filter_buttons = {}
        filter_options = [
            ("All", None, None),
            ("PRs", {"github_pr"}, Icons.GIT_MERGE),
            ("Notes", {"note"}, Icons.PIN),
            ("Sketches", {"sketch"}, Icons.PENCIL),
        ]

        for text, filter_types, icon in filter_options:
            btn = ZenButton(icon=icon, label=text) if icon else ZenButton(label=text)
            btn.add_css_class("dev-pad-filter-btn")
            if filter_types == self._type_filter:
                btn.add_css_class("dev-pad-filter-active")
            btn.connect("clicked", lambda b, ft=filter_types: self._on_filter_click(ft))
            search_box.append(btn)
            key = str(filter_types) if filter_types else "all"
            self._filter_buttons[key] = btn

        search_row.append(search_box)
        self.append(search_row)

        # Row 2: action buttons below the search row
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_bar.set_margin_start(10)
        action_bar.set_margin_end(10)
        action_bar.set_margin_bottom(5)

        # Add Note button
        self.add_note_btn = ZenButton(icon=Icons.PLUS, label="Note")
        self.add_note_btn.add_css_class("dev-pad-btn")
        self.add_note_btn.connect("clicked", self._on_add_note)
        action_bar.append(self.add_note_btn)

        # Add Sketch button
        self.add_sketch_btn = ZenButton(icon=Icons.PLUS, label="Sketch")
        self.add_sketch_btn.add_css_class("dev-pad-btn")
        self.add_sketch_btn.connect("clicked", self._on_add_sketch)
        action_bar.append(self.add_sketch_btn)

        # Refresh PRs button
        self.refresh_prs_btn = ZenButton(icon=Icons.GIT_MERGE, label="Refresh PRs")
        self.refresh_prs_btn.add_css_class("dev-pad-btn-dim")
        self.refresh_prs_btn.connect("clicked", self._on_refresh_prs)
        action_bar.append(self.refresh_prs_btn)

        # Clear All button
        self.clear_btn = ZenButton(label="Clear All")
        self.clear_btn.add_css_class("dev-pad-btn-dim")
        self.clear_btn.connect("clicked", self._on_clear_all)
        action_bar.append(self.clear_btn)

        self.append(action_bar)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(sep)

        # Scrollable content area
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_window.set_vexpand(True)
        self.append(self.scrolled_window)

        # Content box for activities
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.content_box.set_margin_start(10)
        self.content_box.set_margin_end(10)
        self.content_box.set_margin_top(5)
        self.content_box.set_margin_bottom(10)
        self.scrolled_window.set_child(self.content_box)

    def _apply_styles(self):
        """Apply Dev Pad styles."""
        theme = get_theme()
        family, size, weight = self._get_font_settings()

        # Convert weight to CSS value
        css_weight = "bold" if weight == "bold" else ("300" if weight == "light" else "normal")

        nerd_font = get_icon_font_name()

        css_provider = Gtk.CssProvider()
        css = f"""
            .dev-pad-btn {{
                background-color: transparent;
                color: {theme.accent_color};
                border: none;
                padding: 4px 8px;
            }}
            .dev-pad-btn label {{
                font-family: "{family}";
                font-size: {size - 1}pt;
            }}
            .dev-pad-btn:hover {{
                color: {theme.selection_bg};
            }}
            .dev-pad-btn-dim {{
                background-color: transparent;
                color: {theme.fg_dim};
                border: none;
                padding: 4px 8px;
            }}
            .dev-pad-btn-dim label {{
                font-family: "{family}";
                font-size: {size - 1}pt;
            }}
            .dev-pad-btn-dim:hover {{
                color: {theme.accent_color};
            }}
            .dev-pad-close-btn {{
                background-color: transparent;
                color: {theme.fg_dim};
                border: none;
                padding: 4px;
            }}
            .dev-pad-close-btn label {{
                font-family: "{nerd_font}", "{family}";
                font-size: {size}pt;
            }}
            .dev-pad-close-btn:hover {{
                color: {theme.accent_color};
            }}
            .dev-pad-search-box {{
                background-color: {theme.main_bg};
                border: 1px solid {theme.border_color};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            .dev-pad-search-box:focus-within {{
                border-color: {theme.accent_color};
            }}
            .dev-pad-search-icon {{
                font-family: "{nerd_font}", "{family}";
                color: {theme.fg_dim};
                font-size: {size}pt;
            }}
            .dev-pad-search {{
                font-family: "{family}";
                font-size: {size}pt;
                background: none;
                color: {theme.fg_color};
                border: none;
                box-shadow: none;
                outline: none;
                padding: 2px 4px;
            }}
            .dev-pad-filter-label {{
                font-family: "{family}";
                color: {theme.fg_dim};
                font-size: {size - 1}pt;
            }}
            .dev-pad-filter-btn {{
                background-color: transparent;
                color: {theme.fg_dim};
                border: none;
                padding: 4px 8px;
            }}
            .dev-pad-filter-btn label {{
                font-family: "{nerd_font}", "{family}";
                font-size: {size - 1}pt;
            }}
            .dev-pad-filter-btn:hover {{
                color: {theme.accent_color};
            }}
            .dev-pad-filter-active {{
                color: {theme.accent_color};
            }}
            .dev-pad-date {{
                font-family: "{family}";
                font-weight: bold;
                font-size: {size}pt;
                color: {theme.accent_color};
                margin-top: 10px;
                margin-bottom: 5px;
            }}
            .dev-pad-activity-row {{
                padding: 4px 0;
            }}
            .dev-pad-activity-row:hover {{
                background-color: {theme.hover_bg};
            }}
            .dev-pad-delete-btn {{
                color: {theme.fg_dim};
                min-width: 20px;
                min-height: 20px;
            }}
            .dev-pad-delete-btn:hover {{
                color: {theme.accent_color};
            }}
            .dev-pad-time {{
                font-family: "{family}";
                color: {theme.fg_dim};
                font-size: {size - 1}pt;
            }}
            .dev-pad-icon {{
                font-family: "{nerd_font}", "{family}";
                color: {theme.fg_color};
            }}
            .dev-pad-link {{
                font-family: "{family}";
                font-size: {size}pt;
                font-weight: {css_weight};
                color: {theme.accent_color};
            }}
            .dev-pad-link:hover {{
                text-decoration: underline;
            }}
            .dev-pad-text {{
                font-family: "{family}";
                font-size: {size}pt;
                font-weight: {css_weight};
                color: {theme.fg_color};
            }}
            .dev-pad-desc {{
                font-family: "{family}";
                color: {theme.fg_dim};
                font-size: {size - 1}pt;
                margin-left: 25px;
            }}
            .dev-pad-desc-quote {{
                font-family: "{family}";
                color: {theme.fg_dim};
                font-size: {size - 1}pt;
                margin-left: 25px;
                padding-left: 8px;
                padding-top: 4px;
                padding-bottom: 4px;
                border-left: 2px solid {theme.accent_color};
            }}
            .dev-pad-empty {{
                font-family: "{family}";
                color: {theme.fg_dim};
                margin: 20px;
            }}
            .dev-pad-sketch-preview {{
                font-family: "{family}";
                font-size: {size - 2}pt;
                color: {theme.fg_dim};
                background-color: {theme.main_bg};
                border: 1px solid {theme.border_color};
                border-radius: 4px;
                padding: 6px 8px;
                margin-left: 25px;
                margin-top: 2px;
                margin-bottom: 2px;
            }}
        """
        css_provider.load_from_data(css.encode())

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _refresh(self):
        """Refresh the activity list.

        Builds the first batch of rows synchronously for instant feedback,
        then appends remaining rows in idle callbacks so the main loop stays
        responsive and the window can render between batches.
        """
        # Cancel any in-flight incremental refresh
        if hasattr(self, "_refresh_pending") and self._refresh_pending:
            GLib.source_remove(self._refresh_pending)
            self._refresh_pending = None

        # Clear existing content
        while True:
            child = self.content_box.get_first_child()
            if child:
                self.content_box.remove(child)
            else:
                break

        self._activity_links.clear()
        self._link_tag_counter = 0

        # Get activities grouped by date
        max_activities = get_setting("dev_pad.max_activities", 500)
        grouped = self._storage.get_activities_grouped_by_date(
            limit=max_activities, filter_query=self._search_query, type_filter=self._type_filter
        )

        if not grouped:
            # Show empty state
            empty_label = Gtk.Label(label="\n\nNo activities yet.\n\nAs you work, your activities will appear here.")
            empty_label.set_halign(Gtk.Align.CENTER)
            empty_label.add_css_class("dev-pad-empty")
            self.content_box.append(empty_label)
            return

        # Flatten into (widget_factory) work items — date headers + activity rows
        work_items: list = []
        for date_key, activities in grouped.items():
            work_items.append(("date", date_key))
            for activity in activities:
                work_items.append(("row", activity))

        # Build first batch synchronously for instant feedback
        SYNC_BATCH = 20
        self._build_rows(work_items[:SYNC_BATCH])

        # Schedule remaining rows in idle batches
        remaining = work_items[SYNC_BATCH:]
        if remaining:
            BATCH_SIZE = 30

            def _build_next_batch():
                self._refresh_pending = None
                batch = remaining[:BATCH_SIZE]
                del remaining[:BATCH_SIZE]
                self._build_rows(batch)
                if remaining:
                    self._refresh_pending = GLib.idle_add(_build_next_batch)
                return False

            self._refresh_pending = GLib.idle_add(_build_next_batch)

    def _build_rows(self, items):
        """Append a batch of date headers and activity rows to content_box."""
        for kind, data in items:
            if kind == "date":
                date_label = Gtk.Label(label=data)
                date_label.set_halign(Gtk.Align.START)
                date_label.add_css_class("dev-pad-date")
                self.content_box.append(date_label)
            else:
                row = self._create_activity_row(data)
                self.content_box.append(row)

    def _create_activity_row(self, activity: DevPadActivity) -> Gtk.Box:
        """Create a row widget for an activity."""
        # Main row container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        main_box.add_css_class("dev-pad-activity-row")

        # Top row: delete, time, icon, title
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Delete icon as a label with click gesture (not Gtk.Button to avoid
        # button CSS overriding the nerd font — same pattern as TabButton)
        del_icon = Gtk.Label(label=Icons.CLOSE)
        del_icon.add_css_class("dev-pad-icon")
        del_icon.add_css_class("dev-pad-delete-btn")
        del_icon.set_cursor_from_name("pointer")
        _, icon_size, _ = self._get_font_settings()
        self._apply_nerd_font(del_icon, icon_size)
        del_click = Gtk.GestureClick.new()
        del_click.connect("released", lambda g, n, x, y, a=activity: self._on_delete_activity(a))
        del_icon.add_controller(del_click)
        top_row.append(del_icon)

        # Time
        try:
            dt = datetime.fromisoformat(activity.timestamp)
            time_str = dt.strftime("%H:%M")
        except Exception:
            time_str = "     "

        time_label = Gtk.Label(label=time_str)
        time_label.add_css_class("dev-pad-time")
        top_row.append(time_label)

        # Icon
        icon = _get_activity_icon(activity.activity_type)
        icon_label = Gtk.Label(label=icon)
        icon_label.add_css_class("dev-pad-icon")
        _, icon_size, _ = self._get_font_settings()
        self._apply_nerd_font(icon_label, icon_size)
        top_row.append(icon_label)

        # Title (clickable if link_target is set)
        if activity.link_target:
            # Use a label with click gesture for proper wrapping
            title_label = Gtk.Label(label=activity.title)
            title_label.add_css_class("dev-pad-link")
            title_label.set_hexpand(True)
            title_label.set_halign(Gtk.Align.START)
            title_label.set_wrap(True)
            title_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            title_label.set_xalign(0)

            # Store activity reference
            self._link_tag_counter += 1
            tag = f"link_{self._link_tag_counter}"
            self._activity_links[tag] = activity

            top_row.append(title_label)
        else:
            title_label = Gtk.Label(label=activity.title)
            title_label.add_css_class("dev-pad-text")
            title_label.set_hexpand(True)
            title_label.set_halign(Gtk.Align.START)
            title_label.set_wrap(True)
            title_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            title_label.set_xalign(0)
            top_row.append(title_label)

        main_box.append(top_row)

        # Make the entire row clickable if there is a link target
        if activity.link_target:
            main_box.set_cursor_from_name("pointer")
            row_click = Gtk.GestureClick.new()
            row_click.connect("released", lambda g, n, x, y, a=activity: self._on_link_click(a))
            main_box.add_controller(row_click)

        # Sketch preview (for sketch activities with content in metadata)
        if activity.activity_type == "sketch" and activity.metadata.get("content"):
            preview_text = _get_sketch_preview(activity.metadata["content"])
            if preview_text:
                preview_label = Gtk.Label(label=preview_text)
                preview_label.set_halign(Gtk.Align.START)
                preview_label.add_css_class("dev-pad-sketch-preview")
                preview_label.set_xalign(0)
                main_box.append(preview_label)
        # Description (if different from title)
        elif activity.description and activity.description != activity.title:
            desc_label = Gtk.Label(label=activity.description)
            desc_label.set_halign(Gtk.Align.START)
            if activity.activity_type in ("ai_chat", "ai_question"):
                desc_label.add_css_class("dev-pad-desc-quote")
            else:
                desc_label.add_css_class("dev-pad-desc")
            desc_label.set_wrap(True)
            desc_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            desc_label.set_xalign(0)
            main_box.append(desc_label)

        return main_box
