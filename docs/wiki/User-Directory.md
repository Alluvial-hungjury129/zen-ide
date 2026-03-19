# User Directory (~/.zen_ide)

Zen IDE stores all user configuration, state, and data in `~/.zen_ide/`. This directory is created automatically on first launch.

## Directory Structure

```
~/.zen_ide/
├── settings.json          # All IDE settings (see Settings Reference)
├── dev_pad.json           # Dev Pad activity log (max 500 entries)
├── bashrc                 # Custom shell configuration (sourced by terminal)
├── aliases                # Custom shell aliases (sourced by terminal)
├── bash_history           # Terminal command history
├── font_cache.txt         # Nerd Font detection cache
├── custom_theme.json      # Custom theme definition (optional)
└── sketches/              # Saved .zen_sketch diagram files
```

## File Descriptions

### `settings.json`
The central configuration file. See [Settings Reference](Settings) for the complete list of options.

Created with sensible defaults on first launch. Edit manually or use in-app settings.

### `dev_pad.json`
Activity log for the Dev Pad panel. Automatically tracks file edits, git operations, AI chats, and manual notes. Limited to 500 entries (oldest trimmed).

### `bashrc`
Custom bash configuration sourced when the integrated terminal starts. Contains:
- Git-aware prompt with branch name
- Built-in aliases (`gst`, `groh`, `ll`, etc.)
- Coloured output settings

You can add your own shell configuration here.

### `aliases`
Custom shell aliases loaded by the terminal. Add your shortcuts:

```bash
alias gco='git checkout'
alias gp='git push'
alias dc='docker compose'
```

### `bash_history`
Terminal command history, persisted across IDE sessions.

### `font_cache.txt`
Cached result of Nerd Font detection. Delete this file to force re-detection on next launch.

### `custom_theme.json`
Optional custom theme definition. See [Themes](Themes) for the format.

### `sketches/`
Directory for saved Sketch Pad `.zen_sketch` files.

## Resetting to Defaults

To reset all settings:
```bash
rm ~/.zen_ide/settings.json
```

Zen IDE will recreate it with defaults on next launch.

To reset everything:
```bash
rm -rf ~/.zen_ide
```
