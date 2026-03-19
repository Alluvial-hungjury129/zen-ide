# Filesystem Access Centralisation

**Created_at:** 2026-02-17  
**Updated_at:** 2026-03-16  
**Status:** Planned  
**Goal:** Centralize all filesystem operations through well-defined facades instead of scattered direct calls  
**Scope:** `src/shared/`, ~433 filesystem calls across codebase  

---

> Goal: reduce scattered direct filesystem calls across the codebase, route them through
> well-defined facades, and standardise on `pathlib.Path`.

---

## Current State

### Access Inventory (~433 FS calls across `src/`)

| Category | Approx. Calls | Description |
|----------|-------------:|-------------|
| `os.path.*` | 227 | Path checks, joins, directory traversal |
| Pathlib methods (`.exists()`, `.read_text()`, `.glob()`, …) | 102 | Path queries & file I/O |
| `subprocess.*` (git, grep, …) | 40 | External process calls (many touch FS) |
| `open()` | 38 | Direct file read/write |
| `json.load/dump` | 15 | JSON serialisation to/from files |
| `Path()` constructor | 6 | Pathlib path creation |
| `shutil.*` | 5 | File copy/move/delete |

### Top 5 Heaviest Files

| File | ~Calls | Purpose |
|------|-------:|---------|
| `code_navigation.py` | 54 | Symbol indexing, file scanning |
| `zen_ide.py` | 43 | App init, workspace loading, recent files |
| `tree_view.py` | 35 | File explorer directory traversal |
| `status_bar.py` | 25 | Git branch, file info display |
| `ai_chat_terminal.py` | 24 | AI chat history persistence |

> **Note:** Files have since been reorganised — `code_navigation.py` is now at
> `src/navigation/code_navigation.py`, `tree_view.py` at `src/treeview/tree_view.py`.

---

## What Already Has a Facade (✅)

| Facade | File | Used By | Pattern |
|--------|------|---------|---------|
| **GitManager** | `src/shared/git_manager.py` | tree_view, diff_view, code_navigation | Singleton, subprocess-based |
| **SettingsManager** | `src/shared/settings/settings_manager.py` | ~15 files via `get_setting()` / `set_setting()` | Singleton, JSON file at `~/.zen_ide/settings.json` |
| **DevPadStorage** | `src/dev_pad/dev_pad_storage.py` | dev_pad | Singleton, lazy-loading, JSON |
| **CrashLog** | `src/shared/crash_log.py` | zen_ide.py | Pathlib-based, plain text |

---

## What Does NOT Have a Facade (❌)

| Area | Files | Current Approach | Problem |
|------|-------|-----------------|---------|
| **AI chat / model state** | `ai_chat_tabs.py`, `ai_chat_terminal.py` | Direct `os.path`, `json.load/dump`, `open()` | Duplicated JSON read/write, mixed `os.path` vs `Path` |
| **Tree file operations** | `tree_view.py` | Direct `os.path`, `shutil.rmtree()`, `os.makedirs()` | No abstraction for create/rename/delete |
| **Editor file I/O** | `editor_view.py` | Direct `open()` for read/write | No error handling wrapper |
| **Workspace loading** | `zen_ide.py` | Direct `open()`, `os.path.isfile()` | No validation facade |
| **Font cache** | `tree_view.py` | Direct `open()` writing `~/.zen_ide/font_cache.txt` | Belongs in a cache manager |

### Repeated Anti-Patterns

**1. Check-exists-then-read-JSON** — appears in 5+ files:
```python
# This exact pattern is copy-pasted across ai_chat_tabs,
# dev_pad_storage, settings_manager
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
```

**2. Create `~/.zen_ide` subdirectories** — appears in 5 files:
```python
# Each file independently ensures its own subdirectory exists
os.makedirs(os.path.dirname(cache_file), exist_ok=True)
# or
Path.home().joinpath(".zen_ide", "subdir").mkdir(parents=True, exist_ok=True)
```

**3. Mixed path libraries** — `os.path` vs `pathlib.Path` used inconsistently:
- `pathlib`: settings_manager, dev_pad_storage, crash_log
- `os.path`: tree_view, zen_ide, git_ignore_utils

---

## Proposed Architecture

### New Modules

```
src/shared/
├── file_ops.py           # Low-level file operations facade
├── json_store.py         # JSON persistence helper
├── ai_state_manager.py   # AI chat/model state persistence
└── workspace_manager.py  # Workspace file loading/validation
```

### 1. `file_ops.py` — File Operations Facade

Single point of contact for all raw filesystem operations outside of git.

```python
from pathlib import Path
from constants import ZEN_IDE_CONFIG_DIR

def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path

def read_text(path: Path, default: str = "") -> str:
    """Read a text file, returning default if missing."""
    ...

def write_text(path: Path, content: str) -> None:
    """Write text to file, creating parent dirs as needed."""
    ...

def remove(path: Path) -> bool:
    """Remove file or directory tree. Returns True if removed."""
    ...

def list_dir(path: Path, recursive: bool = False) -> list[Path]:
    """List directory contents, optionally recursive."""
    ...
```

