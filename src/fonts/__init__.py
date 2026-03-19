"""Fonts package for Zen IDE - centralized font management."""

from fonts.font_manager import (
    CSS_WEIGHT_MAP,
    DEFAULT_FONT,
    DEFAULT_PROSE_FONT,
    PANGO_WEIGHT_MAP,
    FontManager,
    create_font_description,
    font_exists,
    get_default_editor_font,
    get_default_terminal_font,
    get_default_ui_font,
    get_font_manager,
    get_font_settings,
    register_resource_fonts,
    set_font_settings,
    subscribe_font_change,
)

__all__ = [
    "CSS_WEIGHT_MAP",
    "DEFAULT_FONT",
    "DEFAULT_PROSE_FONT",
    "FontManager",
    "PANGO_WEIGHT_MAP",
    "get_font_manager",
    "get_font_settings",
    "set_font_settings",
    "subscribe_font_change",
    "get_default_editor_font",
    "get_default_terminal_font",
    "get_default_ui_font",
    "font_exists",
    "create_font_description",
    "register_resource_fonts",
]
