# Intellisense: Distinguish Functions vs Properties

**Created_at:** 2026-01-04  
**Updated_at:** 2026-03-16  
**Status:** Planned  
**Goal:** Capture the plan for differentiating functions and properties in autocomplete results.  
**Scope:** `src/editor/autocomplete/`, autocomplete popup rendering  

---

## Goal
Add visual differentiation in the autocomplete popup between:
- **Functions/methods** (callable items) - e.g., `print()`, `len()`, `self.save()`
- **Properties/attributes** (data members) - e.g., `self.name`, `obj.value`, `CONSTANT`

## Current State
- Completions are stored as `List[str]` (plain strings, no type info)
- Need to implement autocomplete in GTK4 version
- Will use `Gtk.Popover` for popup display

## Implementation Plan

### 1. Create a CompletionItem dataclass
**File:** `src/editor/autocomplete/autocomplete.py` (future)

Add a dataclass to hold completion metadata:
```python
from dataclasses import dataclass
from enum import Enum

class CompletionKind(Enum):
    FUNCTION = "function"    # def foo(), methods
    PROPERTY = "property"    # self.x, class attributes
    KEYWORD = "keyword"      # if, for, class, etc.
    BUILTIN = "builtin"      # print, len, etc.
    SNIPPET = "snippet"      # code templates
    VARIABLE = "variable"    # local identifiers

@dataclass
class CompletionItem:
    name: str
    kind: CompletionKind
```

### 2. Update completion-gathering functions to return CompletionItem
Modify these methods to tag each completion with its kind:

| Method | Items | Kind |
|--------|-------|------|
| `_get_python_completions()` | keywords | `KEYWORD` |
| `_get_python_completions()` | builtins | `BUILTIN` |
| `_get_python_completions()` | snippets | `SNIPPET` |
| `_get_public_functions()` | `def xxx` | `FUNCTION` |
| `_get_public_properties()` | module-level vars | `PROPERTY` |
| `_get_class_members()` | `def xxx` | `FUNCTION` |
| `_get_class_members()` | class attrs, enum values | `PROPERTY` |
| `_get_self_attributes()` | `self.xxx` | `PROPERTY` |
| `_extract_identifiers()` | generic identifiers | `VARIABLE` |

### 3. Update `_get_completions()` to use CompletionItem
- Change return type from `List[str]` to `List[CompletionItem]`
- Merge completions by name (keeping the most specific kind)
- Sort by prefix match, then alphabetically

### 4. Update popup rendering to show icons
Modify `_show_popup()` to display kind-specific prefixes/icons:

| Kind | Icon | Color (optional) |
|------|------|------------------|
| FUNCTION | `ƒ` or `λ` | Could use `styles.FUNCTION_COLOR` if defined |
| PROPERTY | `●` or `◆` | Could use `styles.PROPERTY_COLOR` |
| KEYWORD | `κ` | |
| BUILTIN | `β` | |
| SNIPPET | `⌘` | |
| VARIABLE | `ν` | |

Display format: `ƒ print` or `● name`

### 5. Update filtering and selection logic
- `_on_key_release()`: Filter by `item.name` instead of raw string
- `_on_select()`: Insert `item.name` instead of raw string

## Files to Modify
1. `src/editor/autocomplete/autocomplete.py` - GTK4 autocomplete implementation (to be created)

## Testing
- Trigger autocomplete with Ctrl+Space
- Verify functions show `ƒ` prefix
- Verify properties show `●` prefix
- Verify filtering still works correctly
- Verify selection inserts only the name (without icon)
