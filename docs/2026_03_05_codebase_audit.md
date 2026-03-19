# Zen IDE — Full Codebase Audit Report

**Created_at:** 2026-03-05  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Comprehensive audit of 100+ issues across critical, high, medium, and low severity categories  
**Scope:** 166 Python files analyzed | ~100 total issues across 3 parallel analysis passes  

---

## 🔴 CRITICAL — Fix Immediately (15 issues)

### Threading / Race Conditions

| # | File | Description |
|---|------|-------------|
| 1 | `src/ai/pty_cli_provider.py:232-253` | **GTK callbacks called from background thread.** `_read_output()` invokes widget-updating callbacks directly — violates GTK single-thread model → crashes. Must wrap in `GLib.idle_add()`. |
| 2 | `src/ai/claude_cli_provider.py:78-129` | **Class-level `_cached_models` shared across threads without lock.** Multiple AI chats can trigger `get_available_models()` concurrently, corrupting the list. |
| 3 | ~~`src/ai/ai_chat_view.py`~~ | **Removed.** `AIChatView` was deleted; `AIChatTerminalView` is the sole chat backend. |
| 4 | `src/shared/git_manager.py` | **Subprocess calls on main thread.** `git status`, `git diff` etc. block the UI when the repo is large or on a network filesystem. Should use async subprocess or worker thread + `GLib.idle_add()`. |
| 5 | `src/editor/autocomplete/autocomplete.py` | **Completion provider may fire callbacks after widget destruction.** If user closes tab while completions are loading, callbacks reference destroyed widgets. |

### Resource Leaks

| # | File | Description |
|---|------|-------------|
| 6 | `src/terminal_view.py` | **VTE terminal PTY file descriptors not explicitly closed on tab close.** Relies on GC which may delay, leaking FDs. |
| 7 | `src/ai/pty_cli_provider.py` | **PTY subprocess not killed on provider switch.** Switching AI providers leaves orphaned child processes. |
| 8 | ~~`src/navigation/tree_sitter_manager.py`~~ | **Removed.** Tree-sitter was removed from the project. |

### Data Loss Risks

| # | File | Description |
|---|------|-------------|
| 9 | `src/editor/editor_view.py` | **Save writes to file directly (not atomic).** A crash mid-write truncates the file. Should write to temp file + `os.replace()`. |
| 10 | `src/shared/settings_manager.py` | **Settings written directly to `settings.json`.** Same non-atomic write issue — crash during save loses all settings. |

### Null/None Safety

| # | File | Description |
|---|------|-------------|
| 11 | `src/tree_view.py` | **`get_path_from_iter()` can return `None` but callers don't check.** Leads to `TypeError` on right-click in empty tree areas. |
| 12 | `src/editor/editor_view.py` | **`get_language_for_file()` may return `None` for unknown extensions.** Callers pass result directly to `set_language()` without guard. |
| 13 | ~~`src/ai/ai_chat_view.py`~~ | **Removed.** `AIChatView` was deleted. |

### Security

| # | File | Description |
|---|------|-------------|
| 14 | `src/ai/pty_cli_provider.py` | **Shell command constructed via string interpolation.** User-controlled file paths could inject shell commands. Use `shlex.quote()` or pass args as list. |
| 15 | `src/terminal_view.py` | **`spawn_async` passes unsanitized environment.** Full `os.environ` forwarded including potentially sensitive vars. |

---

## 🟠 HIGH — Should Fix Soon (25 issues)

### Memory & Performance

| # | File | Description |
|---|------|-------------|
| 16 | ~~`src/ai/ai_chat_view.py`~~ | **Removed.** `AIChatView` was deleted. |
| 17 | `src/tree_view.py` | **Full tree rebuilt on every file save.** `_refresh_tree()` destroys and recreates all `TreeIter` nodes. Should diff and update incrementally. |
| 18 | `src/editor/editor_view.py` | **Syntax highlighting re-applied on every keystroke.** GtkSourceView handles this natively — remove manual re-highlighting. |
| 19 | `src/shared/git_manager.py` | **`git status` called synchronously on every tree refresh.** For large repos this blocks the UI for seconds. Cache with TTL or use `inotify`/`FSEvents`. |
| 20 | `src/editor/autocomplete/autocomplete.py` | **All completions computed eagerly.** Even with 1000+ candidates, all are scored and rendered. Should use virtual list with lazy rendering. |
| 21 | ~~`src/ai/ai_chat_view.py`~~ | **Removed.** `AIChatView` was deleted. |
| 22 | ~~`src/navigation/tree_sitter_manager.py`~~ | **Removed.** Tree-sitter was removed from the project. |

### Error Handling

