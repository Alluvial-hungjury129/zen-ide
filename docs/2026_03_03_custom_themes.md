# Custom Themes — Design Plan

**Created_at:** 2026-03-03  
**Updated_at:** 2026-03-08  
**Status:** Planned  
**Goal:** Allow users to create, save, and share custom color themes as JSON files  
**Scope:** `src/themes/`, `~/.zen_ide/themes/`  

---

Allow users to define, save, and share their own color themes as JSON files.

## Overview

Users should be able to:
1. **Create** custom themes from scratch or by copying an existing theme
2. **Save** themes as JSON files in `~/.zen_ide/themes/`
3. **Edit** themes using an external JSON editor (with live reload)
4. **Share** themes by copying JSON files between machines
5. **Select** custom themes alongside built-in themes in the Theme Picker

---

## JSON Theme Format

Custom themes are stored as JSON files matching the `Theme` dataclass structure:

```json
{
  "name": "my_custom_theme",
  "display_name": "My Custom Theme",
  "is_dark": true,
  
  "main_bg": "#1a1a2e",
  "panel_bg": "#16213e",
  "fg_color": "#e0e0e0",
  "fg_dim": "#808080",
  
  "selection_bg": "#264f78",
  "hover_bg": "#2a2d3e",
  
  "line_number_bg": "#1a1a2e",
  "line_number_fg": "#606080",
  "caret_fg": "#aeafad",
  "indent_guide": "#404060",
  
  "tab_bg": "#16213e",
  "tab_active_bg": "#1a1a2e",
  "tab_fg": "#808090",
  "tab_active_fg": "#ffffff",
  
  "tree_bg": "#16213e",
  "tree_fg": "#cccccc",
  "tree_selected_bg": "#264f78",
  "tree_modified_fg": "#d9c020",
  "tree_ignored_fg": "#606080",
  
  "term_bg": "#1a1a2e",
  "term_fg": "#cccccc",
  "term_cyan": "#11a8cd",
  "term_black": "#1a1a2e",
  "term_red": "#e06c75",
  "term_green": "#98c379",
  "term_yellow": "#e5c07b",
  "term_blue": "#61afef",
  "term_magenta": "#c678dd",
  "term_white": "#abb2bf",
  
  "accent_color": "#e94560",
  "border_color": "#404060",
  "border_focus": "#e94560",
  "sash_color": "#1a1a2e",
  
  "syntax_keyword": "#569cd6",
  "syntax_string": "#ce9178",
  "syntax_comment": "#6a9955",
  "syntax_number": "#b5cea8",
  "syntax_function": "#dcdcaa",
  "syntax_class": "#4ec9b0",
  "syntax_operator": "#d4d4d4",
  "syntax_keyword_control": "#c586c0",
  "syntax_variable": "#9cdcfe",
  "syntax_string_escape": "#d7ba7d",
  "syntax_regex": "#d16969",
  "syntax_doc_comment": "#608b4e",
  "syntax_constant": "#4fc1ff",
  "syntax_boolean": "#569cd6",
  "syntax_parameter": "#b5cea8",
  
  "chat_user_fg": "#11a8cd",
  "chat_assistant_fg": "#CE93D8",
  "ai_processing_color": "#c678dd",
  
  "search_match_bg": "#ffd700",
  "search_current_bg": "#ff6600",
  
  "git_added": "#98c379",
  "git_modified": "#e5c07b",
  "git_deleted": "#e06c75",
  "warning_color": "#f0d050"
}
```

### Required vs Optional Fields

| Required | Optional (with defaults) |
|----------|-------------------------|
| `name`, `display_name`, `is_dark` | Extended syntax colors |
| Base colors (`main_bg`, `panel_bg`, `fg_color`, `fg_dim`) | `ai_processing_color`, `chat_*` |
| Selection (`selection_bg`, `hover_bg`) | `search_*` colors |
| Editor (`line_number_*`, `caret_fg`, `indent_guide`) | `git_*` colors |
| Tabs (`tab_*`) | `warning_color` |
| Tree (`tree_*`) | Terminal ANSI colors |
| Terminal (`term_bg`, `term_fg`) | `sash_color` |
| Syntax (`syntax_keyword` through `syntax_operator`) | |
| Accent (`accent_color`) | |
| Borders (`border_color`, `border_focus`) | |

Optional fields inherit sensible defaults from the `Theme` dataclass.

---

## Storage Location

```
~/.zen_ide/
├── settings.json          # Existing settings
└── themes/                 # NEW: User custom themes directory
    ├── my_custom_theme.json
    ├── team_theme.json
    └── exported_dracula_modified.json
```

- Directory created automatically on first custom theme save
- Filename must match the theme `name` field + `.json`
- Invalid JSON files are skipped with a warning in logs

---

## Implementation Plan

### Phase 1: JSON Theme Loader

**File:** `src/themes/custom_theme_loader.py` (new)

