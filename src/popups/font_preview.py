"""
Font preview widget for Zen IDE.
Provides font listing, filtering, and list view setup for the font picker.
"""

from pathlib import Path
from typing import List

from gi.repository import Gio, GObject, Gtk

from shared.utils import get_pango_font_map


def _get_resources_fonts() -> List[str]:
    """Get font family names from the resources folder.

    Reads actual font family names registered with the OS font system
    (via CoreText on macOS, fontconfig on Linux).

    Returns:
        List of unique font family names found in resources.
    """
    resources_path = Path(__file__).parent.parent.parent / "resources"
    if not resources_path.exists():
        return []

    font_files = list(resources_path.glob("*.ttf")) + list(resources_path.glob("*.otf"))
    if not font_files:
        return []

    # Get the set of font stems from resource files (without weight suffix)
    resource_stems = set()
    for font_file in font_files:
        name = font_file.stem
        for suffix in (
            "-Bold",
            "-Light",
            "-Regular",
            "-Medium",
            "-Thin",
            "-ExtraBold",
            "-ExtraLight",
            "-SemiBold",
            "-Italic",
            "-BoldItalic",
            "-LightItalic",
            "-MediumItalic",
            "-ThinItalic",
            "-ExtraBoldItalic",
            "-ExtraLightItalic",
            "-SemiBoldItalic",
        ):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        resource_stems.add(name.lower())

    # Match against actual Pango font families
    font_families = set()
    try:
        font_map = get_pango_font_map()
        for family in font_map.list_families():
            family_name = family.get_name()
            # Check if this Pango family matches a resource font stem
            normalized = family_name.replace(" ", "").lower()
            if normalized in resource_stems:
                font_families.add(family_name)
    except Exception:
        pass

    return sorted(font_families)


def _get_all_system_fonts() -> List[str]:
    """Get all fonts available on the system.

    Returns:
        Sorted list of font family names.
    """
    try:
        font_map = get_pango_font_map()
        families = font_map.list_families()
        return sorted([f.get_name() for f in families], key=str.lower)
    except Exception:
        return []


def _get_all_fonts() -> List[str]:
    """Get combined list of all fonts (system + resources)."""
    fonts = set()

    # Add all system fonts
    fonts.update(_get_all_system_fonts())

    # Add resources fonts
    fonts.update(_get_resources_fonts())

    return sorted(fonts, key=str.lower)


class FontItem(GObject.Object):
    """A font item for the list store."""

    def __init__(self, name: str):
        super().__init__()
        self._name = name

    @property
    def name(self) -> str:
        return self._name


class FontPreviewMixin:
    """Font list/preview widget methods mixed into FontPickerDialog."""

    def _init_font_data(self):
        """Initialize font data and stores. Called from __init__."""
        self.all_fonts = _get_all_fonts()
        self.filtered_fonts = list(self.all_fonts)

        # Create the font list store
        self._font_store = Gio.ListStore.new(FontItem)
        self._filter_model = None
        self._selection_model = None

    def _create_font_list_widgets(self):
        """Create and return the font list UI widgets. Called from _create_content."""
        # Populate the font store
        for font in self.all_fonts:
            self._font_store.append(FontItem(font))

        # Create filter model
        self._filter_model = Gtk.FilterListModel(model=self._font_store)
        self._custom_filter = Gtk.CustomFilter.new(self._filter_func, None)
        self._filter_model.set_filter(self._custom_filter)

        # Create selection model
        self._selection_model = Gtk.SingleSelection(model=self._filter_model)
        self._selection_model.connect("selection-changed", self._on_font_selected)

        # Create list view with factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup)
        factory.connect("bind", self._on_factory_bind)

        # Font list in scrolled window
        self.font_list = Gtk.ListView(model=self._selection_model, factory=factory)
        self.font_list.add_css_class("nvim-popup-list")

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.font_list)
        scroll.set_vexpand(True)
        scroll.set_min_content_height(200)
        scroll.set_max_content_height(250)
        return scroll

    def _filter_func(self, item, user_data) -> bool:
        """Filter function for the font list."""
        search_text = self.search_entry.get_text().lower()
        if not search_text:
            return True
        return search_text in item.name.lower()

    def _on_factory_setup(self, factory, list_item):
        """Setup callback for list item factory."""
        name_label = Gtk.Label()
        name_label.set_halign(Gtk.Align.START)
        name_label.set_margin_start(10)
        name_label.set_margin_end(10)
        name_label.set_margin_top(4)
        name_label.set_margin_bottom(4)

        list_item.set_child(name_label)

    def _on_factory_bind(self, factory, list_item):
        """Bind callback for list item factory."""
        name_label = list_item.get_child()
        item = list_item.get_item()
        name_label.set_text(item.name)

    def _on_search_changed(self, entry):
        """Filter font list based on search text."""
        # Reapply the filter
        self._custom_filter.changed(Gtk.FilterChange.DIFFERENT)

    def _on_font_selected(self, selection, position, n_items):
        """Handle font list selection change."""
        if not self._updating_ui:
            self._apply_preview()

    def _move_selection(self, delta: int):
        """Move font list selection up or down."""
        n_items = self._filter_model.get_n_items()
        if n_items == 0:
            return
        current = self._selection_model.get_selected()
        if current == Gtk.INVALID_LIST_POSITION:
            new_pos = 0
        else:
            new_pos = max(0, min(n_items - 1, current + delta))
        self._selection_model.set_selected(new_pos)
        self.font_list.scroll_to(new_pos, Gtk.ListScrollFlags.NONE, None)
