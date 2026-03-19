# UI Testing Guide

**Created_at:** 2026-03-04  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Document the automated UI testing framework for GTK4 widgets and interactions  
**Scope:** `tests/ui/`, test fixtures, test helpers  

---

Zen IDE supports automated UI tests that interact with real GTK4 widgets. Tests can verify widget visibility, simulate clicks, check state changes, and more.

## Quick Start

```bash
# Run all tests (including UI tests)
make tests

# Run only UI tests
uv run python -m pytest tests/ui/ -v --color=yes

# Run a specific test
uv run python -m pytest tests/ui/test_window_startup.py::TestMainPanels::test_editor_view_exists -v
```

## Writing a UI Test

```python
import pytest
from ui.ui_test_helper import simulate_click, find_button_by_label, wait_for

pytestmark = pytest.mark.gui


def test_my_feature(zen_window, process_gtk_events):
    """Verify a button click triggers expected behavior."""
    # 1. Find a widget
    btn = find_button_by_label(zen_window, "Save")
    assert btn is not None

    # 2. Interact with it
    simulate_click(btn)

    # 3. Wait for effects and assert
    process_gtk_events(200)
    assert zen_window.editor_view.is_saved()
```

## Available Fixtures

| Fixture | Scope | Description |
|---------|-------|-------------|
| `gtk_init` | session | Initializes GTK4, skips if no display |
| `zen_app` | function | Creates a `ZenIDEApp` instance |
| `zen_window` | function | Creates a fully initialized `ZenIDEWindow` with temp workspace |
| `process_gtk_events` | function | Returns the `process_events(ms)` helper |

## Helper Functions (`ui_test_helper.py`)

### Event Processing

| Function | Description |
|----------|-------------|
| `process_events(timeout_ms=100)` | Pump the GLib main loop for a duration |
| `wait_for(condition, timeout_s=5.0)` | Wait for a condition, processing events meanwhile |

### Widget Finding

| Function | Description |
|----------|-------------|
| `find_child_by_type(widget, type)` | Find first child of a GTK type |
| `find_children_by_type(widget, type)` | Find all children of a GTK type |
| `find_child_by_css_class(widget, class)` | Find first child with a CSS class |
| `find_button_by_label(widget, text)` | Find a button by its label text |

### Interaction

| Function | Description |
|----------|-------------|
| `simulate_click(widget)` | Click a button or activate a widget |
| `simulate_key_press(widget, keyval, state)` | Send a key press event |

### Assertions

| Function | Description |
|----------|-------------|
| `is_visible(widget)` | Check visibility + non-zero allocation |
| `get_widget_text(widget)` | Get text from Label, Entry, Button |

## Test Patterns

### Check a panel is visible

```python
def test_tree_visible(zen_window):
    assert zen_window.tree_view.get_visible()
```

### Wait for deferred initialization

```python
def test_bottom_panels(zen_window):
    from ui.ui_test_helper import wait_for
    wait_for(lambda: zen_window._bottom_panels_created, timeout_s=5.0)
    assert zen_window._bottom_panels_created
```

### Find and click a button

```python
def test_menu_button(zen_window, process_gtk_events):
    from ui.ui_test_helper import find_children_by_type
    from gi.repository import Gtk

    header = zen_window.get_titlebar()
    buttons = find_children_by_type(header, Gtk.MenuButton)
    assert len(buttons) > 0

    # Click the menu button
    buttons[0].emit("clicked")
    process_gtk_events(200)
```

### Simulate keyboard shortcut

```python
def test_escape_closes_popup(zen_window):
    from ui.ui_test_helper import simulate_key_press
    from gi.repository import Gdk

    simulate_key_press(zen_window, Gdk.KEY_Escape)
```

## Running on Headless Systems (CI)

UI tests require a display. On Linux CI, wrap with `xvfb-run`:

```bash
# CI command
xvfb-run -a uv run python -m pytest tests/ui/ -v --color=yes
```

On macOS CI, no wrapper is needed (Quartz provides a display).

Tests auto-skip when no display is available (`pytest.skip`).

## Architecture Notes

- Each `zen_window` fixture creates a **fresh window** with a temp workspace
- The main loop is pumped synchronously (no `app.run()`) so tests stay in control
- `_layout_ready` flag ensures deferred init has completed before tests access widgets
- Cleanup destroys the window and removes temp environment variables
