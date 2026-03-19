# Startup Optimisation Plan v2

**Created_at:** 2026-03-13  
**Updated_at:** 2026-03-14  
**Status:** Active  
**Goal:** Reduce Full UI visible from ~85ms to <70ms  
**Scope:** `src/main/window_state.py`, `src/main/window_layout.py`  

---

## Current Baseline

| Metric | Current | Target |
|--------|---------|--------|
| First paint | ~80ms | — |
| Interactive | ~81ms | — |
| Full UI visible | ~85ms | **< 70ms** |

Timer starts in `do_activate()` — GTK framework overhead excluded.

---

## Lesson from v1 (Rejected)

Splitting `_on_window_mapped` into two GLib event-loop iterations (via
`GLib.timeout_add(0, ...)`) regressed Full UI visible from ~85ms → 129ms.
The ~44ms GLib transition overhead makes multi-iteration splits counterproductive.

**Constraint:** All visible-content work must stay in one synchronous batch
inside `_on_window_mapped`. We can only save time by **removing work from the
batch**, not by deferring it to another GLib iteration.

---

## What's Already Optimised

- ✅ AppKit pre-loaded in background thread (~200ms hidden)
- ✅ Workspace I/O pre-loaded in background thread
- ✅ Font `.ttf` pre-registered via ctypes before GTK init
- ✅ `GDK_BACKEND=macos` hint (saves ~25ms)
- ✅ GTK animations disabled during startup
- ✅ Placeholder swap-out for heavy widgets
- ✅ Lazy properties for optional panels
- ✅ Heavy modules pre-imported in `do_activate()` before timer
- ✅ `register_resource_fonts()` already short-circuits when pre-registered

---

## Critical Path Breakdown

```
_on_window_mapped()                          ← first paint (~80ms from timer)
├── _deferred_init_editor()                  ~5ms    (VISIBLE — keep)
│   └── EditorView() + callbacks + split panels
├── _create_actions()                        ~3–5ms  (INVISIBLE — defer)
├── _bind_shortcuts()                        ~2–3ms  (INVISIBLE — defer)
├── _setup_key_handler()                     ~0.5ms  (INVISIBLE — defer)
├── register_resource_fonts()                ~0ms    (already short-circuits)
├── _apply_theme() full CSS                  ~3–5ms  (PARTIALLY VISIBLE)
│   └── 57 CSS rules, only ~15 visible at startup
├── subscribe_font_change()                  ~0ms
├── TreeView() + setup                       ~3–5ms  (VISIBLE — keep)
├── _reapply_saved_positions()               ~0.5ms  (called twice — dedup)
├── focus tracking controllers               ~1–2ms  (INVISIBLE — defer)
├── ── "Fully loaded" ──                     ← ~83ms
├── _init_workspace_and_files()              ~3–5ms  (VISIBLE — keep)
└── ── "Full UI visible" ──                  ← ~85ms
```

Work in `_on_window_mapped` is ~20ms. Target: remove ~15ms of invisible work.

---

## Proposed Optimisations

### O1. Move actions/shortcuts/key handler to `_deferred_init_panels` (saves ~5–8ms)

**Risk:** LOW | **Effort:** 30min

`_create_actions()` creates 40+ GAction objects. `_bind_shortcuts()` registers
30+ keyboard accelerators. `_setup_key_handler()` adds a key event controller.
None of these produce visible output — they only enable keyboard interaction.

The user physically cannot press a key within 130ms of the window appearing.
These are safe to move to `_deferred_init_panels` (which already runs via
`GLib.timeout_add(0, ...)`).

**File:** `src/main/window_state.py`, `_on_window_mapped()` lines 32–36

**Change:** Remove from `_on_window_mapped`, add to `_deferred_init_panels`.

---

### O2. Move focus tracking controllers to `_deferred_init_panels` (saves ~1–2ms)

**Risk:** LOW | **Effort:** 15min

Focus tracking creates `Gtk.EventControllerFocus` instances and connects
signals. These are invisible — they only track which panel the user clicks.
No user interaction happens during startup.

**File:** `src/main/window_state.py`, `_on_window_mapped()` lines 57–81

**Change:** Move to `_deferred_init_panels`.

---

### O3. Minimal CSS on critical path, full CSS deferred (saves ~2–4ms)

**Risk:** LOW | **Effort:** 1h

`_apply_theme()` generates ~380 lines of CSS covering 57 rules, including
popovers, searchbar, dropdown, switch, checkbutton, spinbutton, scrollbar,
destructive-action buttons, focus rings — none of which exist at startup.

Split into two phases:
1. **Critical CSS** (~15 rules): window, sidebar, editor, terminal, paned
   separator, headerbar, notebook tabs, accent colors, nerd font — applied
   in `_on_window_mapped`
2. **Full CSS** (all rules): applied in `_deferred_init_panels` via the
   existing `_apply_theme()` method

**File:** `src/main/window_layout.py`, `_apply_theme()`

**Change:** Add `_apply_startup_theme()` with critical-only rules. Call it in
`_on_window_mapped` instead of `_apply_theme()`. Call `_apply_theme()` in
`_deferred_init_panels` for the full CSS.

---

### O4. Remove redundant `_reapply_saved_positions()` (saves ~0.5ms)

**Risk:** LOW | **Effort:** 5min

Called twice: once at end of `_deferred_init_editor()` (line 221) and again
after TreeView setup (line 55). The second call overwrites the first. Remove
the first call.

**File:** `src/main/window_state.py`, line 221

---

## Expected Savings

| # | Optimisation | Savings | Risk |
|---|-------------|---------|------|
| O1 | Move actions/shortcuts to deferred | ~5–8ms | LOW |
| O2 | Move focus tracking to deferred | ~1–2ms | LOW |
| O3 | Minimal startup CSS | ~2–4ms | LOW |
| O4 | Remove redundant position reapply | ~0.5ms | LOW |
| | **Total** | **~9–15ms** | |

**Projected:** 85ms − 12ms = **~73ms** (optimistic **~70ms**)

If still above 70ms after O1–O4, fallback options:
- Pre-create EditorView/TreeView in `do_activate()` before timer (~9–15ms, MEDIUM risk)
- Reduce `_create_layout()` widget count (~2–3ms, MEDIUM risk)

---

## Implementation Notes

- All moved work goes into `_deferred_init_panels` which already runs via
  `GLib.timeout_add(0, ...)` — no new GLib iterations added
- `_on_window_mapped` stays as one synchronous batch
- No visual changes — only invisible work is moved
- Theme/font subscription stays in `_on_window_mapped` (already ~0ms cost)

---

## How to Measure

```bash
make run
```

Run 5 times and check the `⚡ [ZEN]` timing lines in stdout.
