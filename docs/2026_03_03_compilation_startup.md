# Compilation & Startup Performance

**Created_at:** 2026-03-03  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Analyze whether AOT compilation would improve the ~80ms startup time  
**Scope:** Startup performance, Nuitka/Cython/mypyc trade-offs  

---

This document analyzes whether compiling Zen IDE would improve startup performance.

## Current Startup Profile

Zen IDE already starts in **< 100ms** (Vim-level speed). The startup bottleneck breakdown:

| Phase | What happens | Time |
|-------|-------------|------|
| **Python interpreter launch** | CPython loads, initializes | ~30-40ms |
| **Module imports** | PyGObject, GTK4 bindings, app code | ~20-30ms |
| **Widget creation** | Placeholder layout, deferred init | ~10-20ms |
| **Deferred phases** | Real widgets swapped in via `idle_add` | After first paint |

## What Compilation Would Help

| Approach | Speedup | Why |
|----------|---------|-----|
| **Nuitka** (AOT compile to C) | ~10-20ms saved | Eliminates `.pyc` interpretation overhead, faster module loading |
| **Cython** (compile hot paths) | ~5-10ms saved | Only helps CPU-bound code, startup is mostly I/O-bound |
| **PyInstaller** (bundled) | ❌ Often **slower** | Unpacks to temp dir, adds extraction overhead |
| **mypyc** | ~5-15ms saved | Compiles type-annotated code to C extensions |

## Why Compilation Wouldn't Help Much

1. **GTK4 is already native C** — the heavy lifting (widget rendering, GLib main loop) is compiled code called via GObject Introspection. Python is just the glue.

2. **Deferred init pattern already wins** — Zen's 3-phase lazy loading means Python only runs ~50 lines of code before first paint.

3. **Import overhead is the real cost** — most of that is PyGObject loading `.typelib` files (binary introspection data), not Python interpretation.

4. **The interpreter startup (~30ms) is the floor** — even Nuitka still embeds CPython for PyGObject compatibility.

## What Would Actually Help More

If pushing below the current ~80ms first-paint:

| Optimization | Potential | Notes |
|--------------|-----------|-------|
| **Precompiled `.pyc` cache** | ✅ Already done | Automatic in Python |
| **Lazy import more modules** | ~5-10ms | Defer AI providers |
| **Preload GTK in background** | ~10-20ms | System-level daemon approach |
| **Native C extension for hot paths** | ~5ms | Diminishing returns at this scale |

## Conclusion

**Compilation would save ~10-20ms at best** — taking startup from ~80ms to ~60ms. Given the engineering effort required, the current deferred initialization approach provides better ROI.

The real performance wins come from:
- Keeping imports lazy
- Using placeholder widgets
- Deferring heavy initialization to idle callbacks

See [startup.md](2026_02_27_startup.md) for the full startup architecture documentation.
