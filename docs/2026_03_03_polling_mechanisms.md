# Polling Mechanisms in Zen IDE

**Created_at:** 2026-03-03  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Catalog all polling and timer mechanisms (GLib.timeout_add, idle_add) used throughout the IDE  
**Scope:** `src/shared/main_thread.py`, `src/shared/system_monitor.py`, AI providers  

---

This document catalogs all polling and timer mechanisms used throughout Zen IDE, organized by purpose and location.

## Overview

Zen IDE uses GTK's `GLib` timer APIs for all async/deferred operations:

| API | Purpose |
|-----|---------|
| `GLib.timeout_add(ms, fn)` | Repeating timer or delayed one-shot |
| `GLib.idle_add(fn)` | Defer to next main loop iteration |
| `GLib.source_remove(id)` | Cancel a pending timer |

---

## 1. Continuous Polling (True Polling Loops)

These timers run continuously while their feature is active.

### Main Thread Queue Polling
**File:** `src/shared/main_thread.py`

Polls a thread-safe queue every 50ms to safely execute cross-thread callbacks on the main thread. Required because GLib 2.86+ crashes when `GLib.idle_add()` is called from background threads.

```python
_POLL_INTERVAL_MS = 50
_poll_id = GLib.timeout_add(_POLL_INTERVAL_MS, _poll_queue)
```

### System Monitor Refresh
**File:** `src/shared/system_monitor.py`

Configurable polling interval (1s, 2s, 5s, 10s, 30s) to update CPU/memory/disk stats.

```python
self._update_interval = 2.0  # default
self._timeout_id = GLib.timeout_add(int(self._update_interval * 1000), self._on_timer_tick)
```

### AI Chat Terminal - Subprocess Polling
**File:** `src/ai/ai_chat_terminal.py`

Polls subprocess every 500ms as a backup to PTY HUP signal for detecting AI CLI process completion.

```python
self._process_poll_source = GLib.timeout_add(500, self._poll_subprocess)
```

### AI Chat Terminal - Resize Polling
**File:** `src/ai/ai_chat_terminal.py`

Polls terminal column count every 250ms when visible (GTK4 lacks reliable resize signals).

```python
self._resize_poll_source = GLib.timeout_add(250, self._poll_column_count)
```

### Spinner Animations
Multiple files use 80ms timers for loading spinners:

| File | Variable |
|------|----------|
| `src/ai/ai_chat_terminal.py` | `_spinner_source` |
| `src/ai/ai_chat_tabs.py` | `_spinner_timeout_id` |


```python
self._spinner_source = GLib.timeout_add(80, self._update_spinner)
```

---

## 2. Debounced Operations

These timers delay execution to coalesce rapid events.

### Search Debouncing
| File | Delay | Purpose |
|------|-------|---------|
| `src/popups/global_search_dialog.py` | 300ms | Debounce search query input |
| `src/navigation/code_navigation.py` | 300ms | Debounce go-to-definition lookup |

### Git Status Refresh
**File:** `src/treeview/tree_view.py`

```python
self._git_status_timer = GLib.timeout_add(300, self._do_refresh_git_status)
```

### Diagnostics Manager
**File:** `src/shared/diagnostics_manager.py`

Debounces diagnostic refresh per repository root.

```python
timer_id = GLib.timeout_add(delay_ms, _fire)
self._debounce_timers[repo_root] = timer_id
```

### File Watcher Refresh
**File:** `src/shared/file_watcher.py`

```python
self._pending_refresh_source = GLib.timeout_add(self.DEBOUNCE_DELAY_MS, self._execute_refresh)
```

### Editor Updates
| File | Delay | Purpose |
|------|-------|---------|
| `src/editor/color_preview_renderer.py` | 300ms | Rescan colors after changes |
| `src/editor/gutter_diff_renderer.py` | 500ms | Update git diff markers |
| `src/editor/editor_minimap.py` | 500ms | Update minimap diff |
| `src/editor/editor_view.py` | 300ms | Markdown preview update |
| `src/editor/editor_view.py` | 500ms | OpenAPI preview update |

