# Widget Inspector

**Created_at:** 2026-03-17  
**Updated_at:** 2026-03-17  
**Status:** Active  
**Goal:** Document the browser DevTools-like widget inspector and AI chat block inspection feature  
**Scope:** `src/debug/widget_inspector.py`, `src/debug/inspect_popup.py`, `src/ai/chat_canvas.py`, `src/ai/ai_chat_terminal.py`  

---

## Overview

Zen IDE includes a **Widget Inspector** — a browser DevTools-like mode that lets you point-and-click on any UI element to see its full introspection details. It also supports **AI Chat content block inspection**, allowing you to click on chat messages to identify block types (user question, thinking, assistant response) and their colors.

## Activation

| Shortcut | Action |
|----------|--------|
| `Cmd+Shift+I` | Toggle inspect mode on/off |
| Also available from the **Help → Widget Inspector** menu item |

When active, the status bar shows an indicator and a colored outline follows the cursor over widgets.

## Basic Widget Inspection

Hovering highlights widgets with an accent-colored outline. Clicking opens the **Inspector popup** with:

| Section | Details |
|---------|---------|
| **Identity** | Widget type, CSS element name, widget name, label text, tooltip |
| **CSS Classes** | All CSS classes applied to the widget |
| **Geometry** | Position (x, y), allocation (w × h), rendered size |
| **Layout** | Horizontal/vertical alignment, expand flags, margins |
| **State** | Visible, sensitive, focusable, has focus, opacity |
| **Theme Colors** | Matched theme property names and color swatches (based on CSS classes) |
| **Widget Hierarchy** | Full parent chain from the clicked widget to the root window |

## AI Chat Block Inspection

When clicking on the **AI chat area** (`ChatCanvas`), the inspector adds a **Chat Block** section with:

| Field | Description |
|-------|-------------|
| **Block Type** | 💬 `user` — human prompt, 🧠 `thinking` — AI reasoning, 🤖 `assistant` — AI response |
| **Lines** | Line range of the block (e.g. `12–45 (34 lines)`) |
| **Cursor Line** | The exact line number at the click position |
| **Foreground** | Dominant foreground color at the clicked line (hex swatch) |
| **Background** | Background color at the clicked line (hex swatch) |
| **Preview** | First ~120 characters of the block's text content |

### How Block Tracking Works

The `ChatCanvas` maintains a `_block_tags` list that records where each content block begins:

1. **`AIChatTerminalView`** calls `canvas.begin_block(type)` at key moments:
   - `"user"` — when rendering the user's prompt
   - `"thinking"` — when AI thinking/reasoning text starts streaming
   - `"assistant"` — when the first AI response content arrives

2. **`ChatCanvas.get_block_at_line(line)`** looks up which block contains a given line number by finding the nearest preceding block tag.

3. **`ChatCanvas.get_line_colors(line)`** inspects the `AnsiBuffer` spans at a given line to extract the dominant foreground and background hex colors.

4. Block markers are also placed during **message restoration** (when reloading a conversation), so historical messages are fully inspectable.

## Architecture

```
┌─────────────────────┐
│   WidgetInspector    │  Attaches motion+click controllers to main window
│  (widget_inspector)  │  Captures hover highlights & click events
└────────┬────────────┘
         │ click at (x, y)
         ▼
┌─────────────────────┐
│ _collect_widget_info │  Gathers GTK introspection data
│ _guess_theme_colors  │  Maps CSS classes → theme properties
│ _enrich_with_chat_   │  Detects ChatCanvas, resolves block + colors
│   block_info         │
└────────┬────────────┘
         │ info dict
         ▼
┌─────────────────────┐
│   InspectPopup       │  NvimPopup subclass rendering all sections
│  (inspect_popup)     │  Color swatches via CSS (no Cairo)
└─────────────────────┘
```

### Key Files

| File | Responsibility |
|------|---------------|
| `src/debug/widget_inspector.py` | Inspect mode lifecycle, hover/click handlers, widget data collection |
| `src/debug/inspect_popup.py` | NvimPopup subclass that renders the inspector UI |
| `src/ai/chat_canvas.py` | Block tag tracking (`begin_block`, `get_block_at_line`, `get_line_colors`) |
| `src/ai/ai_chat_terminal.py` | Places block markers during streaming and message restoration |

## Keyboard Controls

Within the inspector popup:

| Key | Action |
|-----|--------|
| `Esc` | Close popup |
| `q` | Close popup |

## Design Decisions

- **Read-only labels** — All popup labels have `set_selectable(False)` to prevent GTK from auto-selecting text on popup open, which would obscure content.
- **No Cairo** — Color swatches use CSS `background-color` on a `Gtk.Box`, following the GtkSnapshot rendering standard.
- **NvimPopup inheritance** — The popup inherits from `NvimPopup` for consistent look, keyboard handling, and auto-close on focus loss.
- **Coordinate translation** — Window click coordinates are converted to canvas-local coordinates via `compute_point()` before resolving the buffer line.