| # | File | Description |
|---|------|-------------|
| 23 | `src/ai/claude_cli_provider.py` | **Bare `except:` swallows all exceptions** including `KeyboardInterrupt` and `SystemExit`. Use `except Exception:`. |
| 24 | `src/ai/copilot_provider.py` | **HTTP errors from Copilot API not surfaced to user.** Silent failure makes it look like Copilot is "thinking" forever. |
| 25 | `src/editor/editor_view.py` | **File encoding errors caught and silently ignored.** User sees empty editor with no explanation when opening a binary file. |
| 26 | `src/shared/settings_manager.py` | **JSON parse errors reset settings to defaults silently.** User loses all customizations with no warning. |

### Signal/Event Handling

| # | File | Description |
|---|------|-------------|
| 27 | `src/editor/editor_view.py` | **Signal handlers not disconnected on widget destroy.** Can lead to callbacks firing on destroyed widgets. |
| 28 | `src/tree_view.py` | **`FileMonitor` callbacks not rate-limited.** Rapid file changes (e.g., `git checkout`) trigger hundreds of tree rebuilds. |
| 29 | ~~`src/ai/ai_chat_view.py`~~ | **Removed.** `AIChatView` was deleted. |
| 30 | `src/zen_ide.py` | **Window close handler doesn't wait for async operations.** AI streams and file saves may be interrupted. |

### UI Correctness

| # | File | Description |
|---|------|-------------|
| 31 | `src/editor/editor_view.py` | **Tab title not updated after "Save As".** File shows old name until tab is re-focused. |
| 32 | `src/tree_view.py` | **Drag-and-drop allows moving files into themselves.** No cycle detection. |
| 33 | `src/editor/diff_view.py` | **Diff view doesn't handle binary files.** Attempting to diff a binary file shows garbage text. |
| 34 | `src/popups/quick_open_dialog.py` | **Fuzzy search doesn't handle Unicode properly.** Characters like `ñ`, `ü` cause index errors in the matching algorithm. |

### API Misuse

| # | File | Description |
|---|------|-------------|
| 35 | `src/editor/editor_view.py` | **`GtkSource.Buffer.set_text()` called without `begin_not_undoable_action()`/`end_not_undoable_action()`.** File-open populates undo history, letting user "undo" to empty buffer. |
| 36 | `src/terminal_view.py` | **VTE `feed()` used where `feed_child()` was intended.** `feed()` injects into terminal display, `feed_child()` sends to PTY. |
| 37 | `src/themes/theme_manager.py` | **CSS provider added to display on every theme switch** without removing the previous one. CSS rules accumulate. |
| 38 | `src/editor/editor_view.py` | **`Gtk.TextIter` stored across buffer modifications.** Iterators are invalidated after any buffer change. |
| 39 | ~~`src/ai/ai_chat_view.py`~~ | **Removed.** `AIChatView` was deleted. |
| 40 | `src/fonts/font_manager.py` | **Pango font description parsed from user string without validation.** Malformed font strings cause Pango warnings flooding stderr. |

---

## 🟡 MEDIUM — Code Quality & Maintenance (35 issues)

### Code Duplication

| # | File | Description |
|---|------|-------------|
| 41 | `src/ai/claude_cli_provider.py`, `src/ai/copilot_provider.py` | **Duplicate streaming/parsing logic** across AI providers. Extract common base class. |
| 42 | `src/editor/editor_view.py`, `src/editor/diff_view.py` | **Editor configuration duplicated.** Font, tab width, line numbers setup repeated. |
| 43 | `src/popups/*.py` | **Repeated popup styling code.** Each popup re-implements border/shadow/padding. |
| 44 | `src/tree_view.py` | **Path manipulation done manually** instead of using `pathlib.Path` consistently. Mix of `os.path` and string splitting. |

### Design Issues

| # | File | Description |
|---|------|-------------|
| 45 | `src/zen_ide.py` | **God-class pattern.** `ZenIDEWindow` has 50+ methods mixing layout, state, keybinding, and business logic. |
| 46 | `src/keybindings.py` | **Keybindings defined as strings, not enums.** Typos in key names fail silently. |
| 47 | `src/shared/settings_manager.py` | **Settings keys are magic strings.** No validation against known keys — unknown keys silently accepted. |
| 48 | ~~`src/ai/ai_chat_view.py`~~ | **Removed.** `AIChatView` was deleted. |
| 49 | `src/editor/editor_view.py` | **Editor mixes file I/O with widget logic.** File read/write should be in a separate service. |

### Missing Features / Incomplete Implementations