### Autocomplete Triggers
**File:** `src/editor/autocomplete/autocomplete.py`

```python
self._auto_trigger_timer = GLib.timeout_add(delay_ms, self._show_from_auto_trigger)
self._dismiss_guard_timer = GLib.timeout_add(500, self._clear_dismiss_guard)
```

### Navigation Highlight
**File:** `src/editor/nav_highlight.py`

Clears navigation highlights after timeout.

```python
info["timer_id"] = GLib.timeout_add(HIGHLIGHT_DURATION_MS, _clear)
```

---

## 3. Deferred Initialization (`idle_add`)

These defer work to the next main loop iteration.

### Startup Phases
**File:** `src/main/window_state.py`

```python
GLib.timeout_add(0, self._deferred_init_panels)      # Phase 1
GLib.timeout_add(0, self._deferred_background_init)  # Phase 2
GLib.timeout_add(2000, self._run_workspace_diagnostics)  # Delayed
```

### Widget Initialization
Common pattern across UI components:

```python
GLib.idle_add(self._connect_vadjustment)
GLib.idle_add(self._restore_sessions)
GLib.idle_add(self._apply_styles)
```

### Scroll Operations
Deferred scrolling ensures layout is complete:

```python
GLib.idle_add(lambda: vadj.set_value(saved_scroll) or False)
GLib.idle_add(self._scroll_to_bottom)
```

---

## 4. One-Shot Delays

Fixed-delay timers for specific operations.

### Focus Management
| File | Delay | Purpose |
|------|-------|---------|
| `src/ai/ai_chat_terminal.py` | 150ms | Focus input after action |
| `src/ai/ai_chat_tabs.py` | 150ms | Focus input after tab switch |
| `src/popups/font_picker_dialog.py` | 100ms | Check focus for auto-close |
| `src/popups/global_search_dialog.py` | 100-200ms | Check focus for close |

### Animation & Visual Feedback
| File | Delay | Purpose |
|------|-------|---------|
| `src/editor/editor_view.py` | 16ms | Smooth scroll animation frame |
| `src/shared/utils.py` | 16ms | Paned position animation (~60fps) |
| `src/treeview/tree_panel_keyboard.py` | ~16ms | Smooth scroll animation |
| `src/popups/notification_toast.py` | configurable | Auto-dismiss toast |

### Platform-Specific
| File | Delay | Purpose |
|------|-------|---------|
| `src/editor/preview/markdown_preview.py` | 200ms | macOS WebKit attachment retry |
| `src/editor/preview/openapi_preview.py` | 200ms | macOS WebKit attachment retry |
| `src/main/window_state.py` | 5ms | AppKit readiness check |

---

## 5. Cleanup Patterns

Proper timer cleanup to prevent leaks:

```python
# Cancel before setting new timer
if self._timer_id is not None:
    GLib.source_remove(self._timer_id)
    self._timer_id = None

# Set new timer
self._timer_id = GLib.timeout_add(delay_ms, callback)
```

**Important:** Always store timer IDs and cancel them:
- Before setting a new timer on the same slot
- When the widget/component is destroyed
- When the feature is disabled

---

## Summary Table

| Category | Count | Typical Intervals |
|----------|-------|-------------------|
| Continuous polling | 5 | 50-500ms |
| Debounced operations | 10+ | 100-500ms |
| Deferred init (`idle_add`) | 30+ | Next tick |
| One-shot delays | 15+ | 5-200ms |
| Spinners/animations | 4 | 16-80ms |

---

## Performance Considerations

1. **Main thread poll (50ms)** - Essential for thread safety, minimal overhead
2. **Resize polling (250ms)** - Only active when terminal is visible
3. **Subprocess polling (500ms)** - Backup for PTY HUP, light process check
4. **System monitor** - User-configurable, disabled when dialog closed

All polling respects the principle: **poll only when necessary, stop when feature is inactive.**
