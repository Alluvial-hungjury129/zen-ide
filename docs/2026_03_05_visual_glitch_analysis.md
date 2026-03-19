# Visual Glitch Root Causes — Zen IDE

**Created_at:** 2026-03-05  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Root cause analysis of 30 visual issues including scrolling anomalies, flicker, and artifacts  
**Scope:** `src/editor/`, `src/ai/`, `src/themes/`, rendering pipeline

---

## 📜 SCROLLING ISSUES (7 issues)

### ~~🔴 S1 — AI chat scroll jitter~~ ✅ RESOLVED
~~**File:** `src/ai/ai_chat_view.py`~~ — `AIChatView` was deleted. `AIChatTerminalView` is the sole chat backend.

### 🔴 S2 — `go_to_line_smooth()` snap→rewind→animate triple position change
**File:** `src/editor/editor_view.py`
`scroll_to_iter()` immediately jumps to the target line, then a custom smooth-scroll animation starts from the *original* position, creating a visible snap-back-and-glide effect.
**Symptom:** Editor briefly shows target line, snaps back, then scrolls forward.
**Fix:** Suppress the initial `scroll_to_iter()` jump or use `scroll_to_mark()` with `use_align=False` to avoid the snap.

### 🟠 S3 — Scroll position lost on theme/font change
**File:** `src/themes/theme_manager.py`, `src/fonts/font_manager.py`
Changing theme or font resets the CSS, which triggers a re-layout. No code saves/restores the scroll position across the relayout.
**Symptom:** Editor jumps to top when changing theme or font size.
**Fix:** Save `vadjustment.value` before CSS change, restore in `GLib.idle_add()` after layout settles.

### 🟠 S4 — Tree view scroll position lost on refresh
**File:** `src/tree_view.py`
`_refresh_tree()` clears and rebuilds the entire `TreeStore`. Expanded state is saved but scroll position is not.
**Symptom:** Tree jumps to top after saving a file or any git change.
**Fix:** Save `vadjustment.value` before refresh, restore after repopulation.

### 🟠 S5 — Markdown preview scroll not synced with editor
**File:** `src/editor/markdown_preview.py`
Editor and preview have independent scroll adjustments. No proportional scroll syncing between them.
**Symptom:** Editor and preview show different parts of the document.
**Fix:** Connect `vadjustment.notify::value` on editor, proportionally set preview scroll.

### 🟡 S6 — Autocomplete popup causes editor scroll
**File:** `src/editor/autocomplete/autocomplete.py`
When the popup appears near the bottom edge, GTK may auto-scroll the parent to ensure the popup is visible, shifting the editor content.
**Symptom:** Editor text shifts when autocomplete appears near bottom of viewport.
**Fix:** Use `anchor_rect` positioning and clamp popup to viewport bounds without scrolling parent.

### 🟡 S7 — Multiple `scroll_to_mark()` calls in quick succession
**File:** `src/editor/editor_view.py`
`go_to_definition`, `find_next`, and `go_to_line` all call `scroll_to_mark()`/`scroll_to_iter()`. If triggered rapidly (e.g., holding F3 for find-next), scroll targets queue up and execute serially, causing stutter.
**Symptom:** Jumpy scrolling when rapidly navigating between search results.
**Fix:** Debounce scroll operations or use `scroll_to_mark()` with `GLib.idle_add()` to coalesce.

---

## ⚡ FLICKER / FLASH ISSUES (8 issues)

### 🔴 F1 — CSS provider accumulation causes style flashes
**File:** `src/themes/theme_manager.py`
A new `CssProvider` is added to the `Gtk.StyleContext` on every theme switch **without removing the old one**. Old CSS rules persist and can conflict, causing momentary style flashes as GTK resolves conflicting rules.
**Symptom:** Brief flash of wrong colors during theme switch. Styles may "leak" from previous themes.
**Fix:** Store reference to current provider, call `Gtk.StyleContext.remove_provider_for_display()` before adding new one.

### 🔴 F2 — Tab content visible before it's ready
**File:** `src/editor/editor_view.py`
When switching tabs, the new editor widget is shown (`widget.show()`) before the buffer content and syntax highlighting are fully loaded.
**Symptom:** Brief flash of empty/unstyled editor content when switching tabs.
**Fix:** Set content and highlighting *before* calling `show()`, or use `set_visible(False)` until ready then `set_visible(True)`.

