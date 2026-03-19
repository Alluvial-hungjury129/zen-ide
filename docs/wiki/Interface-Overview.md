# The Interface at a Glance

Zen IDE has a clean, four-panel layout inspired by Neovim.

```
┌──────────────────────────────────────────────────────┐
│  Menu Bar   (File · Edit · View · Help)              │
├──────┬───────────────────────────────┬───────────────┤
│      │  Tab Bar                      │               │
│ File │  ┌──────────────────────────┐ │  AI Chat /    │
│ Tree │  │                          │ │  Dev Pad      │
│      │  │      Editor Area         │ │  (right       │
│      │  │                          │ │   panel)      │
│      │  │                          │ │               │
│      │  └──────────────────────────┘ │               │
├──────┴───────────────────────────────┴───────────────┤
│  Terminal (bottom panel — vertical stack or tabs)     │
├──────────────────────────────────────────────────────┤
│  Status Bar  (mode · git · file · encoding · pos)    │
└──────────────────────────────────────────────────────┘
```

## Panels

| Panel | Location | Toggle | Purpose |
|---|---|---|---|
| **File Explorer** | Left sidebar | `Cmd+Shift+E` | Browse workspace files with vim-style navigation |
| **Editor** | Centre | — | Code editing with GtkSourceView (tabs for multiple files) |
| **Terminal** | Bottom | `` Cmd+` `` | Full VTE terminal with 256-colour support |
| **AI Chat** | Right panel | Click AI tab | Multi-session AI chat with Copilot or Claude |
| **Dev Pad** | Right panel | `Cmd+.` | Activity tracker and notes |
| **Status Bar** | Bottom strip | — | Git branch, file info, cursor position, diagnostics |

## Resizing Panels

All panel dividers are draggable. Your layout is saved automatically to `~/.zen_ide/settings.json`.

| Action | How |
|---|---|
| Resize any panel | Drag the splitter border |
| Maximise a panel | `Cmd+Shift+\` |
| Reset all panels | `Cmd+Shift+0` |
| Toggle all UI | `Cmd+Shift+U` |

## Welcome Screen

When no files are open, the editor shows a branded welcome screen with:
- ASCII art Zen IDE logo
- Current version number
- Complete keyboard shortcut reference by category

## Theming

Every panel respects the active theme. Switch themes instantly with `Cmd+Shift+T` — 41 built-in themes plus custom JSON themes.

## Zoom

| Action | Shortcut |
|---|---|
| Zoom in | `Cmd++` |
| Zoom out | `Cmd+-` |
| Reset zoom | `Cmd+0` |

Zoom affects all panels simultaneously: editor, terminal, tree view, and AI chat.
