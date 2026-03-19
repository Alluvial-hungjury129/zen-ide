# Rendering — No Cairo, Use GtkSnapshot

**Created_at:** 2026-03-06  
**Updated_at:** 2026-03-09  
**Status:** Active  
**Goal:** Enforce GtkSnapshot as the only rendering API — ban legacy Cairo usage  
**Scope:** All custom drawing code in `src/`  

---

## Rule

**Never use `cairo`, `PangoCairo`, or `pycairo` in new or modified code.** Cairo is a legacy CPU-only rendering API. All custom drawing must use the GTK4 `GtkSnapshot` API with `Graphene.Rect`, `snapshot.append_color()`, `snapshot.append_layout()`, `GskPathBuilder`, etc. Existing Cairo code is being migrated — see [docs/2026_03_06_cairo_migration.md](../2026_03_06_cairo_migration.md).

## Banned Imports

- `import cairo`
- `from gi.repository import PangoCairo`
- `snapshot.append_cairo()` (bridge API — only allowed in files already using it until migrated)

## Use Instead

- `snapshot.append_color(Gdk.RGBA, Graphene.Rect)` for filled rectangles
- `snapshot.append_layout(Pango.Layout, Gdk.RGBA)` for text rendering
- `snapshot.append_stroke()` / `snapshot.append_fill()` for paths (GTK 4.14+)
- `Pango.FontMap.get_default()` instead of `PangoCairo.font_map_get_default()`
