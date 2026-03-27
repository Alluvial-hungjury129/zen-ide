"""CSS styles mixin for NvimPopup."""

from gi.repository import Gdk, Gtk

from shared.settings import get_setting
from themes import get_theme


class PopupStylesMixin:
    """Mixin providing _apply_styles() — CSS theme for all popup widgets."""

    def _apply_styles(self):
        """Apply Neovim-like styles to the popup."""
        theme = get_theme()
        font_family, font_size = self._get_popup_font()
        border_radius = get_setting("popup.border_radius", 0)

        from shared.utils import blend_hex_colors, ensure_text_contrast, hex_to_rgba_css

        # More translucent backgrounds (0.75 = 75% opacity)
        panel_bg_translucent = hex_to_rgba_css(theme.panel_bg, 0.75)
        main_bg_translucent = hex_to_rgba_css(theme.main_bg, 0.80)
        primary_button_bg = ensure_text_contrast(theme.accent_color, "#ffffff")
        primary_button_hover_bg = ensure_text_contrast(blend_hex_colors(primary_button_bg, "#000000", 0.08), "#ffffff")

        # Remove old provider before re-applying
        if self._css_provider:
            Gtk.StyleContext.remove_provider_for_display(
                Gdk.Display.get_default(),
                self._css_provider,
            )

        self._css_provider = Gtk.CssProvider()
        css = f"""
            /* Base window - match editor bg so any decoration pixels blend in */
            window.nvim-popup-window {{
                background-color: {theme.main_bg};
                font-family: "{font_family}";
                font-size: {font_size}pt;
                border-radius: {border_radius}px;
                border: none;
                box-shadow: none;
            }}

            window.nvim-popup-window.csd {{
                background-color: {theme.main_bg};
                border-radius: {border_radius}px;
                border: none;
                box-shadow: none;
            }}

            window.nvim-popup-window decoration,
            window.nvim-popup-window.csd decoration,
            window.nvim-popup-window.csd.popup decoration,
            window.nvim-popup-window.popup decoration {{
                all: unset;
                background: {theme.main_bg};
                background-color: {theme.main_bg};
                background-image: none;
                border: none;
                border-image: none;
                box-shadow: none;
                outline: none;
                margin: 0;
                padding: 0;
                min-height: 0;
                min-width: 0;
            }}

            window.nvim-popup-window decoration shadow {{
                all: unset;
                box-shadow: none;
                background: {theme.main_bg};
                margin: 0;
                padding: 0;
            }}

            window.nvim-popup-window.popup {{
                background-color: {theme.main_bg};
                border-radius: {border_radius}px;
                border: none;
                box-shadow: none;
                margin: 0;
                padding: 0;
            }}

            window.nvim-popup-window headerbar,
            window.nvim-popup-window .titlebar {{
                min-height: 0;
                border: none;
                box-shadow: none;
                background: {theme.main_bg};
                margin: 0;
                padding: 0;
            }}

            /* Remove all border-radius from child elements */
            window.nvim-popup-window * {{
                border-radius: {border_radius}px;
            }}

            /* Linux popover for anchor positioning — transparent chrome */
            popover.nvim-popup-popover,
            popover.nvim-popup-popover > contents {{
                background: transparent;
                background-color: transparent;
                border: none;
                box-shadow: none;
                padding: 0;
                margin: 0;
                min-height: 0;
                min-width: 0;
            }}

            /* Frame — no CSS border; border drawn by GtkSnapshot overlay */
            .nvim-popup-frame {{
                border-radius: {border_radius}px;
                background-color: {panel_bg_translucent};
            }}

            /* Title overlaid on the top border line — transparent background */
            .nvim-popup-title {{
                font-weight: 500;
                font-size: {font_size + 1}pt;
                color: {theme.accent_color};
                background-color: transparent;
                padding: 0 8px;
            }}

            .nvim-popup-separator {{
                background-color: {theme.border_color};
                min-height: 1px;
            }}

            /* Content styling */
            .nvim-popup-message {{
                color: {theme.fg_color};
            }}

            .nvim-popup-hint {{
                color: {theme.fg_dim};
                font-size: {int(font_size * 0.85)}pt;
            }}

            /* Input field - slightly translucent */
            .nvim-popup-input {{
                background-color: {main_bg_translucent};
                color: {theme.fg_color};
                border: 1px solid {theme.border_color};
                border-radius: {border_radius}px;
                padding: 8px;
                font-family: "{font_family}";
                outline: none;
                outline-width: 0;
            }}

            .nvim-popup-input:focus-within {{
                border-color: {theme.accent_color};
                outline: none;
                outline-width: 0;
            }}

            .nvim-popup-input > text {{
                outline: none;
                outline-width: 0;
                background: transparent;
                border: none;
                font-family: "{font_family}";
                font-size: {font_size}pt;
                color: {theme.fg_color};
            }}

            /* List styling */
            .nvim-popup-list {{
                background-color: transparent;
                border-radius: {border_radius}px;
            }}

            .nvim-popup-list row {{
                border-radius: {border_radius}px;
                outline: none;
            }}

            .nvim-popup-list row:focus,
            .nvim-popup-list row:focus-visible {{
                outline: none;
            }}

            .nvim-popup-list row:selected {{
                background-color: {theme.selection_bg};
                border-radius: {border_radius}px;
                outline: none;
            }}

            .nvim-popup-list row:hover {{
                background-color: {theme.hover_bg};
                border-radius: {border_radius}px;
            }}

            .nvim-popup-list-item {{
                padding: 3px 8px;
                border-radius: {border_radius}px;
                outline: none;
            }}

            .nvim-popup-list-item:focus,
            .nvim-popup-list-item:focus-visible {{
                outline: none;
            }}

            .nvim-popup-list-item:selected {{
                background-color: {theme.selection_bg};
                border-radius: {border_radius}px;
                outline: none;
            }}

            .nvim-popup-list-item:hover {{
                background-color: {theme.hover_bg};
                border-radius: {border_radius}px;
            }}

            /* Override text colors on selected rows for readability */
            .nvim-popup-list row:selected label,
            .nvim-popup-list-item:selected label {{
                color: {theme.fg_color};
            }}

            .nvim-popup-list row:selected .nvim-popup-keybind,
            .nvim-popup-list-item:selected .nvim-popup-keybind {{
                color: {theme.fg_color};
                background-color: transparent;
                border-color: {theme.fg_dim};
            }}

            .nvim-popup-list-item-text {{
                color: {theme.fg_color};
                font-family: "{self._get_icon_font()}", "{font_family}", system-ui;
            }}

            .nvim-popup-list-item-hint {{
                color: {theme.fg_dim};
                font-size: {int(font_size * 0.9)}pt;
            }}

            .nvim-popup-file-header-box {{
                background-color: rgba(255, 0, 0, 0.25);
                border-radius: {border_radius}px;
                padding: 4px 8px;
            }}

            .nvim-popup-list-item-icon {{
                color: {theme.accent_color};
                margin-right: 8px;
                font-size: {font_size}pt;
                font-family: "{self._get_icon_font()}", "{font_family}", system-ui;
            }}

            /* Button styling */
            .nvim-popup-button {{
                background-color: {theme.main_bg};
                color: {theme.fg_color};
                border: 1px solid {theme.border_color};
                border-radius: {border_radius}px;
                padding: 4px 12px;
                min-width: 70px;
                font-family: "{font_family}";
                font-size: {font_size}pt;
            }}

            .nvim-popup-button > label {{
                font-family: "{font_family}";
                font-size: {font_size}pt;
            }}

            .nvim-popup-button:hover {{
                background-color: {theme.hover_bg};
            }}

            .nvim-popup-button-primary {{
                background-color: {primary_button_bg};
                color: #ffffff;
                border: none;
                font-weight: bold;
            }}

            .nvim-popup-button-primary:hover {{
                background-color: {primary_button_hover_bg};
            }}

            .nvim-popup-button-primary:focus,
            .nvim-popup-button-primary:focus-visible {{
                background-color: {primary_button_bg};
                color: #ffffff;
                outline: 2px solid {theme.fg_color};
                outline-offset: 2px;
            }}

            .nvim-popup-button-danger {{
                background-color: {theme.git_deleted};
                color: white;
                border: none;
            }}

            .nvim-popup-button-danger:focus,
            .nvim-popup-button-danger:focus-visible {{
                background-color: {theme.git_deleted};
                color: white;
                outline: 2px solid {theme.fg_color};
                outline-offset: 2px;
            }}

            .nvim-popup-button:focus,
            .nvim-popup-button:focus-visible {{
                outline: 2px solid {theme.accent_color};
                outline-offset: 2px;
            }}

            /* DropDown styling (e.g. project filter, AI settings combos) */
            .nvim-popup-window dropdown {{
                font-family: "{font_family}";
                font-size: {font_size}pt;
            }}

            .nvim-popup-window dropdown > button {{
                font-family: "{font_family}";
                font-size: {font_size}pt;
                background-color: {theme.main_bg};
                color: {theme.fg_color};
                border: 1px solid {theme.border_color};
                border-radius: {border_radius}px;
                padding: 4px 12px;
            }}

            .nvim-popup-window dropdown > button > box > label {{
                font-family: "{font_family}";
                font-size: {font_size}pt;
            }}

            /* DropDown popover — the results list that opens when you click the combo.
               GTK4 renders the dropdown items in a separate popover window,
               so we must target it globally (not scoped under .nvim-popup-window). */
            dropdown popover {{
                font-family: "{font_family}";
                font-size: {int(font_size * 0.85)}pt;
            }}

            dropdown popover > contents {{
                background-color: {theme.panel_bg};
                border: 1px solid {theme.border_color};
                border-radius: {border_radius}px;
            }}

            dropdown popover listview {{
                font-family: "{font_family}";
                font-size: {int(font_size * 0.85)}pt;
                background-color: transparent;
            }}

            dropdown popover listview > row {{
                font-family: "{font_family}";
                font-size: {int(font_size * 0.85)}pt;
                background-color: transparent;
                color: {theme.fg_color};
                border-radius: {border_radius}px;
                outline: none;
            }}

            dropdown popover listview > row:selected {{
                background-color: {theme.selection_bg};
                border-radius: {border_radius}px;
                outline: none;
            }}

            dropdown popover listview > row:hover {{
                background-color: {theme.hover_bg};
                border-radius: {border_radius}px;
            }}

            dropdown popover listview > row > cell {{
                font-family: "{font_family}";
                font-size: {int(font_size * 0.85)}pt;
                color: {theme.fg_color};
            }}

            dropdown popover listview > row > cell > label {{
                font-family: "{font_family}";
                font-size: {int(font_size * 0.85)}pt;
                color: {theme.fg_color};
            }}

            dropdown popover listview > row label {{
                font-family: "{font_family}";
                font-size: {int(font_size * 0.85)}pt;
                color: {theme.fg_color};
            }}

            dropdown popover listview > row:selected label {{
                color: {theme.fg_color};
            }}

            /* Also style the checkmark/indicator in DropDown rows */
            dropdown popover listview > row image {{
                color: {theme.accent_color};
            }}

            /* Keybind hint */
            .nvim-popup-keybind {{
                font-family: "{font_family}";
                font-size: {int(font_size * 0.85)}pt;
                color: {theme.fg_dim};
                background-color: {theme.main_bg};
                padding: 2px 6px;
                border-radius: {border_radius}px;
                border: 1px solid {theme.border_color};
            }}

            /* File name/path styling */
            .nvim-popup-file-name {{
                font-weight: 500;
                color: {theme.fg_color};
            }}

            .nvim-popup-file-path {{
                color: {theme.fg_dim};
                font-size: {int(font_size * 0.9)}pt;
            }}

            row:selected .nvim-popup-file-name,
            row:selected .nvim-popup-file-path {{
                color: {theme.fg_color};
            }}

            /* Search entry - slightly translucent */
            .nvim-popup-search {{
                background-color: {main_bg_translucent};
                color: {theme.fg_color};
                border: 1px solid {theme.border_color};
                border-radius: {border_radius}px;
                padding: 8px;
                font-family: "{font_family}";
                outline: none;
                outline-width: 0;
            }}

            .nvim-popup-search:focus-within {{
                border-color: {theme.accent_color};
                border-radius: {border_radius}px;
                outline: none;
                outline-width: 0;
            }}

            .nvim-popup-search > text {{
                outline: none;
                outline-width: 0;
                background: transparent;
                border: none;
            }}

            /* ScrolledWindow and all children */
            scrolledwindow {{ border-radius: {border_radius}px; }}
            scrolledwindow undershoot {{ border-radius: {border_radius}px; }}
            scrolledwindow overshoot {{ border-radius: {border_radius}px; }}
            listbox {{ border-radius: {border_radius}px; }}
            listbox row {{ border-radius: {border_radius}px; outline: none; }}
            listbox row:focus,
            listbox row:focus-visible {{ outline: none; }}

            /* ListView selection (used by FontPickerDialog etc.) */
            .nvim-popup-list > row:selected {{
                background-color: {theme.selection_bg};
                border-radius: {border_radius}px;
                outline: none;
            }}

            .nvim-popup-list > row:hover {{
                background-color: {theme.hover_bg};
                border-radius: {border_radius}px;
            }}

            /* Status/count label */
            .nvim-popup-status {{
                color: {theme.fg_dim};
                font-size: {int(font_size * 0.85)}pt;
            }}
        """
        self._css_provider.load_from_data(css.encode())

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )
