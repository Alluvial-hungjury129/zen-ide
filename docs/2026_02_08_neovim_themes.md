# Neovim Themes Integration for Zen IDE

**Created_at:** 2026-02-08  
**Updated_at:** 2026-03-16  
**Status:** Planned  
**Goal:** Strategy for sourcing Zen themes from Neovim colorscheme Lua files  
**Scope:** `src/themes/`, `src/themes/definitions/`, Catppuccin/Tokyo Night/Gruvbox colorschemes  

---

This document outlines the strategy for using Neovim colorschemes as the source for Zen IDE themes, instead of manually rebuilding theme definitions.

## Overview

Neovim themes are typically written in Lua with well-structured color palettes. Many popular themes (Tokyo Night, Catppuccin, Gruvbox, Nord, etc.) already have Lua files defining their complete color palette. This makes them an excellent source for Zen IDE themes.

## Neovim Theme Structure

### Catppuccin Example (Lua palette)

```lua
-- catppuccin/palettes/mocha.lua
return {
    rosewater = "#f5e0dc",
    flamingo = "#f2cdcd",
    pink = "#f5c2e7",
    mauve = "#cba6f7",
    red = "#f38ba8",
    maroon = "#eba0ac",
    peach = "#fab387",
    yellow = "#f9e2af",
    green = "#a6e3a1",
    teal = "#94e2d5",
    sky = "#89dceb",
    sapphire = "#74c7ec",
    blue = "#89b4fa",
    lavender = "#b4befe",
    text = "#cdd6f4",
    subtext1 = "#bac2de",
    subtext0 = "#a6adc8",
    overlay2 = "#9399b2",
    overlay1 = "#7f849c",
    overlay0 = "#6c7086",
    surface2 = "#585b70",
    surface1 = "#45475a",
    surface0 = "#313244",
    base = "#1e1e2e",
    mantle = "#181825",
    crust = "#11111b",
}
```

### Tokyo Night Example

```lua
-- tokyonight/colors.lua (simplified)
local colors = {
    bg = "#1a1b26",
    bg_dark = "#16161e",
    bg_float = "#16161e",
    bg_highlight = "#292e42",
    bg_popup = "#16161e",
    fg = "#c0caf5",
    fg_dark = "#a9b1d6",
    fg_gutter = "#3b4261",
    comment = "#565f89",
    blue = "#7aa2f7",
    cyan = "#7dcfff",
    green = "#9ece6a",
    magenta = "#bb9af7",
    orange = "#ff9e64",
    purple = "#9d7cd8",
    red = "#f7768e",
    yellow = "#e0af68",
}
```

### Gruvbox Example

```lua
-- gruvbox/colors.lua
local colors = {
    dark0_hard = "#1d2021",
    dark0 = "#282828",
    dark0_soft = "#32302f",
    dark1 = "#3c3836",
    dark2 = "#504945",
    dark3 = "#665c54",
    dark4 = "#7c6f64",
    light0_hard = "#f9f5d7",
    light0 = "#fbf1c7",
    -- ... semantic colors
    bright_red = "#fb4934",
    bright_green = "#b8bb26",
    bright_yellow = "#fabd2f",
    bright_blue = "#83a598",
    bright_purple = "#d3869b",
    bright_aqua = "#8ec07c",
    bright_orange = "#fe8019",
}
```

## Color Mapping Strategy

### Mapping Neovim → Zen IDE Theme Fields