### 🔴 F3 — Thread-unsafe widget updates from AI streaming
**File:** `src/ai/pty_cli_provider.py:232-253`
Background threads directly call methods that modify GTK widgets (text buffers, labels). GTK is not thread-safe — this causes:
- Random visual corruption
- Partial renders (half-drawn text)
- Widget state inconsistencies
**Symptom:** Garbled text, partial UI updates, random visual artifacts during AI streaming.
**Fix:** All widget updates must go through `GLib.idle_add()`.

### 🟠 F4 — Diff view flickers during git operations
**File:** `src/editor/diff_view.py`
Diff view clears both panes, runs `git diff` synchronously, then repopulates. During the sync git call, empty panes are visible.
**Symptom:** Diff view briefly shows empty panes when refreshing.
**Fix:** Compute diff in background, swap content atomically. Or hide diff view during refresh.

### 🟠 F5 — Notification toast causes layout reflow
**File:** `src/popups/notification_toast.py`
Toast appears as a `Gtk.Window` overlay. On some compositors/WMs, showing a new top-level window causes the desktop to briefly recomposite, leading to a flash.
**Symptom:** Screen flickers when notifications appear (especially on Wayland/tiling WMs).
**Fix:** Use an in-window overlay (`Gtk.Overlay`) instead of a separate `Gtk.Window`.

### 🟠 F6 — Font loading causes visible reflow
**File:** `src/fonts/font_manager.py`
When a custom font is loaded, all editors reflow text simultaneously. The reflow is visible because it happens synchronously in the main loop.
**Symptom:** All open editor tabs visibly re-layout when font changes.
**Fix:** Freeze editor drawing during font change (`queue_draw()` once after all buffers updated).

### 🟡 F7 — Search highlight repaint flicker
**File:** `src/editor/editor_view.py`
`find_and_highlight_all()` removes all existing search tags, then re-applies them one by one. The removal is visible before new highlights are applied.
**Symptom:** Search highlights briefly disappear then reappear when typing in search box.
**Fix:** Apply new highlights first, then remove old ones. Or batch in `begin_user_action()`/`end_user_action()`.

### 🟡 F8 — Cursor blink timer not stopped on editor hide
**File:** `src/editor/editor_view.py`
Custom cursor blink timer continues running when editor is not visible (e.g., terminal is focused). Each blink triggers a `queue_draw()`.
**Symptom:** Background editor redraws cause subtle flicker in overlapping areas.
**Fix:** Stop blink timer when editor loses focus or is hidden.

---

## 👻 ARTIFACTS / GHOST RENDERING (8 issues)

### 🔴 A1 — Stale ghost text (AI inline completion) not cleared
**File:** `src/ai/ai_inline_completion.py`
Ghost text overlay is rendered at a specific buffer position. When the buffer changes (user types, undo, etc.), the ghost text may remain at the old position or overlap with real text.
**Symptom:** Semi-transparent "ghost" text visible at wrong position after typing.
**Fix:** Clear ghost text on every buffer `changed` signal, re-request if needed.

### 🔴 A2 — Tree view shows deleted files until next refresh
**File:** `src/tree_view.py`
File deletion via terminal or external tool is not immediately reflected. `FileMonitor` may miss rapid deletions, or the debounce delay keeps stale entries visible.
**Symptom:** Deleted files appear in tree, clicking them shows error.
**Fix:** Verify file existence before opening. Reduce debounce delay for `DELETED` events.

### 🟠 A3 — Indent guides drawn over selection highlight
**File:** `src/editor/indent_guides.py`
Indent guide rendering happens in a draw callback that runs *after* the selection highlight. The thin lines are drawn over the selection background, creating visible lines through selected text.
**Symptom:** Vertical lines visible through text selection.
**Fix:** Check if region is selected in draw callback, skip guide rendering for selected lines. Or draw guides *before* selection layer.

### 🟠 A4 — Line number gutter not invalidated after fold/unfold
**File:** `src/editor/editor_view.py`
If code folding is implemented via hiding lines, the gutter line numbers are not recalculated, showing wrong numbers.
**Symptom:** Line numbers are wrong after folding/unfolding code.
**Fix:** Call `queue_draw()` on gutter after fold state changes.

