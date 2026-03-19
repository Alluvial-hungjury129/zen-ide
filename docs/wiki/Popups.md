# Popup Dialogs

All dialogs in Zen IDE are Neovim-style floating popups that inherit from the `NvimPopup` base class. They feature themed borders, keyboard-first navigation, and consistent behaviour.

## Common Navigation

All popups share these keyboard conventions:

| Key | Action |
|---|---|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `Enter` | Select / Confirm |
| `Escape` / `q` | Close / Cancel |
| `Tab` | Switch focus between elements |
| `Ctrl+N` / `Ctrl+P` | Next / Previous item |

Clicking outside a popup closes it.

## Dialog Reference

### Command Palette

**Trigger:** `Cmd+Shift+P` (or from menu)

Fuzzy command search — type to filter, `Enter` to execute. Shows command names, descriptions, and keybindings.

### Quick Open

**Trigger:** `Cmd+P`

Fuzzy file finder across the workspace. Type a filename to filter, `Enter` to open. Respects `.gitignore`. Results limited to 100 matches.

### Global Search

**Trigger:** `Cmd+Shift+F`

Full-text search across all workspace files. Shows matching files with highlighted line previews. Click a result to open at that line.

### Find & Replace

**Trigger:** `Cmd+F`

In-file search with regex and case-sensitivity toggles. `Cmd+G` / `Cmd+Shift+G` for next/previous match.

### Theme Picker

**Trigger:** `Cmd+Shift+T`

Browse all 41 themes with live preview. The IDE updates in real-time as you navigate. `Escape` reverts to the previous theme.

### Font Picker

**Trigger:** View menu → Font Picker

Select fonts for each UI component (editor, terminal, explorer, AI chat, markdown preview). Includes search, size selector, and live preview.

### Colour Picker

**Trigger:** Click a colour swatch in the editor

Interactive colour selection with:
- Hex input field
- RGB(A) sliders
- 30 preset colour palette
- Live preview swatch

### Keyboard Shortcuts

**Trigger:** `Cmd+Shift+/`

Read-only list of all keyboard shortcuts, organised by category. Scroll with `j`/`k`.

### Diagnostics Popup

**Trigger:** Click error/warning count in status bar

Shows all diagnostics (linting errors/warnings) for the current file or workspace. Navigate with `j`/`k`, press `Enter` to jump to the error line.

### Input Dialog

Used by rename, new file, and other operations requiring text input. Type your value, `Enter` to confirm, `Escape` to cancel.

### Confirmation Dialog

Used for destructive actions (delete, discard changes). Shows a message with Yes/No buttons:
- `y` or `Enter` → Confirm
- `n` or `Escape` → Cancel
- Danger mode uses red styling for destructive actions

### Save Confirmation

Appears when closing a tab with unsaved changes:
- **Save** — Save and close
- **Discard** — Close without saving
- **Cancel** — Keep the tab open

For multiple unsaved files, the Save All dialog shows up to 5 filenames with "...and N more" for overflow.

### About Popup

**Trigger:** Help menu → About

Shows IDE version, framework information, and license.

### System Monitor

**Trigger:** From menu

Displays CPU usage, memory consumption, and disk usage.

### Context Menu

**Trigger:** Right-click in tree view or editor

Dropdown menu with context-appropriate actions. See [File Explorer](File-Explorer) for tree context menu options.

## Popup Settings

| Setting | Default | Description |
|---|---|---|
| `popup.border_radius` | `0` | Corner radius for popup windows (px) |