| Neovim (Catppuccin) | Neovim (Tokyo Night) | Neovim (Gruvbox) | Zen IDE Field |
|---------------------|----------------------|------------------|---------------|
| `base` | `bg` | `dark0` | `main_bg` |
| `mantle` | `bg_dark` | `dark0_hard` | `panel_bg` |
| `crust` | `bg_float` | `dark1` | `input_bg` |
| `text` | `fg` | `light0` | `fg_color` |
| `subtext0` | `fg_dark` | `light0_soft` | `fg_dim` |
| `overlay1` | `comment` | `dark4` | `comment_color` |
| `surface1` | `bg_highlight` | `dark2` | `selection_bg` |
| `blue` | `blue` | `bright_blue` | `accent_color` |
| `mauve` | `purple` | `bright_purple` | `syntax_keyword` |
| `green` | `green` | `bright_green` | `syntax_string` |
| `peach` | `orange` | `bright_orange` | `syntax_number` |
| `yellow` | `yellow` | `bright_yellow` | `syntax_function` |
| `sky` | `cyan` | `bright_aqua` | `syntax_type` |
| `red` | `red` | `bright_red` | `syntax_error` |
| `overlay2` | `fg_gutter` | `dark3` | `line_number_color` |
| `surface0` | `bg_popup` | `dark1` | `scrollbar_bg` |

### Additional Mappings for UI Elements

| Purpose | Typical Neovim Source | Zen IDE Field |
|---------|----------------------|---------------|
| Borders | `surface2` / `border` | `border_color` |
| Current line | `bg_highlight` | `current_line_bg` |
| Search highlight | `yellow` (dimmed) | `search_highlight_bg` |
| Git added | `green` | `git_added_color` |
| Git modified | `yellow` / `orange` | `git_modified_color` |
| Git deleted | `red` | `git_deleted_color` |
| Tab active | `surface1` | `tab_active_bg` |
| Tab inactive | `mantle` | `tab_inactive_bg` |

## Implementation Options

### Option A: Ship Raw Lua Files + Runtime Parser

**Approach:**
- Include Neovim theme Lua files in `src/themes/nvim/`
- Create a Lua parser in Python to read palette definitions
- Convert to `Theme` dataclass at runtime

**Pros:**
- Easy to update themes (just replace Lua file)
- Can pull directly from theme repos
- Community themes work out-of-the-box

**Cons:**
- Requires Lua parsing (lupa library or custom parser)
- Runtime overhead
- Some themes have complex Lua logic

**Implementation:**

```python
# src/nvim_theme_loader.py
import re
from dataclasses import dataclass
from typing import Dict

def parse_lua_palette(lua_content: str) -> Dict[str, str]:
    """Parse simple Lua color palette to dict."""
    colors = {}
    # Match: key = "#hexcolor" or key = "#hexcolor",
    pattern = r'(\w+)\s*=\s*["\']?(#[0-9a-fA-F]{6})["\']?'
    for match in re.finditer(pattern, lua_content):
        colors[match.group(1)] = match.group(2)
    return colors

def nvim_to_zen_theme(palette: Dict[str, str], name: str) -> Theme:
    """Convert Neovim palette to Zen IDE Theme."""
    return Theme(
        name=name,
        main_bg=palette.get('base') or palette.get('bg'),
        panel_bg=palette.get('mantle') or palette.get('bg_dark'),
        fg_color=palette.get('text') or palette.get('fg'),
        # ... more mappings
    )
```

### Option B: Pre-convert and Ship Python Files

**Approach:**
- Create a build script that converts Lua → Python
- Ship converted Python theme files
- No runtime Lua parsing needed

**Pros:**
- No extra dependencies
- Fast loading
- Full control over conversion

**Cons:**
- Manual update process for each theme
- Conversion script maintenance

**Implementation:**

```bash
# tools/convert_nvim_themes.py
# Run during development to regenerate themes:
# python tools/convert_nvim_themes.py nvim_themes/ src/themes/
```

### Option C: Hybrid Approach (Recommended)

**Approach:**
- Ship pre-converted popular themes (Catppuccin, Tokyo Night, etc.)
- Provide runtime loader for custom Neovim themes
- Users can drop `.lua` files into `~/.zen_ide/themes/`

**Pros:**
- Fast startup with bundled themes
- Flexibility for custom themes
- Best of both worlds

**Implementation:**

