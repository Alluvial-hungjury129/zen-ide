# Focus Manager System

**Created_at:** 2026-02-08  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Document centralized focus state management for IDE components with visual transitions  
**Scope:** `src/shared/focus_manager.py`, `FocusBorderMixin`  

---

The Focus Manager provides centralized focus state management for Zen IDE components. It ensures that only one component is visually "focused" at a time, with smooth animated transitions between focus states.

## Architecture

The system consists of two main parts:

1. **FocusManager** (`src/shared/focus_manager.py`) - Singleton that tracks which component has focus
2. **FocusBorderMixin** (`src/shared/focus_border_mixin.py`) - Mixin that provides CSS-based focus borders

```
┌─────────────────────────────────────────────────────────────┐
│                  FocusManager                       │
│  (singleton - tracks focus state for all components)        │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Terminal │  │  Editor  │  │ Treeview │  │ AI Chat  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │            │
│       └─────────────┴─────────────┴─────────────┘            │
│                         │                                    │
│              set_focus(component_id)                         │
│                         ▼                                    │
│              Notifies old component → on_focus_out()         │
│              Notifies new component → on_focus_in()          │
└─────────────────────────────────────────────────────────────┘
```

## FocusManager

A singleton that manages focus state for all IDE components.

### Usage

```python
from focus_manager import get_focus_manager

# Get the singleton
focus_mgr = get_focus_manager()

# Register a component with callbacks
focus_mgr.register(
    component_id="terminal",
    on_focus_in=self._handle_focus_in,
    on_focus_out=self._handle_focus_out,
)

# Set focus to a component (automatically unfocuses others)
focus_mgr.set_focus("terminal")

# Check if a component has focus
if focus_mgr.has_focus("terminal"):
    ...

# Get the currently focused component ID
current = focus_mgr.get_current_focus()  # Returns "terminal" or None

# Clear focus without focusing another
focus_mgr.clear_focus("terminal")

# Unregister on cleanup
focus_mgr.unregister("terminal")
```

### Key Methods

| Method | Description |
|--------|-------------|
| `register(component_id, on_focus_in, on_focus_out)` | Register a component with focus callbacks |
| `unregister(component_id)` | Remove a component from focus management |
| `set_focus(component_id)` | Focus a component, unfocusing others |
| `clear_focus(component_id)` | Clear focus without focusing another |
| `has_focus(component_id)` | Check if a component has focus |
| `get_current_focus()` | Get ID of focused component (or None) |
| `clear_all()` | Clear focus from all components |

## FocusBorderMixin

A mixin class that provides CSS-based focus border transitions when focus changes.

### Visual Effect

- **Unfocused**: `panel-unfocused` CSS class applied
- **Focused**: `panel-focused` CSS class applied
- **Transition**: Handled via CSS in the active GTK theme

### Usage

```python
from gi.repository import Gtk
from focus_border_mixin import FocusBorderMixin

class MyPanel(FocusBorderMixin, Gtk.Box):
    def __init__(self, parent):
        Gtk.Box.__init__(self)
        self._init_focus_border()

    def set_focused(self, focused: bool):
        """Call this when focus state changes."""
        self._set_focused(focused)
```

### Key Methods

| Method | Description |
|--------|-------------|
| `_init_focus_border()` | Initialize focus border state |
| `_set_focused(focused)` | Apply focused/unfocused CSS classes |
| `_is_focused()` | Check focus state |
| `_cleanup_focus_border()` | Remove CSS classes on teardown |

## Integration Pattern

Typical integration in a component:

```python
from gi.repository import Gtk
from focus_manager import get_focus_manager
from focus_border_mixin import FocusBorderMixin

class TerminalPanel(FocusBorderMixin, Gtk.Box):
    COMPONENT_ID = "terminal"

    def __init__(self, parent):
        Gtk.Box.__init__(self)
        self._init_focus_border()

        # Register with focus manager
        focus_mgr = get_focus_manager()
        focus_mgr.register(
            self.COMPONENT_ID,
            on_focus_in=self._on_focus_in,
            on_focus_out=self._on_focus_out,
        )

        click = Gtk.GestureClick()
        click.connect("pressed", self._on_click)
        self.add_controller(click)

    def _on_click(self, gesture, n_press, x, y):
        get_focus_manager().set_focus(self.COMPONENT_ID)

    def _on_focus_in(self):
        self._set_focused(True)

    def _on_focus_out(self):
        self._set_focused(False)

    def destroy(self):
        get_focus_manager().unregister(self.COMPONENT_ID)
        super().destroy()
```

## Why This Design?

### Problem

In a multi-panel IDE, users need visual feedback about which panel will receive keyboard input. Without this:
- Users don't know where typed text will go
- Multiple panels might appear "active" simultaneously
- Focus state is ambiguous

### Solution

The Focus Manager provides:

1. **Single source of truth** - Only one component can have focus at a time
2. **Automatic coordination** - Focusing one component automatically unfocuses others
3. **Visual feedback** - Animated border transitions clearly show focus state
4. **Consistent UX** - All components behave the same way
5. **Decoupled design** - Components don't need to know about each other

## Files

| File | Description |
|------|-------------|
| `src/shared/focus_manager.py` | FocusManager singleton |
| `src/shared/focus_border_mixin.py` | FocusBorderMixin with CSS classes |
