# Code Folding

**Created_at:** 2026-03-26
**Updated_at:** 2026-03-26
**Status:** Draft
**Goal:** Implement code folding (collapse/expand) for the editor
**Scope:** `src/editor/fold_manager.py` (new), `src/editor/editor_view.py`, `src/editor/tree_sitter_buffer.py`

---

## Overview

Code folding allows users to collapse multi-line blocks (functions, classes, loops, objects, etc.) down to a single summary line. The implementation leverages the existing tree-sitter infrastructure for structure detection, GTK4's `invisible` text tags for hiding lines, and the snapshot rendering pipeline for gutter fold indicators.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    FoldManager                       │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ FoldRegion   │  │ Gutter       │  │ Invisible  │  │
│  │ Detection    │  │ Indicator    │  │ Tag        │  │
│  │ (tree-sitter)│  │ Renderer     │  │ Manager    │  │
│  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  │
│         │                │                 │         │
│         ▼                ▼                 ▼         │
│  TreeSitterBuffer   do_snapshot()     GtkTextTag     │
│  Cache (existing)   pipeline          "fold-hidden"  │
└──────────────────────────────────────────────────────┘
```

### Components

| Component | Responsibility |
|-----------|---------------|
| **FoldManager** | Central coordinator: owns fold state, computes regions, toggles folds |
| **Fold region detection** | Uses tree-sitter AST to identify foldable node spans |
| **Gutter indicator renderer** | Draws fold chevrons (▶/▼) in the gutter via `snapshot.append_color` |
| **Invisible tag manager** | Applies/removes `invisible` text tags on the buffer to hide/show lines |

---

## Fold Region Detection

### Tree-sitter queries

Foldable regions are identified by querying tree-sitter AST nodes that span 2+ lines. Each supported language defines a set of foldable node types:

```python
FOLD_NODE_TYPES = {
    "python": {
        "function_definition",
        "class_definition",
        "if_statement",
        "elif_clause",
        "else_clause",
        "for_statement",
        "while_statement",
        "with_statement",
        "try_statement",
        "except_clause",
        "finally_clause",
        "dictionary",
        "list",
        "decorated_definition",
    },
    "javascript": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "if_statement",
        "else_clause",
        "for_statement",
        "for_in_statement",
        "while_statement",
        "switch_statement",
        "try_statement",
        "catch_clause",
        "object",
        "array",
        "arrow_function",
    },
    "typescript": {
        # Same as javascript, plus:
        "interface_declaration",
        "type_alias_declaration",
        "enum_declaration",
    },
}
```

### Detection algorithm

Rather than running S-expression queries (which would need one pattern per node type), walk the tree-sitter AST recursively and collect any node whose type is in the foldable set and whose `end_point[0] - start_point[0] >= 1` (spans at least 2 lines):

```python
def _collect_fold_regions(self, node, lang_id, regions):
    """Recursively walk the AST and collect foldable regions."""
    foldable = FOLD_NODE_TYPES.get(lang_id, set())
    if node.type in foldable:
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        if end_line > start_line:
            regions[start_line] = end_line
    for child in node.children:
        self._collect_fold_regions(child, lang_id, regions)
```

This produces a dict `{start_line: end_line}` where each entry represents one foldable region. Nested folds are naturally supported — a class body contains function folds inside it.

### Recomputation strategy

- Recompute fold regions **on buffer change**, debounced at 500ms (same pattern as `GutterDiffRenderer`)
- Reuse the `TreeSitterBufferCache` that already exists on each `EditorTab` (`tab._ts_cache`)
- Only recompute if the tree actually changed (check `_ts_cache._dirty` flag)

### Indent-based fallback

For languages without tree-sitter support, use an indent-based heuristic: a fold starts when indentation increases and ends when it returns to the original level. This reuses logic from `indent_guide_levels.py`.

---

## Line Hiding Mechanism

### GTK4 invisible text tags

GTK4's `Gtk.TextTag` supports the `invisible` property, which hides tagged text from rendering. This is the recommended approach because:

1. GTK handles line number renumbering automatically
2. Scroll position and cursor navigation work correctly
3. No need to maintain a virtual-to-physical line mapping
4. The buffer content is unchanged — only the view is affected

### Implementation

```python
def _setup_fold_tags(self, buffer):
    """Create the invisible tag used to hide folded content."""
    self._fold_tag = buffer.create_tag("fold-hidden", invisible=True)

def _collapse(self, buffer, start_line, end_line):
    """Hide lines start_line+1 through end_line (inclusive)."""
    # The fold header line (start_line) remains visible
    start_iter = buffer.get_iter_at_line(start_line + 1)
    end_iter = buffer.get_iter_at_line(end_line)
    end_iter.forward_to_line_end()
    buffer.apply_tag(self._fold_tag, start_iter, end_iter)