```
src/
├── themes/
│   ├── definitions/       # Pre-converted Python themes (current location)
│   │   ├── catppuccin_mocha.py
│   │   ├── tokyo_night.py
│   │   └── gruvbox_dark.py
│   └── nvim_loader.py     # Runtime Lua parser for custom themes

~/.zen_ide/
├── themes/                # User's custom Neovim themes
│   └── my_theme.lua
```

## Migration Path

### Phase 1: Create Theme Converter Tool

1. Build `tools/nvim_theme_converter.py`:
   - Parse Lua palette files
   - Map colors to Zen IDE fields
   - Generate Python `Theme` dataclass

2. Test with popular themes:
   - Catppuccin (all flavors: mocha, macchiato, frappe, latte)
   - Tokyo Night (night, storm, day)
   - Gruvbox (dark, light)
   - Nord
   - Dracula

### Phase 2: Replace Existing Themes

1. Convert existing manually-created themes to use converter
2. Ensure visual parity with current themes
3. Update `themes/theme_manager.py` to load from new format

### Phase 3: Add Runtime Loader

1. Implement `nvim_loader.py` for custom themes
2. Add settings option: `ui.custom_theme_path`
3. Watch theme file for live reload

### Phase 4: Documentation & Community

1. Document how to add Neovim themes
2. Create PR template for contributing themes
3. Link to popular Neovim theme repos

## Sample Converter Script

```python
#!/usr/bin/env python3
"""
Convert Neovim Lua palette to Zen IDE Theme.

Usage:
    python tools/nvim_theme_converter.py catppuccin/mocha.lua > src/themes/catppuccin_mocha.py
"""

import re
import sys
from pathlib import Path

# Mapping from Neovim color names to Zen IDE Theme fields
# Supports multiple possible source names for each field
FIELD_MAPPING = {
    'main_bg': ['base', 'bg', 'dark0', 'background'],
    'panel_bg': ['mantle', 'bg_dark', 'dark0_hard', 'bg_sidebar'],
    'input_bg': ['crust', 'bg_float', 'dark1', 'bg_popup'],
    'fg_color': ['text', 'fg', 'light0', 'foreground'],
    'fg_dim': ['subtext0', 'fg_dark', 'light0_soft', 'fg_dim'],
    'fg_muted': ['subtext1', 'comment', 'dark4', 'fg_gutter'],
    'accent_color': ['blue', 'accent', 'bright_blue', 'primary'],
    'selection_bg': ['surface1', 'bg_highlight', 'dark2', 'visual'],
    'border_color': ['surface2', 'border', 'dark3'],
    'syntax_keyword': ['mauve', 'purple', 'bright_purple', 'keyword'],
    'syntax_string': ['green', 'bright_green', 'string'],
    'syntax_number': ['peach', 'orange', 'bright_orange', 'number'],
    'syntax_function': ['yellow', 'bright_yellow', 'function'],
    'syntax_type': ['sky', 'cyan', 'bright_aqua', 'type'],
    'syntax_comment': ['overlay1', 'comment', 'dark4'],
    'syntax_variable': ['text', 'fg', 'light0'],
    'syntax_operator': ['sky', 'cyan', 'operator'],
    'syntax_constant': ['peach', 'orange', 'constant'],
    'syntax_builtin': ['red', 'bright_red', 'builtin'],
    'syntax_error': ['red', 'bright_red', 'error'],
    'git_added': ['green', 'bright_green', 'git_add'],
    'git_modified': ['yellow', 'bright_yellow', 'git_change'],
    'git_deleted': ['red', 'bright_red', 'git_delete'],
    'line_number_color': ['overlay2', 'fg_gutter', 'dark3'],
    'current_line_bg': ['surface0', 'bg_highlight', 'dark1'],
    'scrollbar_bg': ['surface0', 'bg_popup', 'dark1'],
    'scrollbar_thumb': ['surface2', 'fg_gutter', 'dark3'],
    'tab_active_bg': ['surface1', 'bg_highlight', 'dark2'],
    'tab_inactive_bg': ['mantle', 'bg_dark', 'dark0_hard'],
}


def parse_lua_palette(content: str) -> dict:
    """Parse Lua palette file to extract color definitions."""
    colors = {}
    
    # Match patterns like: key = "#hexcolor" or key = "#hexcolor",
    pattern = r'[\s,](\w+)\s*=\s*["\']?(#[0-9a-fA-F]{6})["\']?'
    
    for match in re.finditer(pattern, content):
        key = match.group(1)
        value = match.group(2)
        colors[key] = value
    
    return colors


def map_colors(nvim_palette: dict) -> dict:
    """Map Neovim colors to Zen IDE theme fields."""
    zen_theme = {}
    
    for field, possible_keys in FIELD_MAPPING.items():
        for key in possible_keys:
            if key in nvim_palette:
                zen_theme[field] = nvim_palette[key]
                break
        else:
            # Field not found - will use default or raise warning
            print(f"# Warning: No mapping found for '{field}'", file=sys.stderr)
    
    return zen_theme


def generate_python_theme(name: str, colors: dict) -> str:
    """Generate Python theme file content."""
    class_name = ''.join(word.title() for word in name.replace('-', '_').split('_'))
    
    lines = [
        '"""',
        f'{name} theme - converted from Neovim colorscheme.',
        '"""',
        'from dataclasses import dataclass',
        'from themes import Theme',
        '',
        '',
        f'def create_{name.replace("-", "_")}_theme() -> Theme:',
        f'    """Create {class_name} theme."""',
        '    return Theme(',
        f'        name="{name}",',
    ]
    
    for field, value in sorted(colors.items()):
        lines.append(f'        {field}="{value}",')
    
    lines.append('    )')
    lines.append('')
    
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: nvim_theme_converter.py <lua_file> [theme_name]")
        sys.exit(1)
    
    lua_file = Path(sys.argv[1])
    theme_name = sys.argv[2] if len(sys.argv) > 2 else lua_file.stem
    
    content = lua_file.read_text()
    palette = parse_lua_palette(content)
    zen_colors = map_colors(palette)
    output = generate_python_theme(theme_name, zen_colors)
    
    print(output)


if __name__ == '__main__':
    main()
```

