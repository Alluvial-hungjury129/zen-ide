# Preview Canvas Migration — WebKit → ChatCanvas

**Created_at:** 2026-03-13  
**Updated_at:** 2026-03-13  
**Status:** Active  
**Goal:** Replace WebKit-based markdown and OpenAPI previews with a unified native ChatCanvas renderer for pixel-perfect scrolling and consistent theming  
**Scope:** `src/ai/chat_canvas.py`, `src/ai/terminal_markdown_renderer.py`, `src/editor/preview/markdown_preview.py`, `src/editor/preview/openapi_preview.py`  

---

## Problem

The markdown and OpenAPI preview panes use WebKit (Linux) / WKWebView (macOS) to render HTML. This causes:

1. **Scroll drift** — Editor and preview live in different coordinate systems. Scroll sync relies on fraction-based JS↔Python bridging with 150ms echo guards that still drift because editor line heights ≠ preview element heights.
2. **OpenAPI has zero scroll sync** — Never implemented.
3. **Cross-process overhead** — WebKit runs in a separate process; communication is async JS evaluation with no guaranteed latency.
4. **Theming inconsistency** — Preview CSS must be manually kept in sync with the GTK editor theme.
5. **Startup cost** — WebKit process spin-up adds to first-preview latency.

Meanwhile, the AI chat already uses `ChatCanvas` — a `Gtk.DrawingArea` that renders ANSI-styled text via `GtkSnapshot` + Pango inside a native `ScrolledWindow`. Scrolling is pixel-perfect for free because both editor and preview are GTK widgets in the same coordinate system.

---

## Current Architecture

| Component | File | Renderer | Scroll Sync |
|-----------|------|----------|-------------|
| AI Chat | `src/ai/chat_canvas.py` | `ChatCanvas(Gtk.DrawingArea)` + GtkSnapshot | ✅ Native ScrolledWindow |
| Markdown Preview | `src/editor/preview/markdown_preview.py` | WebKit / WKWebView / GtkTextView | ⚠️ Fraction-based, drifts |
| OpenAPI Preview | `src/editor/preview/openapi_preview.py` | WebKit / WKWebView / GtkTextView | ❌ None |
| MD→ANSI Renderer | `src/ai/terminal_markdown_renderer.py` | `TerminalMarkdownRenderer` | N/A |

---

## Target Architecture

```
                  ┌──────────────────────┐
                  │  MarkdownCanvas      │  (new widget, extends ChatCanvas)
                  │  Gtk.DrawingArea     │
                  │  inside ScrolledWindow│
                  └──────┬───────────────┘
                         │ renders
          ┌──────────────┴──────────────┐
          ▼                             ▼
 ┌─────────────────┐         ┌──────────────────┐
 │ MarkdownRenderer│         │ OpenAPIRenderer   │
 │ (md → blocks)   │         │ (spec → blocks)   │
 └─────────────────┘         └──────────────────┘
```

All previews share the same native GTK rendering surface. Scroll sync is automatic — both editor `ScrolledWindow` and preview `ScrolledWindow` are GTK widgets with `vadjustment` signals.

---

## Implementation Plan

### Phase 1 — Extract MarkdownCanvas from ChatCanvas

**Goal:** Create a reusable rendering widget that accepts structured content blocks.

**Files to create:**
- `src/editor/preview/markdown_canvas.py`

**Steps:**
1. Define a `ContentBlock` data model (heading, paragraph, code, table, list, blockquote, horizontal rule, image placeholder).
2. Subclass or wrap `ChatCanvas` into `MarkdownCanvas` that accepts `list[ContentBlock]` instead of raw ANSI bytes.
3. Each block type gets its own Pango layout logic:
   - **Headings** — Sized Pango fonts (H1=24px, H2=20px, H3=16px, etc.), bold weight.
   - **Paragraphs** — Default font, word-wrap via `Pango.Layout.set_wrap(Pango.WrapMode.WORD_CHAR)`.
   - **Code blocks** — Monospace font, background rect via `snapshot.append_color()`, Pygments syntax highlighting mapped to Pango attributes.
   - **Inline code** — Monospace span with subtle background.
   - **Tables** — Pango tab stops or manual column-width calculation with box-drawing borders.
   - **Lists** — Indented layouts with bullet/number prefix.
   - **Blockquotes** — Left border (vertical rect) + indented italic text.
   - **Images** — `GdkTexture` + `snapshot.append_texture()` (load async, show placeholder until ready).
   - **Links** — Underlined text with color, click handling via `GestureClick` controller + hit testing.
4. Implement `do_snapshot()` that iterates blocks and renders each with the appropriate layout.
5. Implement `set_theme(colors: dict)` to apply editor theme colors to all block types.

**Key design decisions:**
- Block list is the intermediate representation — renderers produce blocks, canvas consumes them.
- Reuse `ChatCanvas._measure_font()` and `_update_content_height()` for scroll geometry.
- Reuse `ChatCanvas` selection logic (anchor/cursor, `get_text_format()`).

### Phase 2 — Markdown → ContentBlock Renderer

**Goal:** Convert markdown text into `list[ContentBlock]` for MarkdownCanvas.

**Files to create:**
- `src/editor/preview/markdown_block_renderer.py`

