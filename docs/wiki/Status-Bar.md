# Status Bar

The status bar sits at the bottom of the Zen IDE window, showing contextual information about the current file, git state, and editor position.

## Layout

```
[Z] NORMAL │ ⎇ main │ ~/src/editor_view.py │ ··· │ 2E 1W │ UTF-8 │ Δ │  Python │ 42:7 │ 65%
 └─ mode ──┘  └ git ─┘  └───── path ────────┘      └diag.─┘ └enc.─┘ └mod┘ └─type──┘ └pos─┘ └%──┘
```

## Segments

### Left Side

| Segment | Content | Description |
|---|---|---|
| **Mode** | Zen icon + `NORMAL` | Current editor mode |
| **Inspect** | `Inspect` | Shown when widget inspector is active |
| **Git Branch** | `⎇ main` | Current git branch name (fetched asynchronously) |
| **File Path** | `~/src/editor_view.py` | Active file path (ellipsis for long paths) |

### Right Side

| Segment | Content | Description |
|---|---|---|
| **Diagnostics** | `2E 1W` | Error and warning counts (clickable — opens diagnostics popup) |
| **Encoding** | `UTF-8` | File encoding |
| **Modified** | `Δ` | Shown when the file has unsaved changes |
| **File Type** | ` Python` | Language icon + name |
| **Position** | `42:7` | Line:column of cursor |
| **Percentage** | `65%` | Scroll position (`Top`, `Bot`, or percentage) |

## Interactive Elements

### Diagnostics (Clickable)
Click the error/warning counts to open the **Diagnostics Popup** showing all issues. Colours:
- 🔴 Errors in red
- 🟡 Warnings in yellow

## Theming

The status bar uses theme colours:
- Mode indicator: `term_cyan` / `accent_color`
- Git branch: `accent_color`
- File type icon: `accent_color`
- Modified indicator: `git_modified` colour
- Percentage: `selection_bg`

## Settings

| Setting | Default | Description |
|---|---|---|
| `status_bar.show_full_path` | `true` | Show full file path vs just filename |
| `status_bar.item_spacing` | `12` | Spacing between right-side items (px) |
| `status_bar.inner_spacing` | `10` | Spacing within composite items (px) |
