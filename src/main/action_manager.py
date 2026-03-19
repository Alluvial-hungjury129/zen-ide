"""Manages GTK actions and keyboard shortcuts for the IDE."""

from __future__ import annotations

import platform
from typing import Callable

from gi.repository import Gio


class ActionManager:
    """Creates GTK actions and binds keyboard shortcuts."""

    def __init__(self, app: Gio.Application):
        self._app = app

    def create_actions(self, callbacks: dict[str, Callable]):
        """Bulk-create simple actions from a name → callback mapping."""
        for name, cb in callbacks.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self._app.add_action(action)

    def bind_shortcuts(self, bindings: dict[str, list[str]]):
        """Bulk-bind keyboard shortcuts from action_name → accelerator list."""
        for action, accels in bindings.items():
            self._app.set_accels_for_action(f"app.{action}", accels)

    @staticmethod
    def get_mod_keys() -> tuple[str, str]:
        """Return (mod, mod_shift) key prefixes for current platform."""
        if platform.system() == "Darwin":
            return "<Meta>", "<Meta><Shift>"
        return "<Control>", "<Control><Shift>"