**Steps:**
1. Parse markdown using `cmarkgfm` (already a dependency) to get an AST.
2. Walk the AST and emit `ContentBlock` instances with line-number metadata (`source_line` attribute).
3. Preserve source line mapping for scroll sync: each block knows which editor line(s) it came from.
4. Code blocks: run through Pygments for syntax-highlighted Pango attributes.
5. Tables: parse into row/column structure for the canvas table layout.

**Why cmarkgfm AST instead of TerminalMarkdownRenderer:**
- `TerminalMarkdownRenderer` is line-oriented and emits ANSI strings — not structured enough for Pango layout.
- `cmarkgfm` provides a proper AST with source positions, which is essential for scroll sync.
- We keep `TerminalMarkdownRenderer` for the AI chat terminal (VTE) — it serves a different purpose.

### Phase 3 — Integrate into MarkdownPreview

**Goal:** Replace WebKit backend with MarkdownCanvas.

**Files to modify:**
- `src/editor/preview/markdown_preview.py`

**Steps:**
1. Add a `"canvas"` backend option alongside existing `"webkit_gtk"`, `"macos_webkit"`, `"textview"`.
2. When `"canvas"` is selected, create `MarkdownCanvas` inside the existing `ScrolledWindow`.
3. On `render(content)`: parse markdown → blocks → feed to canvas.
4. Implement **line-level scroll sync**:
   - Editor scrolls → find topmost visible editor line → find matching `ContentBlock` by `source_line` → scroll canvas to that block's Y offset.
   - Canvas scrolls → find topmost visible block → emit `source_line` → editor scrolls to that line.
   - No fractions, no JS, no echo guards — just Y coordinates in the same GTK coordinate space.
5. Initially ship `"canvas"` as opt-in (setting in `settings.json`), keep WebKit as default.
6. Once stable, make `"canvas"` the default, deprecate WebKit backend.

### Phase 4 — OpenAPI → ContentBlock Renderer

**Goal:** Give OpenAPI preview the same native rendering and scroll sync.

**Files to create:**
- `src/editor/preview/openapi_block_renderer.py`

**Files to modify:**
- `src/editor/preview/openapi_preview.py`

**Steps:**
1. Reuse existing `_parse_spec()` and `_resolve_refs()` logic from `openapi_preview.py`.
2. Convert the parsed spec dict into `list[ContentBlock]`:
   - API title/version → heading blocks
   - Endpoints → heading + table blocks (method, path, description)
   - Request/response bodies → code blocks (JSON schema)
   - Schemas → table blocks with property names, types, descriptions
3. Feed blocks to `MarkdownCanvas`.
4. Scroll sync works identically to Phase 3.

### Phase 5 — Polish and Cleanup

**Steps:**
1. **Image support** — Async load images from markdown `![alt](url)`, render via `GdkTexture`.
2. **Link click handling** — Open URLs in browser, navigate to local files.
3. **Zoom** — Scale Pango font descriptions (already have `zoom_in/out/reset` API).
4. **Copy to clipboard** — Reuse `ChatCanvas.copy_clipboard_format()`.
5. **Performance** — Only re-render changed blocks on incremental edits (diff the block list).
6. **Remove WebKit dependency** — Once canvas backend is proven stable, remove WebKit/WKWebView code paths.
7. **Update AI chat** — Consider migrating AI chat from raw ANSI to `MarkdownCanvas` blocks for richer formatting.

---

## Scroll Sync — Why This Solves It

**Current (WebKit):**
```
Editor (GTK)  ──fraction──▶  JS bridge  ──scrollTo──▶  WebKit (separate process)
                  ▲                                          │
                  └──────────── JS callback ─────────────────┘
                  150ms guard, fraction-based, drifts
```

**Proposed (Canvas):**
```
Editor (GTK ScrolledWindow)  ──vadjustment──▶  line mapping  ──vadjustment──▶  Canvas (GTK ScrolledWindow)
                                                    │
                                              source_line ↔ block Y offset
                                              same coordinate system, zero latency
```

Both widgets are GTK `ScrolledWindow` children. Scroll positions are pixel coordinates in the same window. No cross-process bridge, no JS, no fractions, no guards.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **Tables are hard** in Pango | Start with simple fixed-width columns; iterate. Tables in WebKit are already limited (no horizontal scroll). |
| **Images** require async loading | Show a placeholder rect with alt text while loading; non-blocking. |
| **Complex HTML** in markdown (embedded `<div>`, `<iframe>`) | Out of scope — these are rare in code docs. Fall back to text rendering. |
| **Performance** with very large documents | Viewport culling — only render blocks visible in the scroll region (ChatCanvas already clips to viewport). |
| **Regression risk** | Ship as opt-in `"canvas"` backend first; keep WebKit as fallback until stable. |

---

## Success Criteria

- [ ] Markdown preview scrolls in perfect sync with editor — no drift, no delay
- [ ] OpenAPI preview scrolls in sync with editor
- [ ] Theme changes apply instantly to preview (no CSS regeneration)
- [ ] Preview loads faster than WebKit (no process spin-up)
- [ ] All markdown elements render correctly: headings, bold/italic, code blocks, tables, lists, blockquotes, links
- [ ] OpenAPI endpoints, schemas, and examples render clearly
- [ ] Copy-to-clipboard works from preview
- [ ] Zoom in/out works
- [ ] No WebKit/WKWebView dependency required for previews
