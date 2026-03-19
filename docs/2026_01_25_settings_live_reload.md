# Settings Live Reload

**Created_at:** 2026-01-25  
**Updated_at:** 2026-03-16  
**Status:** Active  
**Goal:** Document how Zen IDE reloads `~/.zen_ide/settings.json` changes live without restarting.  
**Scope:** `src/shared/settings/settings_manager.py`, `src/zen_ide.py`, `~/.zen_ide/settings.json`  

---

## Summary

Zen IDE watches `~/.zen_ide/settings.json` for external changes and applies updates in real time without restarting the application.

## How It Works

1. **File watcher** in `src/shared/settings/settings_manager.py`
   - Uses `watchfiles` to monitor the settings file.
   - Runs in a background thread.
   - Debounces rapid edits before notifying the app.

2. **Settings application** in `src/zen_ide.py`
   - Reloads settings when the watcher reports a change.
   - Reapplies affected configuration across the UI.

## Settings Applied Live

- Theme switching
- Word wrap
- Cursor blink
- AI suggestions toggle
- Font settings for editor, tree view, terminal, and AI chat
- Trailing whitespace trimming

## Usage

1. Open settings from **View -> Open Settings...**.
2. Edit `~/.zen_ide/settings.json` in any editor.
3. Save the file.
4. Zen IDE applies supported changes immediately.
