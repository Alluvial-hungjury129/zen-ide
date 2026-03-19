"""
Popups package for Zen IDE.

All floating popups and dialogs are organized here, one class per file.
"""

__all__ = [
    "NvimPopup",
    "NvimContextMenu",
    "show_context_menu",
    "KeyboardShortcutsPopup",
    "show_keyboard_shortcuts",
    "AboutPopup",
    "show_about",
    "InputDialog",
    "show_input",
    "ConfirmDialog",
    "show_confirm",
    "SelectionDialog",
    "show_selection",
    "CommandPaletteDialog",
    "show_command_palette",
    "NotificationToast",
    "show_toast",
    "SaveConfirmPopup",
    "show_save_confirm",
    "SaveAllConfirmPopup",
    "show_save_all_confirm",
    "GlobalSearchDialog",
    "SearchResult",
    "QuickOpenDialog",
    "FontPickerDialog",
    "FontItem",
    "show_font_picker",
    "CopilotPopup",
    "DiagnosticsPopup",
    "show_diagnostics",
    "SystemMonitorDialog",
    "show_system_monitor",
]

# Lazy imports — popups pull in AppKit (90ms on macOS) via nvim_popup
_LAZY_IMPORTS = {
    "NvimPopup": ".nvim_popup",
    "NvimContextMenu": ".nvim_context_menu",
    "show_context_menu": ".nvim_context_menu",
    "KeyboardShortcutsPopup": ".keyboard_shortcuts_popup",
    "show_keyboard_shortcuts": ".keyboard_shortcuts_popup",
    "AboutPopup": ".about_popup",
    "show_about": ".about_popup",
    "InputDialog": ".input_dialog",
    "show_input": ".input_dialog",
    "ConfirmDialog": ".confirm_dialog",
    "show_confirm": ".confirm_dialog",
    "SelectionDialog": ".selection_dialog",
    "show_selection": ".selection_dialog",
    "CommandPaletteDialog": ".command_palette_dialog",
    "show_command_palette": ".command_palette_dialog",
    "NotificationToast": ".notification_toast",
    "show_toast": ".notification_toast",
    "SaveConfirmPopup": ".save_confirm_popup",
    "show_save_confirm": ".save_confirm_popup",
    "SaveAllConfirmPopup": ".save_all_confirm_popup",
    "show_save_all_confirm": ".save_all_confirm_popup",
    "GlobalSearchDialog": ".global_search_dialog",
    "SearchResult": ".global_search_dialog",
    "QuickOpenDialog": ".quick_open_dialog",
    "FontPickerDialog": ".font_picker_dialog",
    "FontItem": ".font_picker_dialog",
    "show_font_picker": ".font_picker_dialog",
    "CopilotPopup": ".copilot_popup",
    "DiagnosticsPopup": ".diagnostics_popup",
    "show_diagnostics": ".diagnostics_popup",
    "SystemMonitorDialog": ".system_monitor_dialog",
    "show_system_monitor": ".system_monitor_dialog",
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name], __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