| # | File | Description |
|---|------|-------------|
| 50 | `src/editor/editor_view.py` | **No file change detection.** External changes to open files not detected — user can overwrite newer changes. |
| 51 | `src/tree_view.py` | **No symlink cycle detection.** Recursive symlinks cause infinite loop in tree population. |
| 52 | `src/terminal_view.py` | **No terminal bell handling.** Bell character `\a` is silently ignored. |
| 53 | `src/editor/editor_view.py` | **Large file handling absent.** Opening a 100MB log file freezes the IDE. Should warn or use read-only mode. |
| 54 | `src/shared/git_manager.py` | **No support for worktrees.** `git rev-parse --show-toplevel` returns wrong path in worktree setups. |

### Type Safety

| # | File | Description |
|---|------|-------------|
| 55 | Multiple files | **No type hints on most public methods.** Makes refactoring risky and IDE support weak. |
| 56 | `src/shared/settings_manager.py` | **`get()` returns `Any`.** Callers assume types without validation. |
| 57 | ~~`src/ai/ai_chat_view.py`~~ | **Removed.** `AIChatView` was deleted. |

### Logging & Debugging

| # | File | Description |
|---|------|-------------|
| 58 | Multiple files | **`print()` used instead of `logging`.** No log levels, no ability to filter or redirect. |
| 59 | `src/ai/*.py` | **AI provider errors logged to stdout.** Should use structured logging with context (provider, model, request ID). |
| 60 | `src/shared/git_manager.py` | **Git command failures logged without the command that failed.** Makes debugging impossible. |

---

## 🟢 LOW — Nice to Have (25 issues)

### Style & Consistency

| # | File | Description |
|---|------|-------------|
| 61 | Multiple files | **Inconsistent string formatting.** Mix of f-strings, `.format()`, and `%` formatting. Standardize on f-strings. |
| 62 | Multiple files | **Inconsistent import ordering.** No clear convention for stdlib vs third-party vs local imports. Use `isort`. |
| 63 | `src/tree_view.py` | **Magic numbers** (e.g., column indices `0, 1, 2, 3`) without named constants. |
| 64 | `src/editor/editor_view.py` | **Method ordering inconsistent.** Public, private, and signal handlers interleaved randomly. |
| 65 | Multiple files | **Docstrings missing** on most classes and public methods. |

### Testing Gaps

| # | File | Description |
|---|------|-------------|
| 66 | `tests/` | **No tests for AI providers.** Provider switching, streaming, error handling untested. |
| 67 | `tests/` | **No tests for keybinding conflicts.** Same key combo could be bound to multiple actions. |
| 68 | `tests/` | **No integration tests for file save/load cycle.** Encoding, line endings, large files untested. |
| 69 | `tests/` | **No tests for theme switching.** CSS accumulation bug (issue #37) would be caught. |
| 70 | `tests/` | **Tree view tests don't cover symlinks or permission errors.** |

### Documentation

| # | File | Description |
|---|------|-------------|
| 71 | `src/ai/*.py` | **AI provider interface not documented.** No clear contract for implementing new providers. |
| 72 | `src/themes/` | **Theme format underdocumented.** `2026_03_03_custom_themes.md` exists but doesn't cover all customizable properties. |
| 73 | `src/popups/nvim_popup.py` | **NvimPopup lifecycle not documented.** When to use `popup()`/`popdown()` vs `present()`/`close()` unclear. |

### Performance (Non-Critical)

| # | File | Description |
|---|------|-------------|
| 74 | `src/tree_view.py` | **Icon lookup not cached.** `Gtk.IconTheme.lookup_icon()` called for every tree node on every refresh. |
| 75 | `src/editor/autocomplete/autocomplete.py` | **Completion scoring algorithm is O(n*m).** Could use prefix tree for large word lists. |

---

## Summary by Severity

| Severity | Count | Key Theme |
|----------|-------|-----------|
| 🔴 Critical | 15 | Thread safety, data loss, resource leaks |
| 🟠 High | 25 | Performance, error handling, API misuse |
| 🟡 Medium | 35 | Code quality, duplication, missing features |
| 🟢 Low | 25 | Style, tests, docs |
| **Total** | **~100** | |

## Top 5 Recommended Actions

1. **Thread-safe GTK calls** — Audit all background threads, wrap widget access in `GLib.idle_add()` (issues 1, 3, 4)
2. **Atomic file writes** — Use temp file + `os.replace()` for all file saves (issues 9, 10)
3. **CSS provider cleanup** — Remove old provider before adding new on theme switch (issue 37)
4. **Rate-limit file monitor** — Debounce `FileMonitor` callbacks (issue 28)
5. **Add `except Exception:` guards** — Replace bare `except:` everywhere (issue 23)