### 2. `json_store.py` — JSON Persistence Helper

Eliminates the check-exists-then-read-JSON anti-pattern.

```python
from pathlib import Path

class JsonStore:
    """Thread-safe JSON file persistence."""

    def __init__(self, path: Path, defaults: dict | None = None):
        self._path = path
        self._defaults = defaults or {}

    def load(self) -> dict:
        """Load JSON from file, returning defaults if missing/corrupt."""
        ...

    def save(self, data: dict) -> None:
        """Atomically write JSON to file."""
        ...

    def update(self, **kwargs) -> dict:
        """Load, merge kwargs, save, and return result."""
        ...
```

### 3. `ai_state_manager.py` — AI State Persistence

Replaces scattered JSON calls in `ai_chat_tabs.py`, `ai_chat_terminal.py`.

```python
class AIStateManager:
    """Centralised persistence for AI chat state."""

    def get_model_cache(self) -> dict: ...
    def save_model_cache(self, data: dict) -> None: ...
    def get_chat_sessions(self) -> list[dict]: ...
    def save_chat_session(self, session: dict) -> None: ...
    def get_chat_messages(self, session_id: str) -> list[dict]: ...
    def save_chat_messages(self, session_id: str, messages: list[dict]) -> None: ...
```

### 4. Constants Update

Add to `src/constants.py`:

```python
from pathlib import Path

ZEN_IDE_CONFIG_DIR = Path.home() / ".zen_ide"
```

All modules reference this instead of computing it independently.

---

## Migration Plan

### Phase 0 — Foundation (no behaviour change)

| Task | Effort | Risk |
|------|--------|------|
| Add `ZEN_IDE_CONFIG_DIR` to `constants.py` | S | None |
| Create `file_ops.py` with utility functions | S | None |
| Create `json_store.py` | S | None |
| Add unit tests for `file_ops.py` and `json_store.py` | S | None |

### Phase 1 — Low-Risk Migrations

Migrate modules that already have a facade or singleton pattern. Swap internal
implementation without changing public API.

| Module | Change | Effort |
|--------|--------|--------|
| `settings_manager.py` | Replace internal `open()`/`json.load` with `JsonStore` | S |
| `dev_pad_storage.py` | Replace internal JSON persistence with `JsonStore` | S |
| `crash_log.py` | Replace `Path` read/write with `file_ops` | S |

**Validation**: `make tests` — no public API changes.

### Phase 2 — AI State Consolidation

Highest impact migration. Eliminates the most duplication.

| Module | Change | Effort |
|--------|--------|--------|
| Create `ai_state_manager.py` | New facade using `JsonStore` | M |
| `ai_chat_tabs.py` | Replace direct FS calls with `AIStateManager` | M |
| `ai_chat_terminal.py` | Replace direct FS calls with `AIStateManager` | M |

**Validation**: `make tests` + manual AI chat test (open/close sessions, switch models).

### Phase 3 — Tree & Editor I/O

These are the most sensitive paths — user data at risk.

| Module | Change | Effort |
|--------|--------|--------|
| `tree_view.py` | Replace `shutil`, `os.makedirs`, `os.path` with `file_ops` | M |
| `editor_view.py` | Route file read/write through `file_ops` | M |
| `zen_ide.py` | Route workspace loading through `file_ops` | M |
| `tree_view.py` font cache | Move to `JsonStore` or `file_ops.write_text` | S |

**Validation**: `make tests` + manual file create/rename/delete, open workspace.

### Phase 4 — Standardise on `pathlib.Path`

Convert remaining `os.path` usages to `pathlib.Path`.

| Module | Change | Effort |
|--------|--------|--------|
| `git_ignore_utils.py` | Replace `os.path` with `Path` | S |
| `file_watcher.py` | Replace `os.path` with `Path` | S |
| `code_navigation.py` | Replace `os.path` with `Path` | M |
| `status_bar.py` | Replace `os.path` with `Path` | S |

**Validation**: `make tests` + `make lint`.

### Phase 5 — Enforce via Lint Rule

Add a custom lint check (or ruff rule) that flags direct `open()`, `os.path`,
`shutil`, and `json.load/dump` calls in `src/` (excluding `src/shared/file_ops.py`
and `src/shared/json_store.py`).

---

## Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| Files with direct `open()` | 16 | 2 (`file_ops.py`, `json_store.py`) |
| Files with `os.path.*` | 26 | ≤5 (legacy/justified) |
| Duplicated JSON read/write patterns | 5+ | 0 |
| `~/.zen_ide` dir creation points | 5 | 1 (`constants.py` or `file_ops.py`) |
| Path library consistency | Mixed | `pathlib.Path` everywhere |

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Regression in file save/load | Each phase validated with `make tests` + manual smoke test |
| Performance overhead from abstraction | `file_ops` is a thin wrapper, no caching layer added unless needed |
| Breaking git operations | Git stays in `git_manager.py` — no changes to that facade |
| Atomic write failures | `json_store.py` writes to temp file + rename (atomic on POSIX) |
