# Sketch Pad — ASCII Diagrams

The Sketch Pad is an ASCII diagram editor for creating architecture diagrams, flowcharts, and system designs directly inside Zen IDE. It saves files in `.zen_sketch` format.

## Opening Sketch Pad

| Action | How |
|---|---|
| Toggle Sketch Pad | `Cmd+Shift+D` |
| Open a sketch file | Open any `.zen_sketch` file from the tree view |

## Drawing Tools

Select a tool by pressing its keyboard shortcut:

| Key | Tool | Description |
|---|---|---|
| `V` | **Select** | Select, move, and resize shapes |
| `H` | **Pan** | Drag the canvas to scroll |
| `B` or `R` | **Rectangle** | Draw boxes with Unicode borders |
| `A` or `L` | **Arrow** | Draw L-shaped orthogonal arrows |
| `P` | **Actor** | Place a stick figure |
| `T` | **Topic** | Draw a box with two vertical dividers |
| `D` | **Database** | Draw a cylinder symbol |
| `C` | **Cloud** | Draw a rounded cloud shape |

## Shape Details

### Rectangle
```
┌───────────┐
│   Label   │
└───────────┘
```
Draw by clicking and dragging. Type text to add a label.

### Arrow
```
──────┐
      │
      ▼
```
L-shaped orthogonal arrows with arrowheads. Three line styles available. Arrows snap magnetically to shapes (shown with ◆ indicator).

### Actor (Stick Figure)
```
 O
/|\
/ \
```
Click to place. Represents a person/user in system diagrams.

### Topic
```
┌───┬───┬───┐
│   │   │   │
└───┴───┴───┘
```
A box with two vertical dividers for multi-column layouts.

### Database
```
╭───╮
│   │
├───┤
│   │
╰───╯
```
Cylinder shape representing a database or data store.

### Cloud
```
(         )
(  Cloud  )
(         )
```
Rounded shape for cloud services or external systems.

## Editing

### Selection & Movement
| Shortcut | Action |
|---|---|
| `V` then click | Select a shape |
| Click + drag | Move selected shape |
| Drag handles | Resize shape |
| Arrow keys | Move selection by 1 cell |
| `Del` / `Backspace` | Delete selected shape |

### Clipboard
| Shortcut | Action |
|---|---|
| `Cmd+C` | Copy selection |
| `Cmd+X` | Cut selection |
| `Cmd+V` | Paste (as structured JSON or ASCII fallback) |
| `Cmd+A` | Select all shapes |

### History
| Shortcut | Action |
|---|---|
| `Cmd+Z` | Undo |
| `Cmd+Shift+Z` | Redo |

## Canvas Controls

| Shortcut | Action |
|---|---|
| `G` | Toggle grid overlay |
| `M` | Toggle dark mode |
| `Cmd++` | Zoom in (max 300%) |
| `Cmd+-` | Zoom out (min 30%) |
| `H` then drag | Pan canvas |

## Magnetic Connections

Arrows automatically snap to shape edges when drawn near them. A ◆ diamond indicator shows the connection point. When you move the shape, connected arrows follow.

## Text Editing

Double-click a shape to enter text editing mode. Each shape supports a text label:
- Font size adjustable per shape (6–72pt)
- Press `Escape` to exit text editing

## File Format

Sketch files use the `.zen_sketch` extension and contain JSON:

```json
{
  "version": 1,
  "format": "zen_sketch",
  "shapes": [
    {
      "type": "rectangle",
      "x": 10, "y": 5,
      "width": 20, "height": 8,
      "text": "My Service"
    }
  ]
}
```

## Export

Sketch Pad supports exporting to:
- **`.zen_sketch`** — Native JSON format (default)
- **PNG** — Raster image
- **JPEG** — Compressed raster image

## Tips

- Use **rectangles** for services and components
- Use **arrows** to show data flow and dependencies
- Use **actors** for users and external systems
- Use **databases** for storage and persistence
- Use **clouds** for external services and APIs
- The grid (`G`) helps align shapes to a consistent grid
