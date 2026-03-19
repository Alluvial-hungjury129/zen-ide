# Cairo → GtkSnapshot Migration Plan

**Created_at:** 2026-03-06  
**Updated_at:** 2026-03-12  
**Status:** Done  
**Goal:** Remove all `cairo` and `PangoCairo` usage, replace with GtkSnapshot/Pango APIs, and delete the `pycairo` dependency.  
**Scope:** `src/editor/`, `src/sketch_pad/`, `src/tree_view.py`, `src/popups/nvim_popup.py`  

---

## Why

Cairo is a CPU-only 2D rendering library. GTK4's `GtkSnapshot` API uses a scene graph with GPU-accelerated rendering (OpenGL/Vulkan), supports caching, and handles effects natively. In GTK4, Cairo can no longer draw directly to surfaces — it must go through `snapshot.append_cairo()` anyway, adding overhead. Removing Cairo simplifies the dependency tree and improves rendering performance.

## Reference Pattern (Already in Codebase)

`src/shared/block_cursor_draw.py` is the gold standard — pure GtkSnapshot, no Cairo:

```python
from gi.repository import Graphene

rect = Graphene.Rect()
rect.init(x, y, width, height)
snapshot.append_color(color, rect)
```

`src/editor/editor_view.py` `_draw_indent_guides_snapshot()` is another pure-snapshot example using `snapshot.append_color()` with `Graphene.Rect`.

## Inventory

### Files Using Cairo Drawing (`cr.*` calls)

| # | File | Drawing | Cairo APIs | Complexity | Phase |
|---|------|---------|-----------|------------|-------|
| 1 | `src/editor/gutter_diff_renderer.py` | ~~Git diff bars~~ | ~~`set_source_rgba`, `rectangle`, `fill`~~ | **Done** ✅ | 1 |
| 2 | `src/editor/color_preview_renderer.py` | ~~Inline color swatches + checkerboard~~ | ~~`set_source_rgba`, `rectangle`, `fill`, `stroke`~~ | **Done** ✅ | 1 |
| 3 | `src/editor/editor_minimap.py` | ~~Diff/diagnostic markers + viewport~~ | ~~`set_source_rgba`, `rectangle`, `fill`~~ | **Done** ✅ | 1 |
| 4 | `src/editor/preview/diff_view.py` (DiffMinimap) | ~~Diff region markers + viewport~~ | ~~`set_source_rgba`, `rectangle`, `fill`~~ | **Done** ✅ | 1 |
| 5 | `src/editor/editor_view.py` (`_draw_diagnostic_waves`) | ~~Wavy underlines~~ | ~~`save`, `restore`, `set_source_rgba`, `move_to`, `stroke`~~ | **Done** ✅ | 2 |
| 6 | `src/popups/nvim_popup.py` (`_draw_border`) | Rounded rectangle border with title gap | `move_to`, `line_to`, `arc`, `close_path`, `stroke`, `set_source_rgba`, `set_line_width` | **Medium** | 2 |
| 7 | `src/treeview/tree_panel_renderer.py` | Tree item text/icon rendering via PangoCairo | `PangoCairo.create_layout`, `PangoCairo.show_layout`, `set_source_rgba`, `rectangle`, `fill` | **Medium** | 3 |
| 8 | `src/sketch_pad/sketch_canvas.py` | Full ASCII diagram canvas (grid, shapes, arrows, text, selection, guides) | 15+ Cairo APIs + PangoCairo | **Complex** | 4 |

### Files Using `PangoCairo` for Font Queries Only (No Drawing)

| # | File | Usage | Replacement |
|---|------|-------|-------------|
| 9 | `src/fonts/font_manager.py` | `PangoCairo.font_map_get_default()` for font enumeration | `Pango.FontMap.get_default()` (GTK4) |
| 10 | `src/treeview/tree_panel.py` | `PangoCairo.context_get_resolution()`, `PangoCairo.font_map_get_default()` | `Pango.FontMap.get_default()`, widget DPI from `Gdk.Display` |
| 11 | `src/treeview/tree_icons.py` | `PangoCairo.font_map_get_default()` for icon font validation | `Pango.FontMap.get_default()` |
| 12 | `src/popups/font_picker_dialog.py` | `PangoCairo.font_map_get_default()` for listing fonts | `Pango.FontMap.get_default()` |

