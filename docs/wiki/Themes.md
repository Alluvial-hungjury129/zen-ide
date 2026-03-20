# Themes

Zen IDE ships with **41 built-in themes** and supports user-defined custom themes via JSON.

## Switching Themes

| Action | Shortcut |
|---|---|
| Open theme picker | `Cmd+Shift+T` |
| Toggle dark/light mode | `Cmd+Shift+L` |

The theme picker shows a live preview as you browse — the IDE updates in real-time. If you press `Escape`, the previous theme is restored.

## Built-in Themes

### Zen (Defaults)
| Theme | Style |
|---|---|
| `zen_dark` | Dark — default theme |
| `zen_light` | Light |
| `zen_style` | Styled variant |
| `zengruv` | Gruvbox-inspired Zen |

### Popular Dark Themes
| Theme | Style |
|---|---|
| `dracula` | Dracula — purple accents |
| `one_dark` | Atom One Dark |
| `tokyo_night` | Tokyo Night — blue/purple |
| `gruvbox_dark` | Gruvbox Dark — warm retro |
| `kanagawa` | Kanagawa — Japanese ink |
| `catppuccin_mocha` | Catppuccin Mocha — pastel dark |
| `melange_dark` | Melange Dark |
| `everforest` | Everforest — muted green |
| `jellybeans` | Jellybeans — dark with pops of colour |
| `oxocarbon` | Oxocarbon — IBM Carbon |
| `spacevim` | SpaceVim |

### Light Themes
| Theme | Style |
|---|---|
| `solarized_light` | Solarized Light |
| `gruvbox_light` | Gruvbox Light |
| `melange_light` | Melange Light |
| `everforest_light` | Everforest Light |
| `catppuccin_latte` | Catppuccin Latte — pastel light |

### Synthwave & Neon
| Theme | Style |
|---|---|
| `synthwave84` | Synthwave '84 — retro neon |
| `laserwave` | Laserwave — pink/purple |
| `cyberdream` | Cyberdream — high contrast neon |
| `fluoromachine` | Fluoromachine — bright neon |
| `aura_dark` | Aura Dark — deep purple |
| `new_aura_dark` | New Aura Dark |
| `aurora_borealis` | Aurora Borealis — northern lights |

### Retro
| Theme | Style |
|---|---|
| `c64_dreams` | Commodore 64 |
| `c64_videogame_dreams` | C64 Videogame Edition |
| `ega_dreams` | EGA (Enhanced Graphics Adapter) |
| `cga_dream` | CGA (Colour Graphics Adapter) |
| `retro_box` | Retro Box — old-school |
| `zx_dreams` | ZX Spectrum |

### Other
| Theme | Style |
|---|---|
| `trix` | Trix — green on black |
| `ansi_blows` | ANSI Blows |
| `modus_vivendi` | Modus Vivendi — high contrast |
| `nyoom` | Nyoom — vibrant |
| `terracotta` | Terracotta — warm earth tones |

## Custom Themes

Create a JSON file at `~/.zen_ide/custom_theme.json`:

```json
{
  "name": "my_theme",
  "display_name": "My Custom Theme",
  "editor_bg": "#1a1b26",
  "fg_color": "#c0caf5",
  "fg_dim": "#565f89",
  "accent_color": "#7aa2f7",
  "selection_bg": "#283457",
  "panel_bg": "#16161e",
  "syntax_keyword": "#9d7cd8",
  "syntax_string": "#9ece6a",
  "syntax_comment": "#565f89",
  "syntax_function": "#7aa2f7",
  "syntax_type": "#2ac3de",
  "syntax_number": "#ff9e64",
  "syntax_variable": "#c0caf5",
  "syntax_operator": "#89ddff",
  "syntax_constant": "#ff9e64",
  "git_added": "#9ece6a",
  "git_modified": "#e0af68",
  "git_deleted": "#f7768e",
  "term_black": "#15161e",
  "term_red": "#f7768e",
  "term_green": "#9ece6a",
  "term_yellow": "#e0af68",
  "term_blue": "#7aa2f7",
  "term_magenta": "#bb9af7",
  "term_cyan": "#7dcfff",
  "term_white": "#a9b1d6"
}
```

### Theme Properties

| Property | Purpose |
|---|---|
| `name` | Internal identifier (no spaces) |
| `display_name` | Shown in the theme picker |
| `editor_bg` | Editor background colour |
| `fg_color` | Primary text colour |
| `fg_dim` | Dimmed/secondary text |
| `accent_color` | UI accent colour (links, highlights) |
| `selection_bg` | Text selection background |
| `panel_bg` | Terminal/chat panel background |
| `syntax_*` | Syntax highlighting colours |
| `git_*` | Git status colours |
| `term_*` | ANSI terminal palette (16 colours) |

## Settings

| Setting | Default | Description |
|---|---|---|
| `theme` | `"zen_dark"` | Active theme name |
