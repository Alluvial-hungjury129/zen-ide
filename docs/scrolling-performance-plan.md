# Scrolling Performance Optimization Plan

Ordered from highest impact & lowest risk to more involved changes.
Each step is implemented one at a time with testing between each.

---

### **Step 1: Add ASCII fast-path to `display_width()`** ✅
**File:** `src/shared/utils.py`
**What:** Add a fast-path for ASCII characters (0x20–0x7E) which covers >95% of code/chat content. Currently every character goes through `unicodedata.category()` + `unicodedata.east_asian_width()` lookups.
**Impact:** Eliminates ~95% of `unicodedata` calls across the entire rendering pipeline (draw, wrap map, mouse hit-testing).
**Risk:** Very low — ASCII chars always have display width 1.

### **Step 2: Cache `Gdk.RGBA` objects for hex color strings** ✅
**File:** `src/ai/chat_canvas.py`
**What:** Replace the `_hex_to_rgba()` static method with a cached version using a simple dict. Currently `Gdk.RGBA.parse()` is called per-span per-frame during `do_snapshot`.
**Impact:** Eliminates ~150+ string parses per frame during scrolling.
**Risk:** Very low — pure memoization of a stateless function.

### **Step 3: Pre-create cached bold/italic `Pango.FontDescription` objects** ✅
**File:** `src/ai/chat_canvas.py`
**What:** Create `_font_desc_bold` and `_font_desc_italic` once in `_measure_font()` and `set_font()`, instead of calling `self._font_desc.copy()` + `set_weight()/set_style()` per styled span per frame.
**Impact:** Eliminates ~100 GObject allocations per frame during scrolling.
**Risk:** Very low — cached font descriptors, updated when font changes.

### **Step 4: Merge adjacent same-background character rects** ✅
**File:** `src/ai/chat_canvas.py`
**What:** In the background pass of `_draw_line()`, merge consecutive characters with the same `span.bg` into a single `Graphene.Rect` + `append_color()` call instead of one per character.
**Impact:** Reduces GObject allocations from ~2000/frame to ~50/frame for code blocks with background colors.
**Risk:** Low — visual result is identical.

### **Step 5: Use `_schedule_redraw()` for scroll events instead of direct `queue_draw()`** ✅
**File:** `src/ai/chat_canvas.py`
**What:** Change `_on_scroll_value_changed` and `_on_page_size_changed` to use the existing `_schedule_redraw()` idle coalescing instead of calling `queue_draw()` directly.
**Impact:** Coalesces rapid-fire scroll events (kinetic scrolling) into fewer actual redraws.
**Risk:** Low — may introduce ~1 frame of latency (16ms), but should feel smoother.

### **Step 6: Populate `_layout_cache` with per-line char_cells + visual rows** ✅
**File:** `src/ai/chat_canvas.py`
**What:** Cache the `char_cells` list and `rows` split for each buffer line in `_layout_cache`, keyed by `line_idx`. Reuse on subsequent frames if the line isn't dirty. The cache is already evicted for dirty lines in `do_snapshot` and cleared entirely on reset, color changes, font changes, and width changes.
**Impact:** Eliminates per-character iteration for unchanged lines (~10,000 character ops/frame → near zero for stable content during pure scrolling).
**Risk:** Medium — must correctly invalidate on dirty lines, width changes, and font changes.