### Files Using `set_draw_func` for Placeholders Only (Minimal Cairo)

| # | File | Usage | Replacement |
|---|------|-------|-------------|
| 13 | `src/editor/preview/markdown_preview.py` | ~~Placeholder DrawingArea~~ | **Done** ✅ — replaced with `_SyncPlaceholder(Gtk.Widget)` + `do_snapshot()` |
| 14 | `src/editor/preview/openapi_preview.py` | ~~Placeholder DrawingArea~~ | **Done** ✅ — replaced with `_SyncPlaceholder(Gtk.Widget)` + `do_snapshot()` |

### Dependency References

| File | Reference | Action |
|------|-----------|--------|
| `pyproject.toml` dependencies | `"pycairo>=1.25.0"` | Removed ✅ |
| `pyproject.toml` gtk-linux | `"libcairo2-dev"` (Linux system dep) | Removed ✅ |
| `pyproject.toml` line 53 | `"python3-gi-cairo"` (Linux system dep) | Keep — needed by PyGObject GI bindings |
| `pyproject.toml` gtk-macos | `"cairo"` (macOS Homebrew dep) | Removed ✅ (transitive via GTK stack) |

---

## Migration Phases

### Phase 1 — Simple Rectangle Renderers ✅ Done

**Files:** `gutter_diff_renderer.py`, `color_preview_renderer.py`, `editor_minimap.py`, `diff_view.py`

**Pattern:** All use only `cr.set_source_rgba()` + `cr.rectangle()` + `cr.fill()` (and occasionally `cr.stroke()`).

**Migration strategy:**
- Convert `set_draw_func` callbacks to `do_snapshot()` overrides on custom `Gtk.Widget` subclasses, OR keep `Gtk.DrawingArea` but convert internal drawing to snapshot calls
- Replace `cr.rectangle() + cr.fill()` → `snapshot.append_color(Gdk.RGBA, Graphene.Rect)`
- Replace `cr.rectangle() + cr.stroke()` → `snapshot.append_border()` or use `GskRoundedRect`
- For the renderers called from `editor_view.py`'s `do_snapshot()`, change their API to accept `snapshot` instead of `cr`

**Example conversion (gutter_diff_renderer.py):**
```python
# BEFORE (Cairo)
cr.set_source_rgba(r, g, b, 0.9)
cr.rectangle(indicator_x, wy, width, lh)
cr.fill()

# AFTER (GtkSnapshot)
color = Gdk.RGBA()
color.red, color.green, color.blue, color.alpha = r, g, b, 0.9
rect = Graphene.Rect()
rect.init(indicator_x, wy, width, lh)
snapshot.append_color(color, rect)
```

**Estimated effort:** ~1 hour

---

### Phase 2 — Path-Based Renderers ✅ Done

**Files:** `editor_view.py` (diagnostic waves), `nvim_popup.py` (border)

**Migration strategy:**

For **diagnostic wavy underlines** (`editor_view.py`):
- Use `GskPathBuilder` to construct the wavy path
- Create a `GskStroke` for line width
- Use `snapshot.append_stroke(path, stroke, color)` (requires GTK 4.14+)
- Fallback: keep `snapshot.append_cairo()` temporarily if GTK version < 4.14

For **nvim_popup border** (`nvim_popup.py`):
- Option A: Replace Cairo rounded rect with CSS `border` + `border-radius` on the widget (simplest — pure CSS, no drawing code)
- Option B: Use `GskRoundedRect` + `snapshot.append_border()` for programmatic borders
- The title gap can be handled by overlaying an opaque label on top of the border

**Estimated effort:** ~2 hours

---

### Phase 3 — Tree Panel Renderer ✅ Done

**Files:** `tree_panel_renderer.py`, `tree_panel.py`, `tree_icons.py`, `tree_canvas.py` (new)