```python
"""Load custom themes from ~/.zen_ide/themes/"""

from pathlib import Path
from dataclasses import fields
import json

from themes.theme_model import Theme

CUSTOM_THEMES_DIR = Path.home() / ".zen_ide" / "themes"

def load_custom_themes() -> dict[str, Theme]:
    """Load all valid JSON themes from the custom themes directory."""
    ...

def save_theme_as_json(theme: Theme, path: Path) -> None:
    """Export a Theme to JSON file."""
    ...

def validate_theme_json(data: dict) -> tuple[bool, list[str]]:
    """Validate theme JSON has required fields. Returns (valid, errors)."""
    ...
```

**Tasks:**
- [ ] Create `custom_theme_loader.py` with load/save/validate functions
- [ ] Use `dataclasses.fields()` to get required vs optional fields
- [ ] Handle missing optional fields with `Theme` defaults
- [ ] Add logging for invalid theme files

### Phase 2: Integrate with Theme Manager

**File:** `src/themes/theme_manager.py` (modify)

**Changes:**
1. Call `load_custom_themes()` at startup (after lazy built-in themes init)
2. Merge custom themes into `THEMES` dict (custom themes can override built-in names)
3. Add `reload_custom_themes()` function for live reload

```python
# In theme_manager.py
from themes.custom_theme_loader import load_custom_themes

def _init_themes():
    """Initialize themes including custom user themes."""
    # ... existing lazy loading ...
    
    # Load custom themes (can override built-in)
    custom = load_custom_themes()
    THEMES.update(custom)
```

**Tasks:**
- [ ] Modify `theme_manager.py` to load custom themes
- [ ] Custom themes loaded after built-ins (override priority)
- [ ] Add `reload_custom_themes()` for live editing workflow

### Phase 3: Theme Picker Updates

**File:** `src/popups/theme_picker_dialog.py` (modify)

**Changes:**
1. Add section divider between built-in and custom themes
2. Add "Open Themes Folder" button to reveal `~/.zen_ide/themes/`
3. Add "Reload Themes" button to pick up external edits

```
┌─────────────────────────────────────┐
│ Theme Picker                        │
├─────────────────────────────────────┤
│ ○ Dark  ○ Light  ○ All              │
├─────────────────────────────────────┤
│ BUILT-IN                            │
│   Zen Dark                       ⚫ │
│   Tokyonight                        │
│   Dracula                           │
│   ...                               │
├─────────────────────────────────────┤
│ CUSTOM                              │
│   My Custom Theme                   │
│   Team Theme                        │
├─────────────────────────────────────┤
│ [Open Themes Folder] [Reload]       │
└─────────────────────────────────────┘
```

**Tasks:**
- [ ] Add section headers in theme list
- [ ] Implement "Open Themes Folder" button (reveal in Finder/file manager)
- [ ] Implement "Reload Themes" button with visual feedback
- [ ] Mark custom themes with an icon (e.g., `` or ``)

### Phase 4: Export Existing Theme

**File:** `src/popups/theme_picker_dialog.py` (modify)

Add context menu or button to export any theme (built-in or custom) as JSON:

```
Right-click on theme → "Export as JSON..."
```

This enables:
1. Starting from a built-in theme and customizing it
2. Sharing custom themes with others
3. Backing up themes

**Tasks:**
- [ ] Add right-click context menu to theme list items
- [ ] Implement "Export as JSON..." action
- [ ] Use `Gtk.FileDialog` to choose save location
- [ ] Auto-suggest filename from theme name

### Phase 5: Documentation

**Files to update:**
- [ ] `docs/2026_02_12_settings_reference.md` — Add custom themes section
- [ ] `README.md` — Mention custom themes in features
- [ ] `AGENTS.md` — Update themes documentation reference

---

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/themes/custom_theme_loader.py` | **New** | JSON theme loading, saving, validation |
| `src/themes/theme_manager.py` | Modify | Integrate custom theme loading |
| `src/popups/theme_picker_dialog.py` | Modify | UI for custom themes section, export |
| `docs/2026_03_03_custom_themes.md` | **New** | This document |
| `docs/2026_02_12_settings_reference.md` | Modify | Reference custom themes location |
| `README.md` | Modify | Feature list update |
| `AGENTS.md` | Modify | Documentation reference update |

---

## Future Enhancements (Out of Scope)

These are not part of the initial implementation but could be added later:

1. **In-app Theme Editor** — Visual color picker UI for editing themes
2. **Theme Marketplace** — Browse and download community themes
3. **Theme Variants** — Auto-generate light/dark variants
4. **Live Preview** — Preview theme before applying
5. **Import External Themes** — Convert third-party JSON theme formats
6. **Syntax Preview Panel** — Show sample code with current syntax colors

---

## Testing Plan

1. **Unit tests** (`tests/test_custom_theme_loader.py`):
   - Valid JSON loads correctly
   - Missing required fields raise validation errors
   - Missing optional fields use defaults
   - Invalid JSON files are skipped gracefully

2. **Integration tests**:
   - Custom theme appears in Theme Picker
   - Custom theme can be selected and applied
   - Reload picks up external file changes
   - Export creates valid JSON that can be re-imported

3. **Manual testing**:
   - Create theme from scratch
   - Modify theme in external editor, reload
   - Share theme file between machines
