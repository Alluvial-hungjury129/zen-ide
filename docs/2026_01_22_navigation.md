# Navigation System

**Created_at:** 2026-01-22  
**Updated_at:** 2026-03-16  
**Status:** Active  
**Goal:** Document code navigation (Cmd+Click / Go-to-Definition) and symbol resolution  
**Scope:** `src/navigation/code_navigation.py`, `src/navigation/code_navigation_py.py`, module resolution  

---

This document describes how code navigation (Cmd+Click / Go-to-Definition) works in Zen IDE.

## Overview

When you Cmd+Click on a symbol in the editor, the IDE navigates to its definition. This works across files, packages, and even workspace folders.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Cmd+Clicks                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     editor_view.py → on_cmd_click()                          │
│                     Detects click position, delegates to navigation           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 navigation/code_navigation_py.py                             │
│                                                                              │
│  PythonIntellisense.on_cmd_click(editor, file_path, index)                  │
│    1. Get word at click position                                            │
│    2. Get module chain (e.g., "LogGateway.debug")                           │
│    3. Parse imports to map symbols to modules                               │
│    4. Resolve the target file                                               │
│    5. Open file and navigate to symbol                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
┌──────────────────────────────────┐  ┌──────────────────────────────────────┐
│     Module Resolution             │  │     Symbol Finding                    │
│                                   │  │                                       │
│  _open_module()                   │  │  _find_symbol_in_editor()            │
│  _find_module_init()              │  │    - Pattern match for:              │
│  _resolve_reexport_in_init()      │  │      • class definitions             │
│                                   │  │      • function definitions          │
│  Searches:                        │  │      • variable assignments          │
│  - Current directory              │  │                                       │
│  - Project root                   │  │  _navigate_to_line()                 │
│  - src/lib/app subdirs            │  │    - Scroll to line                  │
│  - All workspace folders          │  │    - Highlight with animation        │
└──────────────────────────────────┘  └──────────────────────────────────────┘
                                                        │
                                                        ▼
                                      ┌──────────────────────────────────────┐
                                      │  navigation/nav_highlight.py          │
                                      │                                       │
                                      │  NavigationHighlight                  │
                                      │    - Temporary line highlighting      │
                                      │    - Fade-out animation              │
                                      └──────────────────────────────────────┘
```

## Key Components

### 1. Entry Point: `on_cmd_click()`

Located in `PythonIntellisense` class (`src/navigation/code_navigation_py.py`).

**Flow:**
1. Extract word at click position (`get_word_at_index`)
2. Get full chain context (`get_module_chain_at_index`) - e.g., `LogGateway.debug`
3. Parse file imports to build symbol→module mapping
4. Determine navigation target based on import type

### 2. Import Parsing: `_parse_imports()`

Parses Python import statements to build a mapping of symbols to their source modules:

```python
# Input file has:
from python_lambda_utils import LogGateway
import os.path

# Resulting imports dict:
{
    "LogGateway": "python_lambda_utils.LogGateway",
    "os": "os",
    "path": "os.path"
}
```

### 3. Module Resolution

**`_open_module(module_path, current_file)`**

Resolves a dotted module path to an actual file:
- Converts dots to path separators
- Searches multiple locations (current dir, project root, workspace folders)
- Handles both `.py` files and packages (`__init__.py`)

**`_find_module_init(module_path, current_file)`**

Finds `__init__.py` for a package without opening it. Used to check for re-exports.

**`_resolve_reexport_in_init(init_file, symbol, current_file)`**

Checks if a symbol in `__init__.py` is re-exported from another module:

```python
# __init__.py contains:
from .log_gateway import LogGateway

