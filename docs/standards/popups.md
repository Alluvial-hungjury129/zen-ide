# Popups — Inherit from NvimPopup

**Created_at:** 2026-02-09  
**Updated_at:** 2026-03-09  
**Status:** Active  
**Goal:** Enforce NvimPopup as the base class for all popup windows — no exceptions  
**Scope:** `src/popups/`, all floating window implementations  

---

## Rule

**All popup windows MUST inherit from `NvimPopup`.** No exceptions. The base class in `src/popups/nvim_popup.py` provides consistent neovim-style floating windows with:

- Centered positioning on parent window (default)
- Anchored positioning relative to any widget (via `anchor_widget` + `anchor_rect`)
- Non-modal, non-focus-stealing mode (via `modal=False, steal_focus=False`)
- Vim-style keyboard navigation (j/k, Enter, Escape)
- Theme integration with accent borders
- Reusable popups via `popup()`/`popdown()` (when `steal_focus=False`)

See `src/popups/` for real examples (`KeyboardShortcutsPopup`, `AboutPopup`).

```python
from nvim_popup import NvimPopup

# Centered modal popup (default)
class MyPopup(NvimPopup):
    def __init__(self, parent):
        super().__init__(parent, title="My Popup", width=400)
    
    def _create_content(self):
        # Add your widgets to self._content_box
        pass

# Anchored non-modal popup (e.g. autocomplete)
popup = NvimPopup(
    parent=window,
    anchor_widget=editor_view,
    anchor_rect=cursor_rect,
    modal=False,
    steal_focus=False,
)
popup.popup()    # Show without stealing focus
popup.popdown()  # Hide without destroying
```

## Popup Reference

All popup/dialog classes and their locations:

| Class | File | Use Case | Trigger |
|-------|------|----------|---------|
| **NvimPopup** | `src/popups/nvim_popup.py` | Base class for all floating popups | — |
| **NvimContextMenu** | `src/popups/nvim_context_menu.py` | Right-click context menu with vim navigation | Right-click on UI elements |
| **KeyboardShortcutsPopup** | `src/popups/keyboard_shortcuts_popup.py` | Categorized keyboard shortcuts list | `Ctrl+?` |
| **AboutPopup** | `src/popups/about_popup.py` | App info (version, framework, license) | Menu action |
| **GlobalSearchDialog** | `src/popups/global_search_dialog.py` | Search across all workspace files | `Ctrl+Shift+F` |
| **QuickOpenDialog** | `src/popups/quick_open_dialog.py` | Fuzzy file finder | `Ctrl+P` |
| **InputDialog** | `src/popups/input_dialog.py` | Single text entry prompt with validation | `show_input()` |
| **ConfirmDialog** | `src/popups/confirm_dialog.py` | Yes/No confirmation (y/n/Tab keybinds) | `show_confirm()` |
| **SelectionDialog** | `src/popups/selection_dialog.py` | Multi-item selection list (j/k + number keys) | `show_selection()` |
| **CommandPaletteDialog** | `src/popups/command_palette_dialog.py` | Fuzzy-searchable command palette | `show_command_palette()` |
| **SaveConfirmPopup** | `src/popups/save_confirm_popup.py` | Save/Discard/Cancel for unsaved files (s/d/c) | `show_save_confirm()` |
| **SaveAllConfirmPopup** | `src/popups/save_all_confirm_popup.py` | Save All/Discard All/Cancel for multiple files | Window close with unsaved files |
| **FontPickerDialog** | `src/popups/font_picker_dialog.py` | Font family and size selection | Settings/Preferences |
| **AIPopup** | `src/popups/copilot_popup.py` | AI-generated code suggestions (j/k, Enter) | AI completion event |
| **Autocomplete** | `src/editor/autocomplete/autocomplete.py` | Code completions at cursor (anchored, non-modal NvimPopup) | `Ctrl+Space` or auto-trigger |
| **CopilotPopup** | `src/ai/ai_chat_tabs.py` | GitHub Copilot provider confirmation | Switching to Copilot provider |
| **SystemMonitorDialog** | `src/system_monitor.py` | Real-time CPU, memory, disk, process stats | Menu action |
| **ColorPickerPopup** | `src/popups/color_picker_popup.py` | Hex color editor with RGB(A) sliders and live preview | Click on inline color swatch |
| **ApiKeySetupPopup** | `src/popups/api_key_setup_popup.py` | API key entry for HTTP AI providers (Anthropic, OpenAI) | Provider selection in AI chat |

### NvimContextMenu Usages

Via `show_context_menu()` helper:

| Usage | File | Trigger |
|-------|------|---------|
| Tree view file/folder actions | `src/tree_view.py` | Right-click on tree item |
| Terminal copy/paste/clear | `src/terminal_view.py` | Right-click on terminal |
| AI chat tab rename/close/etc | `src/ai/ai_chat_tabs.py` | Right-click on AI chat tab |
| AI provider selection | `src/ai/ai_chat_tabs.py` | Provider selector button |

### Non-Popup GTK Components

Not floating popups — these are OS-native or framework widgets:

| Class / Usage | File | GTK Type | Why Not NvimPopup |
|---------------|------|----------|-------------------|
| **NotificationToast** | `src/popups/notification_toast.py` | `Gtk.Window` | ⚠️ Should migrate to NvimPopup (anchored, non-modal, auto-dismiss) |
| **SettingsDialog** | `src/popups/` | `Adw.PreferencesWindow` | ⚠️ Should migrate to NvimPopup |
| **GC Complete alert** | `src/shared/system_monitor.py` | `Gtk.AlertDialog` | ⚠️ Should migrate to NvimPopup |
| **File open/save/folder** | `src/zen_ide.py`, `src/editor/editor_view.py` | `Gtk.FileDialog` | ✅ OS-native file pickers — exception allowed |
| **App menu** (☰ button) | `src/zen_ide.py` | `Gtk.MenuButton` + `Gio.Menu` → `Gtk.PopoverMenu` | ✅ Standard GTK4 header bar menu — exception allowed |
| **AI terminal context menu** | `src/ai/ai_chat_terminal.py` | `Gtk.PopoverMenu` + `Gio.Menu` | ✅ GTK4 native popover menu — exception allowed |
