"""Manages mutually exclusive split panels in the IDE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from gi.repository import Gtk


@dataclass
class _PanelEntry:
    widget: Gtk.Widget
    show_fn: Callable
    hide_fn: Callable


class SplitPanelManager:
    """Manages mutually exclusive split panels sharing a Gtk.Paned.

    Only one panel can be active at a time. Showing a new panel
    automatically hides the currently active one.
    """

    def __init__(self, paned: Gtk.Paned, editor_view: Gtk.Widget):
        self._paned = paned
        self._editor = editor_view
        self._panels: dict[str, _PanelEntry] = {}
        self._active: str | None = None

    def register(self, name: str, widget: Gtk.Widget, show_fn: Callable, hide_fn: Callable):
        """Register a panel with custom show/hide callbacks."""
        self._panels[name] = _PanelEntry(widget, show_fn, hide_fn)

    def show(self, name: str, **kwargs):
        """Show a panel, hiding the currently active panel first."""
        if self._active and self._active != name:
            self.hide(self._active)
        self._panels[name].show_fn(**kwargs)
        self._active = name

    def hide(self, name: str | None = None):
        """Hide a panel (defaults to the active panel)."""
        name = name or self._active
        if name and name in self._panels:
            self._panels[name].hide_fn()
            if self._active == name:
                self._active = None

    def toggle(self, name: str, **kwargs):
        """Toggle a panel's visibility."""
        if self._active == name:
            self.hide(name)
        else:
            self.show(name, **kwargs)

    def is_visible(self, name: str) -> bool:
        """Check if a specific panel is currently active."""
        return self._active == name

    # -- Common helpers for end_child split panels --

    def swap_end_child(self, widget: Gtk.Widget):
        """Set widget as the paned end_child if not already."""
        if self._paned.get_end_child() != widget:
            self._paned.set_end_child(widget)

    def set_half_position(self) -> bool:
        """Set paned to 50% split. Returns False for GLib.idle_add."""
        width = self._paned.get_width()
        if width > 0:
            self._paned.set_position(width // 2)
        return False

    def restore_full_position(self):
        """Give all space back to the start child."""
        self._paned.set_position(self._paned.get_width())
