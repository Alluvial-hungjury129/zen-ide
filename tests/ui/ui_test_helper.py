"""Reusable GTK4 UI test utilities for Zen IDE.

Provides helpers to:
- Process GTK main loop events in tests
- Wait for conditions (e.g., widget visibility, layout ready)
- Simulate user interactions (clicks, key presses)
- Find widgets by type or CSS class
"""

import time

from gi.repository import Gdk, GLib, Gtk


def process_events(timeout_ms=100):
    """Process pending GTK events for up to timeout_ms milliseconds.

    This pumps the GLib main loop so widgets get allocated, signals fire,
    and deferred callbacks execute.
    """
    ctx = GLib.MainContext.default()
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while time.monotonic() < deadline:
        if not ctx.iteration(may_block=False):
            # No more pending events — sleep briefly then retry
            time.sleep(0.005)


def wait_for(condition, timeout_s=5.0, poll_interval_ms=50):
    """Wait for a condition to become True, processing GTK events meanwhile.

    Args:
        condition: Callable returning bool.
        timeout_s: Max seconds to wait.
        poll_interval_ms: How often to check condition.

    Returns:
        True if condition was met, False if timeout.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        process_events(poll_interval_ms)
        if condition():
            return True
    return False


def simulate_click(widget):
    """Simulate a click on a GTK4 widget by activating it.

    For buttons and actionable widgets, this triggers the "clicked" signal.
    For other widgets, it calls activate() if available.
    """
    if isinstance(widget, Gtk.Button):
        widget.emit("clicked")
        process_events(50)
    elif hasattr(widget, "activate"):
        widget.activate()
        process_events(50)


def simulate_key_press(widget, keyval, state=0):
    """Simulate a key press event on a widget.

    Args:
        widget: Target GTK widget.
        keyval: GDK key value (e.g., Gdk.KEY_Escape, Gdk.KEY_Return).
        state: Modifier state (e.g., Gdk.ModifierType.CONTROL_MASK).
    """
    # Use the event controller approach for GTK4
    display = widget.get_display() or Gdk.Display.get_default()
    if display is None:
        return

    # For widgets with key controllers, propagate through them
    for controller in _get_controllers(widget):
        if isinstance(controller, Gtk.EventControllerKey):
            controller.emit("key-pressed", keyval, 0, state)
            process_events(50)
            return

    # Fallback: if widget has a mnemonic_activate
    if hasattr(widget, "mnemonic_activate"):
        widget.mnemonic_activate(False)
        process_events(50)


def find_child_by_type(widget, widget_type):
    """Recursively find the first child widget of a given type.

    Args:
        widget: Root widget to search from.
        widget_type: GTK widget class to find.

    Returns:
        First matching widget or None.
    """
    if isinstance(widget, widget_type):
        return widget

    child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
    while child:
        result = find_child_by_type(child, widget_type)
        if result:
            return result
        child = child.get_next_sibling()
    return None


def find_children_by_type(widget, widget_type):
    """Recursively find all child widgets of a given type.

    Args:
        widget: Root widget to search from.
        widget_type: GTK widget class to find.

    Returns:
        List of matching widgets.
    """
    results = []
    if isinstance(widget, widget_type):
        results.append(widget)

    child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
    while child:
        results.extend(find_children_by_type(child, widget_type))
        child = child.get_next_sibling()
    return results


def find_child_by_css_class(widget, css_class):
    """Recursively find the first child widget with a given CSS class.

    Args:
        widget: Root widget to search from.
        css_class: CSS class name to match.

    Returns:
        First matching widget or None.
    """
    if widget.has_css_class(css_class):
        return widget

    child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
    while child:
        result = find_child_by_css_class(child, css_class)
        if result:
            return result
        child = child.get_next_sibling()
    return None


def find_button_by_label(widget, label_text):
    """Find a button containing the given label text.

    Searches through all Button children for one whose label matches.

    Args:
        widget: Root widget to search from.
        label_text: Text to match (case-sensitive).

    Returns:
        First matching Gtk.Button or None.
    """
    for btn in find_children_by_type(widget, Gtk.Button):
        if btn.get_label() == label_text:
            return btn
        # Check for child labels
        lbl = find_child_by_type(btn, Gtk.Label)
        if lbl and lbl.get_text() == label_text:
            return btn
    return None


def is_visible(widget):
    """Check if a widget is visible and has been allocated space."""
    if not widget.get_visible():
        return False
    # Check if the widget has a non-zero allocation
    alloc = widget.get_allocation()
    return alloc.width > 0 and alloc.height > 0


def get_widget_text(widget):
    """Get the text content of a widget (Label, Entry, Button, etc.)."""
    if isinstance(widget, Gtk.Label):
        return widget.get_text()
    if isinstance(widget, Gtk.Entry):
        return widget.get_text()
    if isinstance(widget, Gtk.Button):
        return widget.get_label() or ""
    if hasattr(widget, "get_text"):
        return widget.get_text()
    return ""


def _get_controllers(widget):
    """Get all event controllers attached to a widget."""
    controllers = []
    i = 0
    while True:
        try:
            ctrl = widget.observe_controllers().get_item(i)
            if ctrl is None:
                break
            controllers.append(ctrl)
            i += 1
        except Exception:
            break
    return controllers
