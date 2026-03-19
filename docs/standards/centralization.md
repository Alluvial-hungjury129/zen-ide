# Centralization — No Hardcoding

**Created_at:** 2026-01-03  
**Updated_at:** 2026-03-14  
**Status:** Active  
**Goal:** Enforce centralized configuration, git operations, gitignore matching, and utility functions  
**Scope:** `src/shared/settings/default_settings.py`, `src/constants.py`, `src/themes/`, `src/keybindings.py`, `src/fonts/`, `src/shared/git_manager.py`, `src/shared/git_ignore_utils.py`, `src/shared/utils.py`  

---

## No Hardcoding — Centralize Configuration

**Never hardcode values directly in components.** Constants, defaults, and configurations must be centralized:

| Type | Location |
|------|----------|
| User-configurable defaults | `src/shared/settings/default_settings.py` |
| Immutable code constants | `src/constants.py` |
| Colors, themes | `src/themes/` |
| Key bindings | `src/keybindings.py` |
| Font defaults | `src/fonts/` |

### `default_settings.py` vs `constants.py`

These two files serve **distinct purposes** — never confuse them:

**`src/shared/settings/default_settings.py`** — Single source of truth for **user-configurable** default values. It defines the `DEFAULT_SETTINGS` template that seeds `~/.zen_ide/settings.json`. Users can override any value there. If a setting should be adjustable by the user at runtime (via `settings.json`), it belongs here.

**`src/constants.py`** — Single source of truth for **immutable** code constants. These are values that should not be scattered as magic numbers across the codebase, but are **not intended to be changed by users** — they are baked into the Python code. Examples: cursor blink timing, scroll speeds, indent guide opacity, minimum window sizes.

**Rule of thumb:** Ask "should a user be able to change this in `settings.json`?"
- **Yes** → put it in `default_settings.py`
- **No** → put it in `constants.py`

**Never duplicate** a value across both files. A setting lives in exactly one place.

## Git Operations — Use `git_manager.py`

**Never call git subprocess commands directly in components.** All git operations must go through the `GitManager` facade in `src/shared/git_manager.py`.

```python
# BAD - direct subprocess call in component
result = subprocess.run(["git", "rev-parse", "--show-toplevel"], ...)

# GOOD - use git_manager facade
from shared.git_manager import get_git_manager
git = get_git_manager()
repo_root = git.get_repo_root(file_path)
```

## Gitignore Matching — Use `git_ignore_utils.py`

**Use `GitIgnoreUtils` for all .gitignore pattern matching.** The class in `src/shared/git_ignore_utils.py` handles parsing and matching paths against `.gitignore` patterns.

```python
from shared.git_ignore_utils import should_skip, get_matcher

# Simple check
if should_skip(file_path, workspace_roots):
    continue  # Skip this file
```

## Utility Functions — Use `shared/utils.py`

**Never hardcode utility functions in standalone files.** Generic helpers (color conversions, string manipulation, math, parsing, etc.) must live in `src/shared/utils.py`, not be defined privately inside individual components.

Before writing a new helper, check if `shared/utils.py` already provides it. If you find a utility buried in a component file, move it to `shared/utils.py` and have the original delegate to the shared version.

```python
# BAD - private utility hidden in a component
class StatusBar:
    def _contrast_color(self, hex_color):
        r, g, b = hex_to_rgb(hex_color)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return "#000000" if luminance > 128 else "#ffffff"

# GOOD - shared utility importable by any module
from shared.utils import contrast_color
```