# When clicking on LogGateway import:
# Returns path to log_gateway.py instead of opening __init__.py
```

### 4. Symbol Finding: `_find_symbol_in_editor()`

Uses regex patterns to locate symbol definitions in code:

| Pattern | Matches |
|---------|---------|
| `^class\s+{symbol}\s*[:\(]` | Class definitions |
| `^\s*def\s+{symbol}\s*\(` | Function/method definitions |
| `^{symbol}\s*=` | Top-level variable assignments |
| `^\s+{symbol}\s*=` | Class member assignments |

**Indent Guide Handling:**

The editor displays indent guide characters (`│`) that aren't in the actual file. Before pattern matching, these are stripped:

```python
content = content.replace("│", " ")
```

### 5. Navigation Highlight: `nav_highlight.py`

Located in `src/navigation/`.

Provides temporary line highlighting with smooth fade-out animation when navigating to definitions:
- Gold highlight on target line
- Fades out over ~400ms
- Clears immediately on user action (typing, clicking)

## Navigation Scenarios

### Simple Import Navigation

```python
from mymodule import MyClass
#    ^^^^^^^^
# Click here → opens mymodule.py, navigates to class MyClass
```

### Method Navigation via Chain

```python
LogGateway.debug("message")
#          ^^^^^
# Click here → opens log_gateway.py, navigates to def debug()
```

### Re-export Navigation

```python
# In consumer.py:
from python_lambda_utils import LogGateway
#                               ^^^^^^^^^^
# Click here:
#   1. Finds python_lambda_utils/__init__.py
#   2. Reads: "from .log_gateway import LogGateway"
#   3. Opens log_gateway.py (NOT __init__.py)
#   4. Navigates to class LogGateway
```

### Cross-Workspace Navigation

When you have multiple workspace folders, navigation searches all of them:

```
Workspace folders:
  - /project/my-api           ← You're editing here
  - /project/shared-library   ← Library is here

# In my-api/handler.py:
from shared_library import Utils
#    ^^^^^^^^^^^^^^
# Click → finds /project/shared-library/shared_library/utils.py
```

## Resolvability Check

Before showing the underline hover effect, the IDE checks if a symbol is navigable:

**`check_resolvability(reference, file_path, editor, index)`**

Returns `True` if the symbol can be navigated to:
- Is an imported symbol
- Is defined locally (class, function, variable)
- Is a module that exists on disk

Returns `False` for Python builtins implemented in C (`str`, `int`, `len`, `print`, etc.) since they have no Python source.

## File Structure

```
src/
├── navigation/
│   ├── __init__.py
│   ├── code_navigation.py       # Navigation coordinator
│   ├── code_navigation_py.py    # Python navigation logic
│   ├── code_navigation_ts.py    # TypeScript navigation logic
│   ├── code_navigation_tf.py    # Terraform navigation logic
│   ├── navigation_provider.py   # Base provider interface
│   ├── custom_provider.py       # Generic/custom navigation
│   └── terraform_provider.py    # Terraform-specific provider
```

## Critical Behavior: Re-Export Following for Method Calls

**IMPORTANT: This behavior has been lost and restored multiple times. It MUST be preserved.**

When clicking on a method call like `save_item` in:

```python
from python_db_item_handler import DBItemHandler

DBItemHandler(self.value).save_item(item)
```

The navigation MUST:

1. ✅ Detect this is a method call on a class instantiation (`ClassName().method()`)
2. ✅ Extract the class name (`DBItemHandler`)
3. ✅ Find the import: `from python_db_item_handler import DBItemHandler`
4. ✅ Check `python_db_item_handler/__init__.py` for re-exports
5. ✅ Parse: `from .db_item_handler import DBItemHandler`
6. ✅ Open `db_item_handler.py` (NOT `__init__.py`!)
7. ✅ Navigate to `def save_item(...)` in the class

### Why This Matters

If step 5-6 is skipped, the user lands in `__init__.py` where `save_item` doesn't exist. They must manually follow the re-export chain, which defeats the purpose of Cmd+Click navigation.

### Implementation Details

Three code paths in `on_cmd_click()` handle this:

1. **Class instantiation methods**: `ClassName(...).method()`
   - In `code_navigation_py.py`

2. **Variable methods**: `var.method()` where `var = SomeClass()`
   - In `code_navigation_py.py`

3. **Self attribute methods**: `self.attr.method()`
   - In `code_navigation_py.py`

All three paths must call `_resolve_reexport_in_init()` before opening the target file.

### Test Coverage

See `tests/test_go_to_definition.py`:

- `TestReExportNavigation` - Tests re-export pattern parsing and navigation flow
- `TestVariableMethodNavigation` - Tests type inference from variable assignments

Run: `make tests` to verify this behavior is preserved.

## Future Improvements

The navigation code has been extracted from the former `language_service.py` into dedicated files under `src/navigation/`. Further improvements could include LSP integration for more accurate cross-language navigation.
