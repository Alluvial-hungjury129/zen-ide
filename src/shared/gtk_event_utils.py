"""Shared GTK event helper utilities."""

from gi.repository import Gtk


def is_button_click(widget) -> bool:
    """Return True when widget is a Gtk.Button or is inside one."""
    current = widget
    while current is not None:
        if isinstance(current, (Gtk.Button, Gtk.ToggleButton, Gtk.MenuButton)):
            return True
        current = current.get_parent()
    return False


def is_click_inside_widget(source, x, y, target) -> bool:
    """Check if a click at (x, y) in source is inside target widget."""
    result = source.translate_coordinates(target, x, y)
    if result is None:
        return False
    tx, ty = result
    width = target.get_width()
    height = target.get_height()
    return 0 <= tx <= width and 0 <= ty <= height
