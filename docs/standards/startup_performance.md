# Startup Performance — Zero Regression Policy

**Created_at:** 2026-01-23  
**Updated_at:** 2026-03-15  
**Status:** Active  
**Goal:** Maintain Vim-level startup speed with hard performance limits — no regressions accepted  
**Scope:** `src/zen_ide.py`, `src/main/window_layout.py`, `src/main/window_state.py`, all top-level imports  

---

## Hard Limits

**Zen IDE must maintain Vim-level startup speed. This is a hard requirement — no regressions accepted.**

| Metric | Hard Limit | Description |
|--------|-----------|-------------|
| First paint | < 70ms | Window visible with stub titlebar + placeholder layout |
| Interactive | < 80ms | Editor created and ready for input |
| Fully loaded | < 80ms | Editor + tree + shortcuts + theme ready, IDE is usable |
| Full UI visible | < 90ms | All visible panels created, workspace loaded |

**Before merging any change that touches the startup path, run `make startup-time` and verify metrics stay within limits.**

## Startup Path

The startup path includes:

- `src/zen_ide.py` (module-level imports and `ZenIDEWindow.__init__`)
- `src/main/window_layout.py` (`_create_layout`)
- `src/main/window_state.py` (`_on_window_mapped`, `_deferred_init`, `_deferred_init_phase2`, `_deferred_init_phase3`)
- Any module imported at the top level of the above files

## Rules for Startup-Safe Code

1. **Never add module-level imports of heavy modules** — defer imports to the function/phase where they're first needed. Heavy modules include: `AppKit`, AI providers, font enumeration, `asyncio`, `pyte`
2. **Never create real widgets in `_create_layout()`** — use `Gtk.Box()` placeholders and swap in real widgets during `_deferred_init`
3. **Use a stub titlebar before present()** — a lightweight `Gtk.Box` stub is set as titlebar in `_create_layout()`. The real `Gtk.HeaderBar` is swapped in after first paint via `_ensure_header_bar()` (~2ms swap vs ~13ms HeaderBar realization penalty)
4. **Defer `editor_split_paned` to Phase 2** — the split paned wrapper is created in `_deferred_init_editor()`, not in `_create_layout()`, to reduce the pre-paint widget count
5. **Never do I/O or subprocess calls before first paint** — defer to `_deferred_init` or later phases
6. **New panels must use lazy `@property` initialization** — follow the pattern of `diff_view`, `dev_pad`
7. **Open files one-per-idle-tick** — use `GLib.idle_add()` batching, never open multiple files synchronously

See [docs/2026_02_27_startup.md](../2026_02_27_startup.md) for the full startup architecture documentation.
