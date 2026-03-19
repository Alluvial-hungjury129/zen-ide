# Welcome Screen

**Created_at:** 2026-03-17  
**Updated_at:** 2026-03-17  
**Status:** Active  
**Goal:** Document the welcome screen shown when no files are open in the editor  
**Scope:** `src/main/welcome_screen.py`  

---

## Overview

The Welcome Screen is the default view displayed in the editor area when no files are open. It provides branding, version information, and a quick-reference guide to keyboard shortcuts — giving new and returning users an instant orientation point.

## Visual Layout

The screen renders as a scrollable panel with the editor background color and contains:

1. **ASCII Logo** — A large `ZEN IDE` banner using Unicode block characters, colored with the active theme's accent color. Block-character runs (`█`) receive a matching `background` attribute to eliminate 1-pixel inter-glyph gaps.
2. **Version** — Reads the current version from `pyproject.toml` at the project root (e.g. `v0.1.0`). Falls back to `"unknown"` if the file cannot be read.
3. **Welcome tagline** — *"Welcome to Zen IDE – A Minimalist Opinionated IDE"*
4. **Made with ❤️ in 🇬🇧**
5. **Keyboard shortcuts** — All shortcut categories from `KeyBindings.get_shortcut_categories()`, grouped and rendered with key–description pairs.

## Version Resolution

The version is read at render time from `pyproject.toml`:

```
src/main/welcome_screen.py
  → Path(__file__).parent.parent.parent  (project root)
  → project_root / "pyproject.toml"
  → parse `version = "X.Y.Z"` line
```

This ensures the displayed version always matches the single source of truth in `pyproject.toml`. No hardcoded version strings exist elsewhere.

## Theming & Font Integration

- **Theme** — The screen subscribes to `subscribe_theme_change()`. Any theme switch triggers a full UI rebuild with the new colors.
- **Font** — The screen subscribes to `subscribe_font_change()`. Font family and size changes are applied immediately.
- **Background** — Set via a GTK CSS provider using the theme's `editor_bg`.

## Lifecycle

| Event | Behavior |
|-------|----------|
| IDE starts with no files open | Welcome screen shown as the active editor tab |
| User opens a file | Welcome screen tab is replaced / another tab gains focus |
| All tabs closed | Welcome screen re-appears |
| Theme or font change | `_create_ui()` rebuilds the entire widget tree |

## Key Implementation Details

- **Class:** `WelcomeScreen(Gtk.ScrolledWindow)` — a single self-contained widget.
- **No Cairo** — all rendering uses Pango markup inside `Gtk.Label` widgets; compliant with the GtkSnapshot rendering standard.
- **Pango markup escaping** — user-facing text (shortcut names, category headers) is escaped via `GLib.markup_escape_text` to prevent injection of unintended markup.

## File Reference

| File | Role |
|------|------|
| `src/main/welcome_screen.py` | Welcome screen widget |
| `pyproject.toml` | Version source of truth |
| `src/shared/settings/keybindings.py` | Provides shortcut categories |
| `src/themes/` | Active theme colors |
| `src/fonts/` | Font family and size |