def _expand(self, buffer, start_line, end_line):
    """Reveal previously hidden lines."""
    start_iter = buffer.get_iter_at_line(start_line + 1)
    end_iter = buffer.get_iter_at_line(end_line)
    end_iter.forward_to_line_end()
    buffer.remove_tag(self._fold_tag, start_iter, end_iter)
```

### Fold placeholder

When a region is collapsed, append a visual indicator on the fold header line. Two options:

**Option A — Overlay text via snapshot** (preferred):
Draw a dimmed `" ..."` string at the end of the fold header line using `PangoLayout` + `snapshot.append_layout`. This is purely visual and doesn't modify the buffer.

**Option B — Invisible placeholder tag**:
Insert ` ...` text with a special tag, and remove it on expand. Simpler but modifies the buffer (affects undo history, save, etc.).

Recommendation: **Option A** — keep the buffer clean.

---

## Gutter Fold Indicators

### Rendering

Follow the established pattern from `GutterDiffRenderer.draw(snapshot, vis_range)`:

```python
def draw_fold_indicators(self, snapshot, vis_range):
    """Draw fold chevrons in the gutter area."""
    if not self._fold_regions:
        return

    view = self._view
    buf = view.get_buffer()
    start_ln, end_ln = vis_range

    # Position fold indicators to the left of diff indicators
    text_x, _ = view.buffer_to_window_coords(
        Gtk.TextWindowType.WIDGET, 0, 0
    )
    indicator_x = max(text_x - FOLD_INDICATOR_OFFSET, 0)

    for line_num in range(start_ln, end_ln + 1):
        if line_num not in self._fold_regions:
            continue

        collapsed = self._collapsed.get(line_num, False)

        it = buf.get_iter_at_line(line_num)
        try:
            it = it[1]  # GTK4 tuple return
        except (TypeError, IndexError):
            pass

        y, lh = view.get_line_yrange(it)
        _, wy = view.buffer_to_window_coords(
            Gtk.TextWindowType.WIDGET, 0, y
        )

        # Draw chevron: ▶ (collapsed) or ▼ (expanded)
        self._draw_chevron(snapshot, indicator_x, wy, lh, collapsed)
```

### Chevron drawing

Draw the fold indicator as a small triangle using `Gsk.PathBuilder`:

- **Expanded (▼)**: downward-pointing triangle
- **Collapsed (▶)**: right-pointing triangle
- Color: use `theme.fg_dim` at 0.6 alpha (subtle, not distracting)
- Size: ~8x8 pixels, vertically centered in the line

### Visibility behavior

Two possible UX approaches:

1. **Always visible**: Show chevrons on all foldable lines (like VS Code)
2. **Hover-to-reveal**: Only show chevrons when the mouse hovers near the gutter (like Sublime Text)

Recommendation: Start with **always visible** for simplicity. Add hover-to-reveal as a follow-up if the gutter feels cluttered.

---

## Integration into Editor Pipeline

### EditorTab.__init__

```python
# In EditorTab.__init__, after tree-sitter buffer cache setup:
from .fold_manager import FoldManager

self._fold_manager = FoldManager(self.view, self._ts_cache)
self.view._fold_manager = self._fold_manager
```

### ZenSourceView._do_custom_snapshot

Add fold indicator rendering to the existing snapshot pipeline, after diff indicators:

```python
def _do_custom_snapshot(self, snapshot):
    if self._show_guides:
        self._draw_indent_guides_snapshot(snapshot)

    visible = self.get_visible_rect()
    vis_start, _ = self.get_line_at_y(visible.y)
    vis_end, _ = self.get_line_at_y(visible.y + visible.height)
    vis_range = (vis_start.get_line(), vis_end.get_line())

    if self._gutter_diff_renderer and self._gutter_diff_renderer._diff_lines:
        self._gutter_diff_renderer.draw(snapshot, vis_range)

    # NEW: Fold indicators in the gutter
    if self._fold_manager and self._fold_manager._fold_regions:
        self._fold_manager.draw_fold_indicators(snapshot, vis_range)

    # ... rest of pipeline (color preview, diagnostics, ghost text, cursor)
```

### Click handling

Add fold toggle to the existing click handler in `EditorTab._on_click_pressed`:

```python
def _on_click_pressed(self, gesture, n_press, x, y):
    # Check if click is in the fold gutter zone
    if x < fold_gutter_right_edge:
        bx, by = self.view.window_to_buffer_coords(
            Gtk.TextWindowType.WIDGET, x, y
        )
        line_iter, _ = self.view.get_line_at_y(by)
        line = line_iter.get_line()
        if self._fold_manager.toggle_fold(line):
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            return
    # ... existing click handling