## Supported Neovim Theme Repositories

| Theme | Repository | Palette Location |
|-------|------------|------------------|
| Catppuccin | `catppuccin/nvim` | `lua/catppuccin/palettes/*.lua` |
| Tokyo Night | `folke/tokyonight.nvim` | `lua/tokyonight/colors/*.lua` |
| Gruvbox | `ellisonleao/gruvbox.nvim` | `lua/gruvbox/palette.lua` |
| Nord | `shaunsingh/nord.nvim` | `lua/nord/colors.lua` |
| Dracula | `Mofiqul/dracula.nvim` | `lua/dracula/palette.lua` |
| One Dark | `navarasu/onedark.nvim` | `lua/onedark/palette.lua` |
| Kanagawa | `rebelot/kanagawa.nvim` | `lua/kanagawa/colors.lua` |
| Everforest | `sainnhe/everforest` | `lua/everforest/palette.lua` |
| Rose Pine | `rose-pine/neovim` | `lua/rose-pine/palette.lua` |
| Nightfox | `EdenEast/nightfox.nvim` | `lua/nightfox/palette/*.lua` |

## Benefits Summary

1. **Consistency** - Use battle-tested color combinations from popular themes
2. **Maintenance** - Updates come from theme maintainers
3. **Community** - Leverage huge Neovim theme ecosystem
4. **Familiarity** - Users can use themes they already know
5. **Quality** - Neovim themes are optimized for code readability

## Next Steps

1. [ ] Create `tools/nvim_theme_converter.py` script
2. [ ] Convert Catppuccin Mocha as first test
3. [ ] Validate visual output matches original theme
4. [ ] Convert remaining bundled themes
5. [ ] Implement runtime Lua loader for custom themes
6. [ ] Add theme hot-reload for development
7. [ ] Document theme contribution process
