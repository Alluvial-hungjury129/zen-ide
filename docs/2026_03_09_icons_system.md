# IconsManager System

**Created_at:** 2026-03-09  
**Updated_at:** 2026-03-09  
**Status:** Active  
**Goal:** Document the centralised icon management system, file-type icon mapping, and rendering helpers  
**Scope:** `src/icons/icon_manager.py`, `src/icons/__init__.py`, `src/treeview/tree_icons.py`, `src/fonts/font_manager.py`, `src/constants.py`  

---

## Overview

Zen IDE uses a centralised icon system built on **Nerd Fonts**. All UI icons — buttons, context menus, notifications, file-type indicators, autocomplete kinds, and sketch pad tools — are defined as named constants in a single `IconsManager` class. Components import these constants instead of hardcoding Unicode code-points.

The system has two layers:

| Layer | File | Purpose |
|-------|------|---------|
| **Global** | `src/icons/icon_manager.py` | All UI icons, file-type lookup, icon label rendering |
| **Tree view** | `src/treeview/tree_icons.py` | Tree-specific icons with emoji fallback, color palette, git status colors |

The global layer (`icon_manager.py`) imports the color palette from the tree layer (`tree_icons.py`) to ensure consistent file-type colors across the entire UI.

---

## Architecture

```
src/icons/
├── __init__.py          # Public API (re-exports)
└── icon_manager.py      # IconsManager class, file lookup, label helper

src/treeview/
└── tree_icons.py        # Tree icons, emoji fallback, ICON_COLORS, git status

src/fonts/
├── font_manager.py      # Nerd Font loading, detection, caching
└── resources/
    └── SauceCodeProNerdFont.ttf   # Bundled font (2.3 MB)

src/constants.py
└── NERD_ICON_SIZE_OFFSET = 3      # Extra pt added to icon font size
```

### Data flow

```
get_file_icon("main.py")
    ↓
  1. Check workspace extensions (constants.WORKSPACE_EXTENSIONS)
  2. Check _FILE_NAME_MAP by filename
  3. Check _FILE_ICON_MAP by extension
  4. Fallback → IconsManager.FILE_DEFAULT
    ↓
  Color lookup from tree_icons.ICON_COLORS
    ↓
  Returns (icon_char, hex_color)
```

---

## Public API

All imports go through `src/icons/__init__.py`:

```python
from icons import IconsManager, create_icon_label, get_file_icon, ICON_SIZE_CSS_CLASS
```

| Export | Type | Description |
|--------|------|-------------|
| `IconsManager` | class | Named constants for every icon |
| `get_file_icon(path)` | function | Returns `(icon_char, hex_color)` for a file path |
| `create_icon_label(icon, size_pt)` | function | Creates a consistently-sized `Gtk.Label` |
| `ICON_SIZE_CSS_CLASS` | str | CSS class `"zen-icon"` applied to all icon labels |

---

## Icon Constants

The `IconsManager` class contains **~110 named constants** grouped by category. Each value is a single Unicode character — either a Nerd Font code-point or a standard Unicode symbol.

### Actions (buttons & context menus)

| Constant | Glyph | Nerd Font Name |
|----------|-------|----------------|
| `PLUS` | `\uf067` | nf-fa-plus |
| `TRASH` | `\uf1f8` | nf-fa-trash |
| `CUT` | `\uf0c4` | nf-fa-scissors |
| `COPY` | `\uf0c5` | nf-fa-copy |
| `PASTE` | `\uf0ea` | nf-fa-paste |
| `SELECT_ALL` | `\uf245` | nf-fa-mouse_pointer |
| `EDIT` | `\uf044` | nf-fa-pencil |
| `UNDO` | `\uf2ea` | nf-fa-undo_alt |
| `WRENCH` | `\uf0ad` | nf-fa-wrench |
| `GLOBE` | `\uf0ac` | nf-fa-globe |
| `PENCIL` | `\uf040` | nf-fa-pencil |
| `DELETE` | `\U0000ee23` | nf-md-delete |
| `EXPORT` | `\U000f0207` | nf-md-export |
| `IMPORT` | `\U000f02fa` | nf-md-import |
| `ERASER` | `\U000f0b89` | nf-md-eraser |
| `COG` | `\U000f0493` | nf-md-cog |
| `ZOOM_IN` | `\ueb81` | nf-cod-zoom_in |
| `ZOOM_OUT` | `\ueb82` | nf-cod-zoom_out |
| `ZOOM_RESET` | `\uf50d` | nf-md-magnify_remove_outline |
| `MAXIMIZE` | `⛶` | Unicode |
| `CLOSE` | `×` | Unicode |
| `NEW_TAB` | `󰐕` | nf-md-plus_circle_outline |
| `MENU` | `\ueb94` | nf-cod-menu |

### File & folder

| Constant | Description |
|----------|-------------|
| `FILE` | Generic file |
| `FILE_BINARY` | Binary file |
| `FOLDER_CLOSED` | Closed folder |
| `FOLDER_OPEN` | Open folder |
| `HEART` | Favourite/heart |

### Notifications & status

| Constant | Glyph | Usage |
|----------|-------|-------|
| `INFO` | ℹ | Info toast |
| `SUCCESS` | ✓ | Success toast |
| `WARNING` | ⚠ | Warning toast |
| `ERROR` | ✗ | Error toast |
| `ERROR_X` | ✕ | Close/dismiss |
| `MODIFIED_DOT` | ● | Unsaved indicator |
| `STOP` | ⏹ | Stop action |

### Git

| Constant | Glyph | Nerd Font Name |
|----------|-------|----------------|
| `GIT_BRANCH` | `\ue725` | nf-dev-git_branch |

### File-type icons

~53 constants following the pattern `FILE_<LANGUAGE>`. Used by the status bar and `get_file_icon()`:

| Constant | Language/Type |
|----------|--------------|
| `FILE_PYTHON` | Python |
| `FILE_JS` / `FILE_JSX` | JavaScript |
| `FILE_TS` / `FILE_TSX` | TypeScript |
| `FILE_HTML` | HTML |
| `FILE_CSS` / `FILE_SCSS` / `FILE_SASS` / `FILE_LESS` | Styles |
| `FILE_JSON` / `FILE_YAML` / `FILE_XML` / `FILE_TOML` / `FILE_INI` | Config |
| `FILE_MD` | Markdown |
| `FILE_RUST` / `FILE_GO` / `FILE_JAVA` / `FILE_RUBY` / `FILE_PHP` | Server languages |
| `FILE_C` / `FILE_CPP` / `FILE_CSHARP` / `FILE_SWIFT` / `FILE_DART` | Compiled languages |
| `FILE_KOTLIN` / `FILE_SCALA` / `FILE_R` / `FILE_JULIA` / `FILE_LUA` / `FILE_VIM` | Other languages |
| `FILE_SQL` / `FILE_GRAPHQL` | Query languages |
| `FILE_SHELL` | Shell scripts |
| `FILE_DOCKER` / `FILE_MAKEFILE` / `FILE_GITIGNORE` / `FILE_ENV` | DevOps/config |
| `FILE_VUE` / `FILE_SVELTE` | Frontend frameworks |
| `FILE_IMAGE` / `FILE_PDF` / `FILE_ARCHIVE` | Media/archives |
| `FILE_LOCK` / `FILE_LICENSE` / `FILE_TEXT` / `FILE_LOG` | Special files |
| `FILE_SKETCH` / `FILE_WORKSPACE` | Zen IDE files |
| `FILE_DEFAULT` | Fallback |

### Autocomplete kind icons

| Constant | Glyph | Completion type |
|----------|-------|-----------------|
| `KIND_FUNCTION` | ƒ | Functions/methods |
| `KIND_CLASS` | ◆ | Classes/types |
| `KIND_PROPERTY` | ● | Properties/fields |
| `KIND_KEYWORD` | κ | Language keywords |
| `KIND_BUILTIN` | β | Built-in symbols |
| `KIND_SNIPPET` | ⌘ | Snippets |
| `KIND_VARIABLE` | ν | Variables |
| `KIND_PARAMETER` | π | Parameters |

### Sketch pad tools

| Constant | Nerd Font Name | Tool |
|----------|----------------|------|
| `TOOL_SELECT` | nf-md-cursor_default | Selection tool |
| `TOOL_PAN` | nf-md-pan | Pan/scroll |
| `TOOL_RECTANGLE` | nf-md-rectangle | Draw rectangle |
| `TOOL_ARROW` | nf-md-arrow | Solid arrow |
| `TOOL_ARROW_DOTTED` | nf-md-arrow | Dotted arrow |
| `TOOL_ACTOR` | nf-md-account | Actor/person |
| `TOOL_TOPIC` | — | Topic bubble |
| `TOOL_DATABASE` | — | Database shape |
| `TOOL_CLOUD` | nf-cod-cloud | Cloud shape |
| `TOOL_SETTINGS` | — | Settings/gear |

---