```

### Keyboard shortcuts

| Action | Shortcut | Description |
|--------|----------|-------------|
| Toggle fold at cursor | `Ctrl+Shift+[` | Collapse/expand the fold containing the cursor |
| Collapse all | `Ctrl+K, Ctrl+0` | Collapse all foldable regions |
| Expand all | `Ctrl+K, Ctrl+J` | Expand all foldable regions |
| Fold level N | `Ctrl+K, Ctrl+{1-5}` | Collapse to indent level N |

---

## Fold State Management

### Data structures

```python
class FoldManager:
    def __init__(self, view, ts_cache):
        self._view = view
        self._ts_cache = ts_cache
        self._fold_regions = {}    # {start_line: end_line} — all foldable regions
        self._collapsed = {}       # {start_line: True} — currently collapsed regions
        self._fold_tag = None      # Gtk.TextTag with invisible=True
        self._update_timeout_id = None
```

### Fold persistence

Fold state should survive:
- **Theme changes**: Yes (tags are recreated, reapply collapsed state)
- **Buffer edits**: Yes (recompute regions, preserve collapsed state where possible)
- **File close/reopen**: No (start fresh — fold state is ephemeral)

When regions are recomputed after an edit, match old collapsed entries to new regions by proximity (same start line or within +/-2 lines).

---

## Edge Cases

### Cursor inside folded region
If the cursor is placed inside a folded region (e.g., via Find & Replace or Go to Line), **auto-expand** that fold before moving the cursor. Listen to `GtkTextBuffer::mark-set` for the insert mark.

### Nested folds
Collapsing an outer region hides inner fold indicators. Expanding the outer region should restore inner folds to their previous state.

### Buffer edits inside folds
If a collapsed region is edited programmatically (e.g., format-on-save, LSP code action), expand the affected fold first, apply the edit, then optionally re-collapse.

### Undo/redo
Since invisible tags are applied/removed as buffer operations, they participate in GTK's undo stack. This should work naturally, but needs testing to confirm that undo through a fold toggle restores visibility correctly.

### Line numbers
GTK4's `GtkSourceView.set_show_line_numbers(True)` should automatically skip invisible lines in the gutter. Verify this — if not, line numbers may need manual adjustment.

### Indent guides
Skip drawing indent guides for lines that are inside a collapsed fold. Check `_fold_manager._collapsed` in `_draw_indent_guides_snapshot` and skip lines in collapsed ranges.

---

## Interaction with Existing Features

| Feature | Impact | Action needed |
|---------|--------|---------------|
| **Git diff indicators** | Collapsed lines won't have visible diff bars | No action — GTK skips invisible lines |
| **Indent guides** | Should not draw inside collapsed regions | Skip collapsed line ranges |
| **Diagnostics** | Wavy underlines on hidden lines are invisible | Show fold-level diagnostic summary (future) |
| **Minimap** | Should reflect fold state | Update minimap to skip collapsed regions |
| **Search (Ctrl+F)** | Matches in folded regions must auto-expand | Hook into search navigation |
| **Go to line** | Target in fold must auto-expand | Hook into cursor movement |
| **Semantic highlight** | Works on buffer content, unaffected | No action |
| **Ghost text (AI)** | Should not appear inside collapsed regions | Check fold state before showing |

---

## File Structure

```
src/editor/
    fold_manager.py          # NEW — FoldManager class + fold region detection
    fold_queries.py          # NEW — FOLD_NODE_TYPES per language (optional, can inline)
    editor_view.py           # MODIFY — wire FoldManager into EditorTab + snapshot pipeline
    tree_sitter_buffer.py    # UNCHANGED — reused as-is
    gutter_diff_renderer.py  # UNCHANGED — rendering pattern reference
    indent_guide_levels.py   # UNCHANGED — fallback fold detection reference
```

---

## Implementation Order

1. **`FoldManager` skeleton** — fold state dict, `invisible` tag setup, collapse/expand methods
2. **Tree-sitter fold detection** — AST walk, region collection, debounced recomputation
3. **Gutter chevron rendering** — draw in `do_snapshot`, follow `GutterDiffRenderer` pattern
4. **Click-to-toggle** — gutter click handler to toggle folds
5. **Keyboard shortcuts** — Ctrl+Shift+[ toggle, Ctrl+K chords
6. **Placeholder text** — draw `" ..."` overlay on collapsed header lines
7. **Auto-expand on navigation** — cursor/search entering folded region expands it
8. **Indent-based fallback** — fold detection for non-tree-sitter languages
9. **Polish** — nested fold state, minimap integration, animation (optional)

---

## Open Questions

- **Animation**: Should fold/expand animate (smooth height transition) or be instant? GTK4 doesn't natively animate line visibility, so animation would require a custom approach (e.g., timed height interpolation over ~150ms).
- **Fold summary**: Should the collapsed placeholder show more than `...`? (e.g., `... 42 lines` or a preview of the first hidden line)
- **Persistence across sessions**: Worth saving fold state to `.zen_ide/fold_state.json`?
- **Gutter width**: Adding fold indicators increases effective gutter width. Should this be configurable or auto-detected?
