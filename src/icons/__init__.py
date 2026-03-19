"""Centralised icon management for Zen IDE.

All icon definitions, file-type icon lookups, and consistent icon rendering
helpers live here. Import icons from this module instead of hardcoding
Unicode characters throughout the codebase.
"""

from icons.icon_manager import (
    ICON_FONT_FAMILY,
    ICON_SIZE_CSS_CLASS,
    Icons,
    apply_icon_font,
    create_icon_label,
    get_file_icon,
    get_icon_font_name,
    icon_font_css_rule,
    icon_font_fallback,
)

__all__ = [
    "ICON_FONT_FAMILY",
    "ICON_SIZE_CSS_CLASS",
    "Icons",
    "apply_icon_font",
    "create_icon_label",
    "get_file_icon",
    "get_icon_font_name",
    "icon_font_css_rule",
    "icon_font_fallback",
]
