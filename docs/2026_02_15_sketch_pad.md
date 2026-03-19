# Sketch Pad

**Created_at:** 2026-02-15  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Document the ASCII diagram editor with shape tools, grid, selection, and export  
**Scope:** `src/sketch_pad/`, `.zen_sketch` files  

---

ASCII diagram editor for drawing shapes, arrows, and text on an infinite character grid using Unicode box-drawing characters. Inspired by [MonoSketch](https://github.com/tuanchauict/MonoSketch).

## Overview

Sketch Pad is an ASCII art diagram editor that opens as a tab in the editor notebook. It uses a **shape-based model** — each shape is an independent object with its own properties (position, style, text). The canvas is always derived by compositing all shapes in z-order.

## Toggle

- **Keyboard shortcut:** `Cmd+Shift+D` (macOS) / `Ctrl+Shift+D` (Linux)
- **Menu:** View → Toggle Sketch Pad
- **Open `.zen_sketch` file:** Double-click in tree view or open from file dialog

## Display Behavior

Sketch Pad opens as a **tab** in the editor notebook (alongside file tabs):

| Scenario | Layout |
|----------|--------|
| Toggle on | Opens as a new tab in the editor notebook |
| Already open | Switches to existing sketch tab |
| Close | Tab removed from notebook |
| Open `.zen_sketch` file | Loads content into sketch and opens tab |
| Session restore | Last open `.zen_sketch` file restored on startup |

The tab shows the sketch filename (or "Sketch Pad") with a close button. Minimum width: 200px.

## Drawing Tools

The toolbar provides 8 drawing tools:

| Tool | Icon | Key | Description |
|------|------|-----|-------------|
| **Select** | 󰔵 | `V` | Select, move, and resize shapes |
| **Pan** | 󰊓 | `H` | Pan the canvas by dragging |
| **Rectangle** | 󰃭 | `B` or `R` | Draw rectangles with Unicode box-drawing borders |
| **Arrow** | 󰁔 | `A` or `L` | Draw L-shaped orthogonal arrows with optional connections |
| **Actor** | 󰀄 | `P` | Place a stick figure actor (single-click places, then reverts to Select) |
| **Topic** | 󰦨 | `T` | Draw topic box with vertical dividers |
| **Database** | 󰆼 | `D` | Place a cylinder database symbol (single-click places, then reverts to Select) |
| **Cloud** | 󰅟 | `C` | Draw a cloud shape with rounded parentheses style |

### Additional toolbar controls

| Control | Key | Description |
|---------|-----|-------------|
| Line style cycle | — | Cycle arrow style: Solid → Dashed → Dotted |
| Zoom Out | `Cmd+-` | Decrease zoom (min 30%) |
| Reset View | — | Reset zoom to 100% and pan to origin |
| Zoom In | `Cmd+=` | Increase zoom (max 300%) |
| Delete | `Del` | Delete selected shapes |
| Font size | — | Spinbox (6–72pt) for selected shape text |
| Settings | — | Open global diagram settings popup |
| Export | — | Export as `.zen_sketch`, PNG, or JPEG |
| Import | — | Import `.zen_sketch` file |
| Clear | — | Clear entire board |
| Grid toggle | `G` | Show/hide the alignment grid overlay |
| Dark mode | `M` | Toggle dark/light mode |

## Shape Model (Z-Layer Architecture)

Shapes are **independent objects** stored in a `Board` container with z-ordering:

- **Shapes never erase each other.** Moving, resizing, or deleting one shape cannot corrupt another.
- **Overlapping is composited.** Shapes with higher z-order overwrite lower ones at overlapping positions.
- **Canvas is always derived.** The `Board.render()` method produces a `dict[(col, row) → char]` grid by rendering all shapes in z-order.

### Shape Types

**RectangleShape** — Rectangle with Unicode box-drawing border (`┌┐└┘─│`), optional fill (spaces), and centered text content. Supports custom font size.

**ArrowShape** — L-shaped (orthogonal) arrow between two points with arrow endpoints. Supports 3 line styles (solid, dashed, dotted), optional text label at midpoint, and magnetic connections to other shapes.

**ActorShape** — Fixed 5×4 stick figure person for use-case and sequence diagrams. Double-click to add a text label below.

**TopicShape** — Rectangle with 2 vertical dividers for structured content. Supports custom font size.

**DatabaseShape** — Cylinder shape (`╭╮├┤╰╯`) representing a database. Supports custom font size.

**CloudShape** — Cloud shape with rounded parentheses style. Supports custom font size.

## Border Style

All shapes use a single Unicode box-drawing border character set:

| Corners | H/V | Example |
|---------|-----|---------|
| `┌ ┐ └ ┘` | `─ │` | `┌──┐` |

## Arrow Line Styles

Arrows support 3 line styles, cycled via the toolbar button:

| Style | H char | V char |
|-------|--------|--------|
| **Solid** (default) | `─` | `│` |
| **Dashed** | `-` (alternating spaces) | `:` (alternating spaces) |
| **Dotted** | `·` (alternating spaces) | `·` (alternating spaces) |

Arrow endpoints are automatically oriented:

| Direction | Character |
|-----------|-----------|
| Right | `►` |
| Left | `◄` |
| Up | `▲` |
| Down | `▼` |

Arrows are L-shaped (orthogonal): horizontal first, then vertical at the endpoint column. Corner characters (`┌┐└┘`) are used at the bend.

## Connection Points

When an arrow endpoint is near a shape (within 3 cells snap distance), it **magnetically snaps** to the shape edge creating a connection.

- **Diamond (◆)** — indicates a connected endpoint (vs. unconnected)
- Connected arrows automatically adjust endpoints when the connected shape is moved

### Automatic Alignment

When shapes are moved or resized, connected arrows automatically re-align using the optimal edge and position via `_best_edges_between()`. This keeps diagrams tidy without manual adjustment.

### Manual Connection Override (Pinning)

To override automatic alignment:

1. **Select** the arrow (click with Select tool)
2. **Drag an endpoint handle** to reposition it on the target shape's edge
3. The connection is now **pinned** — it stays at the chosen edge and position even when shapes move

Pinned connections:
- Are immune to automatic edge re-optimization
- Coordinates still track the connected shape when it moves (the arrow follows the shape, keeping the same relative edge position)
- Persist across save/load cycles

## Drawing Mechanics

### Canvas

- **Infinite canvas** — shapes can be placed at any grid position
- Character rendering via **Pango** with monospace font (grid text) or custom font family (font-sized text)
- Grid overlay (toggleable) for alignment
- Alignment guides shown while dragging shapes (vertical/horizontal snap lines)
- Pan via: right/middle-click drag, Pan tool (`H`), or scroll wheel
- Zoom via: toolbar buttons, `Cmd+=`/`Cmd+-`, `Cmd+scroll`, or trackpad pinch gesture
- Pan constrained via `_clamp_pan()` to prevent panning beyond diagram + margin

### Shape Drawing

**Rectangle/Topic/Cloud:** Click and drag to define bounds. Preview shown while dragging. Minimum 2×2 cells.

**Arrow:** Click start point and drag to endpoint. L-shaped routing is automatic. Endpoints snap to nearby shapes.

**Actor/Database:** Single-click places the shape at cursor position. Tool automatically reverts to Select.

## Selection & Editing

### Selection

- **Click** on a shape (Select tool) → selects the topmost shape at that position
- **Click** on empty space → deselects
- **Marquee selection** → drag on empty space to select multiple shapes
- **Cmd+A** → select all shapes
- Selection shown with highlighted bounding box and resize handles

### Shape Text Editing

- **Double-click** on a shape → enters text editing mode
- Text in shapes is centered inside the interior (excluding border)
- Text on arrows is centered horizontally at the arrow's midpoint
- `Enter` creates a new line
- `Backspace` deletes character
- `Shift+arrows` for text selection within editor
- `Escape` exits text editing mode

### Custom Text Font Size

- **Select** a shape with text
- Use the **Font size spinbox** (6–72pt) in the toolbar to set a specific font size
- Shapes with custom font sizes render text as a centered Pango overlay (not ASCII grid characters)
- Font size is saved with the shape and persists across sessions
- Global settings popup can set font size for all shapes at once

### Move

- **Click and drag** a selected shape to move it
- **Arrow keys** → move selected shapes by 1 cell
- Alignment guides appear during drag for snapping

### Resize

8 resize handles (4 corners + 4 midpoints) appear on selected non-arrow shapes. Drag to resize.

### Delete

- `Delete` or `Backspace` with selection → removes selected shapes from the board

### Clipboard

- **Cmd+C** → copy selected shapes (JSON to internal clipboard, ASCII art to system clipboard)
- **Cmd+X** → cut (copy + delete)
- **Cmd+V** → paste from internal clipboard (structured) or system clipboard (ASCII fallback)
- Connection IDs are remapped on paste to preserve structure

## Undo/Redo

- **Cmd+Z** / **Cmd+Shift+Z**
- History stored as JSON board snapshots
- Snapshots recorded after each operation (draw, move, resize, delete, text edit)

## File Persistence

Sketch Pad uses `.zen_sketch` files for persistence:

- **Save (Cmd+S)** when sketch pad is focused → saves to the associated `.zen_sketch` file
- **Export** → save as `.zen_sketch`, PNG, or JPEG via file dialog
- **Import** → load a `.zen_sketch` file
- **Session restore** → last open `.zen_sketch` file is tracked and restored on startup
- **Auto-save on close** → if a `.zen_sketch` file path is associated, content is saved on window close

## Dev Pad Integration

Sketch activities are logged to Dev Pad via `log_sketch_activity()`:

- On export (with file path and content)
- On import (with file path and content)
- On show (current content logged)
- On save (content logged)

## Serialization

Board state is serialized as JSON (version 3):
```json
{
  "version": 3,
  "format": "sketch_pad",
  "shapes": [
    {"type": "rectangle", "id": "a1b2c3d4", "left": 0, "top": 0, "width": 10, "height": 5, "z_order": 0, "text": "Hello", "font_size": null},
    {"type": "arrow", "id": "e5f6g7h8", "start_col": 10, "start_row": 2, "end_col": 15, "end_row": 2, "z_order": 1, "text": "", "font_size": null, "line_style": "solid", "start_connection": null, "end_connection": {"shape_id": "a1b2c3d4", "edge": "right", "ratio": 0.5, "pinned": false}},
    {"type": "actor", "id": "i9j0k1l2", "left": 20, "top": 0, "z_order": 2, "text": "User"},
    {"type": "topic", "id": "m3n4o5p6", "left": 30, "top": 0, "width": 12, "height": 6, "z_order": 3, "text": "Topic", "font_size": null},
    {"type": "database", "id": "q7r8s9t0", "left": 45, "top": 0, "width": 10, "height": 5, "z_order": 4, "text": "DB", "font_size": null},
    {"type": "cloud", "id": "u1v2w3x4", "left": 58, "top": 0, "width": 10, "height": 5, "z_order": 5, "text": "API", "font_size": null}
  ]
}
```

Each shape has a unique 8-character hex ID generated on creation.

## Global Settings Popup

The **Settings** toolbar button opens a popup with bulk configuration:

- **Dark mode** toggle
- **Grid** toggle
- **Font family** selector (dropdown with system fonts)
- **Bulk font size** — applies to all shapes that have `font_size` set
- **Bulk shape size** — sets width/height (in cells) for Rectangle, Topic, Database, and Cloud shapes

## Theme & Font Support

- Dark mode toggleable via `M` key or Settings popup
- Theme colors from `themes.get_theme()`: `fg_color`, `panel_bg`, `accent_color`
- Grid text always uses `Monospace` font family
- Custom `font_size` text uses user-selectable font family (via Settings popup)
- Adapts to theme changes via `subscribe_theme_change()`

## Architecture

| File | Class | Description |
|------|-------|-------------|
| `src/sketch_pad/sketch_model.py` | `Board` | Shape container with z-ordering, rendering, serialization |
| `src/sketch_pad/sketch_model.py` | `RectangleShape` | Rectangle with border/text |
| `src/sketch_pad/sketch_model.py` | `ArrowShape` | L-shaped arrow with connections |
| `src/sketch_pad/sketch_model.py` | `ActorShape` | Stick figure person |
| `src/sketch_pad/sketch_model.py` | `TopicShape` | Topic box with dividers |
| `src/sketch_pad/sketch_model.py` | `DatabaseShape` | Cylinder database symbol |
| `src/sketch_pad/sketch_model.py` | `CloudShape` | Cloud shape |
| `src/sketch_pad/sketch_model.py` | `Connection` | Magnetic snap connection data |
| `src/sketch_pad/sketch_canvas.py` | `SketchCanvas` | GTK4 DrawingArea — rendering, mouse/keyboard, tools |
| `src/sketch_pad/sketch_pad.py` | `SketchPad` | Main widget — toolbar, canvas, status bar |
| `src/sketch_pad/global_settings_popup.py` | `GlobalDiagramSettingsPopup` | Bulk settings popup |
| `src/zen_ide.py` | `ZenIDEWindow` | Integration — tab management, toggle, file I/O |

## Public API

```python
class SketchPad(Gtk.Box):
    def __init__(self): ...
    def get_content(self) -> str: ...       # Board as JSON string
    def load_content(self, text: str): ...  # Load JSON content
    def is_empty(self) -> bool: ...         # True if board has no shapes
    def show_panel(self): ...               # Show + focus
    def hide_panel(self): ...               # Hide
    def undo(self): ...                     # Undo last action
    def redo(self): ...                     # Redo last undone action
    def destroy(self): ...                  # Clean up subscriptions
    ._drawing_area                          # SketchCanvas for focus tracking
    ._zoom(delta)                           # Zoom in/out
```

## Keyboard Shortcuts Summary

| Action | Shortcut |
|--------|----------|
| Toggle Sketch Pad | `Cmd+Shift+D` |
| Undo | `Cmd+Z` |
| Redo | `Cmd+Shift+Z` |
| Copy selection | `Cmd+C` |
| Cut selection | `Cmd+X` |
| Paste | `Cmd+V` |
| Select all | `Cmd+A` |
| Zoom In | `Cmd+=` |
| Zoom Out | `Cmd+-` |
| Move selection | Arrow keys |
| Delete selection | `Delete` / `Backspace` |
| Exit text/selection | `Escape` |
| Select tool | `V` |
| Pan tool | `H` |
| Rectangle tool | `B` or `R` |
| Arrow tool | `A` or `L` |
| Actor tool | `P` |
| Topic tool | `T` |
| Database tool | `D` |
| Cloud tool | `C` |
| Toggle grid | `G` |
| Toggle dark mode | `M` |