### 🟠 A5 — Minimap/overview shows stale content
**File:** `src/editor/editor_view.py`
If a minimap or overview ruler is rendered, it may not update when the buffer changes, showing content that doesn't match the actual buffer.
**Symptom:** Minimap shows old version of code.
**Fix:** Connect minimap to buffer `changed` signal.

### 🟡 A6 — Old tab content briefly visible when tab is reused
**File:** `src/editor/editor_view.py`
When clicking a file in the tree that replaces a "preview" tab, the old buffer content is visible for one frame before the new content loads.
**Symptom:** Brief flash of previous file content when opening a new file in preview tab.
**Fix:** Clear buffer immediately before loading new content, or hide editor during transition.

### 🟡 A7 — Tooltip/hover info appears at wrong position after scroll
**File:** `src/editor/editor_view.py`
Hover tooltips calculate position based on buffer coordinates. After scrolling, the tooltip may appear at the pre-scroll position if the position isn't recalculated.
**Symptom:** Tooltip appears above/below the actual symbol after scrolling.
**Fix:** Recalculate tooltip position relative to current scroll offset, or dismiss on scroll.

### 🟡 A8 — Sketch pad artifacts after undo
**File:** `src/sketch_pad/sketch_pad.py`
Undo restores a previous canvas state but the visible canvas may not fully repaint, leaving artifacts from the undone operation.
**Symptom:** Ghost lines or boxes visible after undo in sketch pad.
**Fix:** Force full canvas `queue_draw()` after every undo/redo operation.

---

## 🔄 REFRESH / REDRAW ISSUES (7 issues)

### 🔴 R1 — `queue_draw()` called redundantly during batch operations
**File:** Multiple files
Many operations (e.g., applying highlights, updating git markers, changing indent) call `queue_draw()` for each individual change. GTK coalesces draws, but the overhead of queuing hundreds of draws per keystroke is measurable.
**Symptom:** UI feels sluggish during rapid editing.
**Fix:** Batch visual updates, call `queue_draw()` once at the end.

### 🔴 R2 — Full tree rebuild on every `FileMonitor` event
**File:** `src/tree_view.py`
Any file change (create, modify, delete) triggers a full tree clear + rebuild. For workspaces with thousands of files, this takes 100ms+ during which the tree is visually empty.
**Symptom:** Tree blinks empty during rapid file operations (e.g., `npm install`).
**Fix:** Implement incremental tree updates — only add/remove/update the affected node.

### 🟠 R3 — Status bar updates not throttled
**File:** `src/status_bar.py`
Every cursor movement triggers a status bar update (line, column, selection count, language). With keyboard repeat, this fires hundreds of updates per second.
**Symptom:** Status bar flickers during rapid cursor movement.
**Fix:** Throttle status bar updates to max 30fps (one update per ~33ms).

### 🟠 R4 — Git gutter markers rebuilt on every save
**File:** `src/editor/editor_view.py`
After saving, `git diff` is run and all gutter markers (added/modified/deleted lines) are recalculated and repainted.
**Symptom:** Brief flicker of gutter markers disappearing then reappearing after save.
**Fix:** Compare new markers with old, only update changed regions.

### 🟠 R5 — Preview pane re-renders entire document on each keystroke
**File:** `src/editor/markdown_preview.py`
Each buffer change triggers full markdown→HTML conversion and WebKit reload.
**Symptom:** Preview blinks/flashes on every keystroke.
**Fix:** Debounce preview updates (200-300ms). Use incremental DOM updates instead of full page reload.

### 🟡 R6 — Dev Pad activity list not virtualized
**File:** `src/editor/dev_pad.py`
All activity entries are rendered as real GTK widgets. After many activities, the list becomes slow to update.
**Symptom:** Dev pad becomes laggy after extended use.
**Fix:** Use `Gtk.ListView` with `Gtk.SignalListItemFactory` for virtualized rendering.

### 🟡 R7 — Window resize triggers cascading relayouts
**File:** `src/main/window_layout.py`
Paned widgets, editor, tree, terminal all receive allocation changes during resize. Each triggers its own `queue_draw()`.
**Symptom:** Choppy/laggy window resizing.
**Fix:** Use `Gtk.Widget.set_can_target(False)` during resize, re-enable after. Or freeze non-essential redraws during resize.

