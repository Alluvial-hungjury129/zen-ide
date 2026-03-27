"""
Dev Pad module for Zen IDE.

Activity tracking panel that opens as an editor tab (Cmd+.).
Logs file opens, edits, sketch saves, and manual notes.

Submodules:
- dev_pad.dev_pad: DevPad UI widget
- dev_pad.dev_pad_storage: Persistence and data classes
"""

from .activity_store import log_file_activity, log_sketch_activity
from .dev_pad import DevPad
from .dev_pad_storage import NOTES_DIR, DevPadActivity, DevPadStorage, get_dev_pad_storage

__all__ = [
    "DevPad",
    "DevPadActivity",
    "DevPadStorage",
    "NOTES_DIR",
    "get_dev_pad_storage",
    "log_file_activity",
    "log_sketch_activity",
]
