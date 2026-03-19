"""Settings package for Zen IDE."""

from shared.settings.default_settings import DEFAULT_SETTINGS
from shared.settings.keybindings import KeyBindings
from shared.settings.settings_manager import (
    SETTINGS_BACKUP,
    SETTINGS_DIR,
    SETTINGS_FILE,
    get_layout,
    get_setting,
    get_settings,
    get_workspace,
    has_pending_changes,
    load_settings,
    restore_from_backup,
    save_layout,
    save_settings,
    save_workspace,
    set_setting,
)

__all__ = [
    "DEFAULT_SETTINGS",
    "KeyBindings",
    "SETTINGS_BACKUP",
    "SETTINGS_DIR",
    "SETTINGS_FILE",
    "get_layout",
    "get_setting",
    "get_settings",
    "get_workspace",
    "has_pending_changes",
    "load_settings",
    "restore_from_backup",
    "save_layout",
    "save_settings",
    "save_workspace",
    "set_setting",
]