## File-Type Icon Lookup

### `get_file_icon(file_path) → (icon_char, hex_color)`

Resolution priority:

1. **Workspace extensions** — if the file ends with a workspace extension (from `constants.WORKSPACE_EXTENSIONS`), returns `(FILE_WORKSPACE, default_color)`
2. **Filename match** — case-insensitive lookup in `_FILE_NAME_MAP` (6 entries: `dockerfile`, `makefile`, `cmakelists.txt`, `license`, `.gitignore`, `.env`)
3. **Extension match** — lookup in `_FILE_ICON_MAP` (~65 extensions)
4. **Fallback** — `IconsManager.FILE_DEFAULT`

### Color resolution

Colors come from `ICON_COLORS` in `src/treeview/tree_icons.py`:

1. Try `ICON_COLORS[original_basename]` (e.g., `"Dockerfile"`)
2. Try `ICON_COLORS[extension]` (e.g., `".py"`)
3. Fallback to `ICON_COLORS["default"]` → `"#6d8086"` (gray)

### Color palette

| Key | Color | Usage |
|-----|-------|-------|
| `folder` | `#dcb67a` | Folder icons |
| `.py` | `#ffbc03` | Python files |
| `.js` | `#f1e05a` | JavaScript files |
| `.ts` | `#3178c6` | TypeScript files |
| `.jsx` / `.tsx` | `#61dafb` | React files |
| `.html` | `#e34c26` | HTML files |
| `.css` | `#563d7c` | CSS files |
| `.json` | `#cbcb41` | JSON files |
| `.yaml` / `.yml` | `#cb171e` | YAML files |
| `.md` | `#ffffff` | Markdown files |
| `.sh` | `#89e051` | Shell scripts |
| `.go` | `#00ADD8` | Go files |
| `.rb` | `#701516` | Ruby files |
| `.rs` | `#dea584` | Rust files |
| `default` | `#6d8086` | Everything else |

---

## Icon Label Rendering

### `create_icon_label(icon, size_pt=None) → Gtk.Label`

Creates a `Gtk.Label` with consistent icon sizing:

1. Sets label text to the icon character
2. Adds `"zen-icon"` CSS class
3. If `size_pt` is `None`, uses editor font size + `NERD_ICON_SIZE_OFFSET` (3 pt)
4. Applies `Pango.attr_size_new(size_pt * Pango.SCALE)`

```python
from icons import IconsManager, create_icon_label

# Auto-size (editor font size + 3pt)
label = create_icon_label(IconsManager.FILE_PYTHON)

# Explicit size
label = create_icon_label(IconsManager.PLUS, size_pt=16)
```

---

## CSS Integration

The `.zen-icon` CSS class is set on all icon labels via `create_icon_label()`. It is defined in `src/main/window_layout.py`:

```css
.zen-icon {
    font-family: "{nerd_font}", system-ui, sans-serif;
}
```

Toast notification icons have level-specific color classes:

```css
.toast-icon-info    { color: {theme.accent_color}; }
.toast-icon-success { color: {theme.git_added}; }
.toast-icon-warning { color: {theme.git_modified}; }
.toast-icon-error   { color: {theme.git_deleted}; }
```

---

## Nerd Font Loading

### Bundled font

Zen IDE bundles **SauceCodePro Nerd Font** (`src/fonts/resources/SauceCodeProNerdFont.ttf`, 2.3 MB) to guarantee Nerd Font availability on all platforms.

### Registration

Font registration is **deferred** to avoid startup penalty (~300 ms):

- **macOS**: Uses CoreText `CTFontManagerRegisterFontsForURL` (process-scoped)
- **Linux**: Uses fontconfig `FcConfigAppFontAddFile`
- Called from `register_resource_fonts()` in `src/fonts/font_manager.py` during deferred init

### Detection & caching

The tree view detects available Nerd Fonts via Pango and caches the result in `~/.zen_ide/font_cache.txt` to avoid re-scanning on every launch.

### Platform defaults

| Platform | Default font |
|----------|-------------|
| macOS | SauceCodePro Nerd Font |
| Linux | JetBrains Mono (or Nerd Font if available) |
| Windows | Consolas |

### Fallback chain

When Nerd Font is unavailable (e.g., Windows without manual install), the tree view falls back to **emoji icons** via `EMOJI_FILE_ICONS` in `tree_icons.py`.

---

## Tree View Icon System

The tree view has its own icon layer in `src/treeview/tree_icons.py` that wraps the global `IconsManager` system with:

- **Emoji fallback** — `EMOJI_FILE_ICONS` dict for systems without Nerd Fonts
- **Nerd Font detection** — `get_nerd_font_name()` checks for 12 known Nerd Font variants
- **Chevron icons** — expandable tree chevrons with Nerd Font / Unicode fallback
- **Git status colors** — `get_git_status_colors()` returns theme-aware colors for Modified, Added, Deleted, Renamed, Untracked

### `get_icon_set() → (file_icons, name_icons, folder_closed, folder_open)`

Returns the appropriate icon set based on Nerd Font availability. Used by `tree_panel.py` to populate its internal `_icon_map`.

---

## Usage Patterns

### Direct icon constants (buttons)

```python
from icons import IconsManager

btn = Gtk.Button(label=IconsManager.PLUS)
clear_btn = Gtk.Button(label=IconsManager.TRASH)
```

### File icon lookup (status bar)

```python
from icons import get_file_icon

icon, color = get_file_icon("/path/to/file.py")
# Returns ("\ue73c", "#ffbc03")
```

### Styled icon label (consistent sizing)

```python
from icons import IconsManager, create_icon_label

label = create_icon_label(IconsManager.FILE_PYTHON, size_pt=14)
```

### Autocomplete kind icons

```python
from icons import IconsManager

COMPLETION_ICONS = {
    CompletionKind.FUNCTION: IconsManager.KIND_FUNCTION,   # ƒ
    CompletionKind.CLASS: IconsManager.KIND_CLASS,           # ◆
    CompletionKind.VARIABLE: IconsManager.KIND_VARIABLE,    # ν
}
```

### Toast notifications

```python
from icons import IconsManager

icon_map = {
    "info": IconsManager.INFO,       # ℹ
    "success": IconsManager.SUCCESS, # ✓
    "warning": IconsManager.WARNING, # ⚠
    "error": IconsManager.ERROR,     # ✗
}
```

---

## Consumers

| Component | File | IconsManager used |
|-----------|------|------------|
| Status bar | `src/main/status_bar.py` | `get_file_icon()` for file type + color |
| Tree view | `src/treeview/tree_panel.py` | `get_icon_set()`, `IconsManager.FILE`, chevrons |
| Tree view renderer | `src/treeview/tree_panel_renderer.py` | `ICON_COLORS`, `get_git_status_colors()` |
| Tree actions | `src/treeview/tree_view_actions.py` | Action icons (copy, paste, delete, etc.) |
| Autocomplete | `src/editor/autocomplete/autocomplete.py` | `KIND_*` icons |
| Editor | `src/editor/editor_view.py` | Various editor icons |
| Binary viewer | `src/editor/preview/binary_viewer.py` | `FILE_BINARY` |
| Terminal header | `src/terminal/terminal_header.py` | `PLUS`, `TRASH`, `MAXIMIZE`, `CLOSE` |
| Terminal shortcuts | `src/terminal/terminal_shortcuts.py` | `COPY`, `PASTE`, `SELECT_ALL` |
| Sketch pad | `src/sketch_pad/sketch_pad.py` | `TOOL_*` icons, `ZOOM_*`, `ERASER` |
| Toast notifications | `src/popups/notification_toast.py` | `INFO`, `SUCCESS`, `WARNING`, `ERROR` |
| Diagnostics popup | `src/popups/diagnostics_popup.py` | Diagnostic icons |
| Global search | `src/popups/global_search_dialog.py` | Search UI icons |
| AI chat | `src/ai/ai_chat_tabs.py` | AI chat UI icons |
| AI terminal | `src/ai/ai_chat_terminal.py` | AI terminal icons |
| Welcome screen | `src/main/welcome_screen.py` | Welcome screen icons |

---

## Adding a New Icon

1. **Find the glyph** at [nerdfonts.com/cheat-sheet](https://www.nerdfonts.com/cheat-sheet)
2. **Add the constant** to the appropriate category in `IconsManager` class (`src/icons/icon_manager.py`)
3. **If it's a file-type icon**, also add the extension mapping to `_FILE_ICON_MAP` and optionally to `NERD_FILE_ICONS` in `tree_icons.py`
4. **If it needs a color**, add the extension entry to `ICON_COLORS` in `tree_icons.py`
5. **Use it** via `from icons import IconsManager` — never hardcode the Unicode value

```python
# In icon_manager.py
class IconsManager:
    MY_NEW_ICON = "\uf123"  # nf-fa-something

# In your component
from icons import IconsManager
btn = Gtk.Button(label=IconsManager.MY_NEW_ICON)
```