Migrated all Cairo drawing to GtkSnapshot:
- Created `TreeCanvas(Gtk.DrawingArea)` subclass with `do_snapshot()` override
- Replaced `PangoCairo.create_layout()` + `show_layout()` → `Pango.Layout.new()` + `snapshot.append_layout()`
- Replaced `cr.rectangle() + fill()` → `snapshot.append_color()`
- Replaced `cr.move_to() + line_to() + stroke()` → `Gsk.PathBuilder` + `snapshot.append_stroke()`
- Replaced `cr.arc()` (rounded rects) → `Gsk.RoundedRect` + `snapshot.push_rounded_clip()`
- Replaced `cr.arc()` (circles) → `Gsk.PathBuilder.add_circle()` + `snapshot.append_fill()`
- Replaced `PangoCairo.font_map_get_default()` → `widget.get_pango_context().get_font_map()`
- Replaced `PangoCairo.context_get_resolution()` → `Gtk.Settings.get_property("gtk-xft-dpi")`

---

### Phase 4 — Sketch Canvas ✅ Done

**File:** `sketch_canvas.py` — migrated from `Gtk.DrawingArea` + Cairo to `Gtk.Widget` + `do_snapshot()`.

All 14 drawing methods converted: `_draw_grid`, `_draw_chars`, `_draw_custom_font_texts`, `_draw_selection`, `_draw_arrow_sel`, `_draw_connection_hints`, `_draw_alignment_guides`, `_draw_resize_handles`, `_draw_editing_text`, `_draw_text_cursor`, `_draw_text_selection`, marquee, snap indicators, and `export_to_image` (now uses `Gsk.Renderer.render_texture()` instead of `cairo.ImageSurface`).

---

### Phase 5 — PangoCairo Font Queries ✅ Done

**Files:** `font_manager.py`, `font_picker_dialog.py` — replaced `PangoCairo.font_map_get_default()` with `Pango.FontMap.get_default()`.

---

### Phase 6 — Placeholder DrawingAreas ✅ Done

**Files:** `markdown_preview.py`, `openapi_preview.py`

These use `Gtk.DrawingArea` with `set_draw_func` just as a placeholder surface for macOS WKWebView overlay. Replace with a simple `Gtk.Box` with CSS background styling — no custom drawing needed at all.

**Estimated effort:** ~15 min

---

### Phase 7 — Remove pycairo Dependency ✅ Done

Completed:

1. Removed `"pycairo>=1.25.0"` from `pyproject.toml` dependencies.
2. Removed `"libcairo2-dev"` from Linux system deps.
3. Removed direct `"cairo"` from macOS Homebrew deps.
4. Kept `"python3-gi-cairo"` for GI compatibility on Linux.
5. Verified with repository checks (`make lint` and `make tests`).

---

## Total Estimated Effort

| Phase | Effort | Complexity |
|-------|--------|-----------|
| Phase 1 — Rectangle renderers | ✅ Done | Easy |
| Phase 2 — Path renderers | ✅ Done | Medium |
| Phase 3 — Tree panel | ✅ Done | Medium |
| Phase 4 — Sketch canvas | ✅ Done | Complex |
| Phase 5 — PangoCairo font queries | ✅ Done | Easy |
| Phase 6 — Placeholder DrawingAreas | ✅ Done | Trivial |
| Phase 7 — Remove dependency | 🟢 Ready | Testing |

## GTK Version Requirements

Some GtkSnapshot path APIs require GTK 4.14+:
- `snapshot.append_stroke()` — GTK 4.14
- `snapshot.append_fill()` — GTK 4.14
- `GskPathBuilder` — GTK 4.14
- `GskStroke` — GTK 4.14

Check current GTK version with:
```python
print(f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}")
```

If GTK < 4.14, Phase 2 and Phase 4 path operations must use `snapshot.append_cairo()` as an interim bridge until GTK is updated. Phases 1, 3, 5, 6 work on any GTK4 version.

## Validation Checklist (Per Phase)

- [ ] `make lint` passes
- [ ] `make tests` passes
- [ ] `make run` — visually verify the migrated component renders correctly
- [ ] `make startup-time` — no regression (for components in startup path)
- [ ] No `import cairo` or `PangoCairo` in migrated files
- [ ] No `cr.` calls in migrated files
