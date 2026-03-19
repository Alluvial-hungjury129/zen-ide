# Dialog System (GTK4)

**Created_at:** 2026-02-08  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Document the Neovim-style floating dialog system and NvimPopup base class  
**Scope:** `src/popups/nvim_popup.py`, all popup subclasses  

---

Neovim-style floating dialog system for the Zen IDE GTK4 version.

**Base class:** `src/popups/nvim_popup.py`

## Overview

**All popups and floating windows in Zen IDE MUST inherit from `NvimPopup`. No exceptions.**

The dialog system provides keyboard-centric, floating dialogs that mirror Neovim's UI philosophy:

- **Floating windows** - Centered (default) or anchored to any widget
- **Keyboard-first** - j/k navigation, Enter to confirm, Escape to close
- **Minimal design** - No visual clutter, just essential information
- **Vim-style shortcuts** - Number keys for quick selection, g/G for first/last
- **Non-modal mode** - For inline popups like autocomplete that don't steal focus

## NvimPopup Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `parent` | required | Parent Gtk.Window to attach to |
| `title` | `""` | Optional title shown in header |
| `width` | `400` | Popup width (-1 for natural size) |
| `height` | `-1` | Popup height (-1 for natural size) |
| `anchor_widget` | `None` | Widget to anchor to (None = center on parent) |
| `anchor_rect` | `None` | Gdk.Rectangle relative to anchor_widget |
| `modal` | `True` | Whether the popup blocks parent interaction |
| `steal_focus` | `True` | Whether presenting steals keyboard focus |

### Centered mode (default)

Standard modal dialog centered on parent window:

```python
popup = NvimPopup(parent=window, title="My Dialog", width=400)
popup.present()
```

### Anchored mode

Popup positioned relative to a widget (e.g. at cursor position):

```python
rect = Gdk.Rectangle()
rect.x, rect.y = cursor_x, cursor_y
popup = NvimPopup(
    parent=window,
    anchor_widget=editor_view,
    anchor_rect=rect,
    modal=False,
    steal_focus=False,
)
popup.popup()  # Show without stealing focus
popup.set_anchor_rect(new_rect)  # Update position
popup.popdown()  # Hide without destroying
```

### Methods

| Method | Description |
|--------|-------------|
| `present()` | Show the popup (standard GTK) |
| `popup()` | Show the popup (popover-compatible alias) |
| `popdown()` | Hide without destroying (for reusable popups) |
| `close()` | Hide (steal_focus=False) or destroy (steal_focus=True) |
| `set_anchor_rect(rect)` | Update anchor position for repositioning |

## Dialog Types

### NvimPopup (Base Class)

Base class for ALL dialogs and popups. Provides:

- Transient window with no decorations
- Automatic centering on parent (default) or anchored positioning
- Themed styling with double-line border drawn by Cairo
- Escape key to close
- CSS styling for consistent look
- Non-modal mode for inline popups (autocomplete, tooltips)

### InputDialog

Single-line text input with validation.

```python
from popups import show_input

def on_submit(text):
    print(f"User entered: {text}")

def validate(text):
    if not text:
        return "Name cannot be empty"
    return None  # No error

show_input(
    parent=window,
    title="New File",
    message="Enter the filename:",
    placeholder="filename.py",
    initial_value="",
    on_submit=on_submit,
    validate=validate
)
```

**Keyboard shortcuts:**
- `Enter` - Submit input
- `Escape` - Cancel

### ConfirmDialog

Yes/No confirmation with optional danger styling.

```python
from popups import show_confirm

show_confirm(
    parent=window,
    title="Delete File",
    message="Are you sure you want to delete 'config.py'?",
    confirm_text="Delete",
    cancel_text="Cancel",
    danger=True,  # Red confirm button
    on_confirm=lambda: delete_file(),
    on_cancel=lambda: print("Cancelled")
)
```

**Keyboard shortcuts:**
- `y` or `Enter` - Confirm
- `n` or `Escape` - Cancel
- `Tab` - Switch focus between buttons

### SelectionDialog

Scrollable list with Vim-style navigation.

```python
from popups import show_selection

items = [
    {"label": "Open File", "hint": "Cmd+O", "icon": "📂"},
    {"label": "Save File", "hint": "Cmd+S", "icon": "💾"},
    {"label": "Close Tab", "hint": "Cmd+W", "icon": "✕"},
    "Simple string item",  # Also supported
]

show_selection(
    parent=window,
    title="Actions",
    items=items,
    on_select=lambda item: print(f"Selected: {item}"),
    show_icons=True,
    max_visible=10  # Scroll after 10 items
)
```

**Keyboard shortcuts:**
- `j` or `↓` - Move down
- `k` or `↑` - Move up
- `g` - Jump to first item
- `G` - Jump to last item
- `1-9` - Quick select by number
- `Enter` - Select current item
- `Escape` - Close

