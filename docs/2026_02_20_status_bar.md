# Status Bar

**Created_at:** 2026-02-20  
**Updated_at:** 2026-03-15  
**Status:** Active  
**Goal:** Document the Neovim-style status bar with file info, git branch, cursor position, and encoding segments  
**Scope:** `src/main/status_bar.py`  

---

The status bar is a Neovim-style information bar at the bottom of the Zen IDE window. It provides at-a-glance context about the active file, cursor position, and git state.

## Source

| File | Class | Description |
|------|-------|-------------|
| `src/main/status_bar.py` | `StatusBar` | Main status bar widget (extends `Gtk.Box`) |

## Layout

The bar is divided into three sections:

```
┌──────────────────────────────────────────────────────────────────────┐
│ [Zen Icon] │ ⎇ branch │ ~/path/to/file.py │  spacer  │ UTF-8 │ Δ │  python │ 42:7 │ 65% │
│  LEFT      │  LEFT     │  LEFT              │          │ RIGHT │   │  RIGHT  │ RIGHT│RIGHT│
└──────────────────────────────────────────────────────────────────────┘
```

### Left Section

| Segment | CSS Class | Content |
|---------|-----------|---------|
| **Mode indicator** | `status-mode` | Zen icon (from `zen_icon.png`) or fallback "Z". Mode label is hidden until vim-mode support is added. |
| **Git branch** | `status-git` | Branch icon (`⎇`) + current branch name. Detected asynchronously via `git rev-parse --abbrev-ref HEAD`. Hidden when not in a git repo. |
| **File path** | `status-filepath` | Path of the active file. Displays `~/…` shortened path or just the filename, controlled by the `status_bar.show_full_path` setting. Hidden when no file is open. |

### Right Section

| Segment | CSS Class | Content |
|---------|-----------|---------|
| **Encoding** | `status-encoding` | File encoding (`UTF-8`, `UTF-16`, `UTF-8-BOM`, `Binary`). Detected by reading initial bytes of the file. |
| **Modified** | `status-modified` | Shows `Δ` when the buffer has unsaved changes. Colored with the theme's `git_modified` color. |
| **File type** | `status-filetype` | Nerd Font icon + language name (e.g. ` python`). Icon colors match the tree view via `ICON_COLORS`. Supports 50+ file extensions. |
| **Position** | `status-position` | Cursor line and column (`line:col`). |
| **Percentage** | `status-percent` | Scroll position: `Top`, `Bot`, or `N%`. |

## Integration with the Main Window

The status bar is created during deferred initialization (`_deferred_init` in `zen_ide.py`) to avoid slowing down first paint. A lightweight placeholder `Gtk.Box` is rendered initially and replaced with the real `StatusBar` once the UI is ready.

### Update triggers

| Event | Method Called | Source |
|-------|-------------|--------|
| Tab switched | `set_file()`, `set_position()`, `set_modified()` | `_on_editor_tab_switched` |
| File opened | `set_file()`, `set_position()` | `_on_editor_file_opened` |
| Tab reveal (switch) | `set_file()`, `set_position()` | `_on_editor_tab_switched_reveal` |
| Cursor moved | `set_position()` | `_on_cursor_position_changed` |
| All tabs closed | `set_file(None)` | Tab close handler |

## Theming

Each segment has its own background and foreground colors derived from the active theme:

| Segment | Background | Foreground |
|---------|-----------|------------|
| Mode | `theme.term_cyan` / `theme.accent_color` | Auto-contrast (black or white) |
| Git | `theme.accent_color` | Auto-contrast |
| File path | `theme.panel_bg` | White |
| Encoding | `theme.panel_bg` | `theme.fg_dim` |
| Modified | `theme.panel_bg` | `theme.git_modified` |
| File type | `theme.accent_color` | Auto-contrast |
| Position | `theme.panel_bg` | `theme.fg_dim` |
| Percentage | `theme.selection_bg` | `theme.fg_color` |

The status bar always uses `SauceCodePro Nerd Font` for visual consistency. Font size follows the editor font size, and theme/font updates are applied live via subscriptions to `subscribe_theme_change`, `subscribe_settings_change`, and `subscribe_font_change`.

## Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `status_bar.show_full_path` | `bool` | `true` | Show the full `~/…` file path or just the filename. |

## Public API

```python
class StatusBar(Gtk.Box):
    def set_file(self, file_path: Optional[str])          # Update active file display
    def set_position(self, line: int, col: int, total: int) # Update cursor position
    def set_modified(self, modified: bool)                 # Update modified indicator
    def set_encoding(self, encoding: str)                  # Update encoding label
    def set_mode(self, mode: str)                          # Update mode (future vim-mode)
    def set_workspace_folders(self, folders: list)          # Set workspace for git detection
```