---

## Fix Status (Updated 2026-03-05)

### ✅ Fixed Issues

| Issue | Fix Description |
|-------|----------------|
| **F1** | CSS provider accumulation — `_apply_theme()` now removes old provider before adding new one |
| **S1** | AI chat scroll jitter — animation cancellation via `cancelled_ref` flag |
| **S2** | `go_to_line_smooth` — computes target position mathematically instead of snap→rewind→animate |
| **F3** | Thread-unsafe AI widget updates — `_on_output`, `_on_error`, `_on_complete` now wrapped in `GLib.idle_add()` |
| **R3** | Status bar throttled — `set_position()` now uses 33ms (30fps) throttle |
| **S3** | Scroll preserved on theme/font change — `vadjustment.value` saved/restored |
| **F4** | Diff view flicker — buffers no longer cleared before loading, keeping old content visible |
| **R4** | Git gutter — diff comparison only redraws if `_diff_lines` actually changed |
| **A2** | Tree deleted files — file existence verified before opening, triggers refresh if deleted |
| **A3** | Indent guides over selection — guides now skipped for selected lines |
| **F5** | Notification toast — CSS provider scoped to widget instead of display-level |
| **Editor CSS** | `EditorTab._apply_theme()` — old CSS provider removed before adding new one |

### ✅ Already Handled (no change needed)

| Issue | Reason |
|-------|--------|
| **F8** | Blink timer already stops on `_bc_focus_out` via focus controller |
| **R5** | Markdown preview already debounced at 300ms in `_on_md_buffer_changed` |
| **S4** | Tree refresh already saves/restores `vadjustment` scroll position |
| **F7** | Search uses `GtkSource.SearchContext` — no manual tag removal flicker |
| **F2** | `load_file()` sets content + language before tab added to notebook |
| **A8** | Sketch pad `undo()`/`redo()` already call `queue_draw()` |
| **R1** | GTK coalesces `queue_draw()` calls automatically; no loops found |
| **R2** | File watcher already distinguishes modified (targeted) vs created/deleted (1s debounce) |
| **S7** | `scroll_to_iter` is instant; rapid F3 shows correct behavior |

### N/A (not applicable to current codebase)

| Issue | Reason |
|-------|--------|
| **A1** | Ghost text/inline completion not implemented as described |
| **A4** | Code folding not implemented |
| **A5** | `GtkSource.Map` auto-syncs with buffer |
| **A6** | No preview tab (single-click preview) concept |
| **A7** | Hover underline recalculates position on each motion event |

### Deferred (large refactors)

| Issue | Reason |
|-------|--------|
| **S5** | Markdown scroll sync requires JS injection across 3 rendering backends |
| **S6** | Autocomplete already uses NvimPopup with anchor positioning |
| **F6** | Font reflow is inherent GTK relayout behavior |
| **R6** | Dev Pad virtualization requires full Gtk.ListView migration |
| **R7** | Window resize cascading is inherent GTK paned behavior |

## ~~Priority Matrix~~

_(Superseded by Fix Status above)_

| Priority | Issues | Key Actions |
|----------|--------|-------------|
| **Fix Now** (🔴) | S1, S2, F1, F2, F3, A1, A2, R1, R2 | Thread safety, CSS cleanup, ghost text clearing, tree incremental updates |
| **Fix Soon** (🟠) | S3-S5, F4-F6, A3-A5, R3-R5 | Scroll preservation, debouncing, diff atomicity |
| **Fix Eventually** (🟡) | S6-S7, F7-F8, A6-A8, R6-R7 | Virtualization, resize optimization, tooltip positioning |

## ~~Quick Wins (< 1 hour each)~~

1. **F1** — Remove old CSS provider before adding new → 3 lines changed
2. **A1** — Clear ghost text on buffer `changed` signal → 5 lines
3. **S1** — Cancel previous scroll animation → 10 lines
4. **R3** — Throttle status bar updates → 15 lines
5. **F7** — Swap highlight apply/remove order → 5 lines
6. **F8** — Stop blink timer on focus-out → 5 lines