### CommandPaletteDialog

Fuzzy-search command palette (Cmd+Shift+P).

```python
from popups import show_command_palette

commands = [
    {
        "name": "file.save",
        "label": "Save File",
        "hint": "Save the current file",
        "icon": "💾",
        "keybind": "Cmd+S",
        "action": lambda: save_file()
    },
    {
        "name": "file.open",
        "label": "Open File",
        "icon": "📂",
        "keybind": "Cmd+O",
        "action": lambda: open_file()
    },
]

show_command_palette(
    parent=window,
    commands=commands,
    on_execute=lambda cmd: print(f"Executed: {cmd['name']}"),
    placeholder="Type a command..."
)
```

**Keyboard shortcuts:**
- `↓` or `Ctrl+N` - Move down
- `↑` or `Ctrl+P` - Move up
- `Enter` - Execute selected command
- `Escape` - Close

**Fuzzy matching:**
- Searches both `name` and `label` fields
- Prioritizes exact matches over fuzzy
- Results are sorted by relevance score

### NotificationToast

Non-modal notification that auto-dismisses.

```python
from popups import show_toast

# Info toast (default)
show_toast(parent=window, message="File saved successfully")

# Success toast
show_toast(parent=window, message="Build completed!", level="success")

# Warning toast
show_toast(parent=window, message="Unsaved changes", level="warning")

# Error toast
show_toast(parent=window, message="Connection failed", level="error", timeout_ms=5000)
```

**Levels:** `info`, `success`, `warning`, `error`

**Default timeout:** 3000ms (set `timeout_ms=0` to disable auto-close)

## Styling

All dialogs use CSS classes that can be themed:

| CSS Class | Purpose |
|-----------|---------|
| `.dialog-title` | Title text (accent color, bold) |
| `.dialog-message` | Message text |
| `.dialog-hint` | Hint text (dimmed) |
| `.dialog-input` | Text entry field |
| `.dialog-list` | List container |
| `.dialog-list-item` | List row |
| `.dialog-button` | Standard button |
| `.dialog-button-primary` | Primary action button (accent color) |
| `.dialog-button-danger` | Destructive action button (red) |
| `.keybind` | Keyboard shortcut badge |

Colors come from the active theme via `themes.get_theme()`.

## Usage in Zen IDE

The dialog system is used throughout the GTK4 IDE:

- **File tree context menu** - New file/folder dialogs
- **Global search** - Extends `NvimPopup` for search UI
- **Quick open** - File picker with fuzzy search
- **Autocomplete** - Anchored, non-modal NvimPopup at cursor position
- **Settings** - Confirmation dialogs for dangerous actions

### Example: GlobalSearchDialog

The global search dialog (`popups/global_search_dialog.py`) extends `NvimPopup`:

```python
from popups.nvim_popup import NvimPopup

class GlobalSearchDialog(NvimPopup):
    def __init__(self, parent, on_open_file):
        super().__init__(parent, title="Search in Files", width=600)
        self._on_open_file = on_open_file
    
    def _create_content(self):
        # Add search entry to self._content_box
        self._entry = Gtk.Entry()
        self._content_box.append(self._entry)
        # ... results list, etc.
```

### Example: Autocomplete (anchored, non-modal)

The autocomplete popup uses NvimPopup in anchored, non-focus-stealing mode:

```python
from popups.nvim_popup import NvimPopup

popup = NvimPopup(
    parent=window,
    width=-1, height=-1,
    modal=False, steal_focus=False,
    anchor_widget=editor_view,
)
popup.set_anchor_rect(cursor_rect)
popup.popup()    # Show without stealing focus
popup.popdown()  # Hide without destroying
```

## Design Principles

1. **Keyboard-first** - Every action should be achievable without a mouse
2. **Vim muscle memory** - Use j/k, g/G, numbers for navigation where possible
3. **Minimal chrome** - No title bars, close buttons, or unnecessary decorations
4. **Fast dismissal** - Escape always closes, Enter confirms
5. **Contextual hints** - Show keyboard shortcuts inline

## API Reference

### Convenience Functions

```python
# Input dialog
show_input(parent, title, message, placeholder, initial_value, on_submit, validate) -> InputDialog

# Confirmation dialog
show_confirm(parent, title, message, confirm_text, cancel_text, danger, on_confirm, on_cancel) -> ConfirmDialog

# Selection menu
show_selection(parent, title, items, on_select, show_icons, max_visible) -> SelectionDialog

# Command palette
show_command_palette(parent, commands, on_execute, placeholder) -> CommandPaletteDialog

# Toast notification
show_toast(parent, message, level, timeout_ms) -> NotificationToast
```

All functions return the dialog instance, which can be used to:
- Call `dialog.get_result()` to get the result after close
- Connect to GTK signals for additional control
