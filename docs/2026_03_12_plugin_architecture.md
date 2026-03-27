# Plugin Architecture

**Created_at:** 2026-03-12  
**Updated_at:** 2026-03-12  
**Status:** Planned  
**Goal:** Document the current Zen IDE extensibility architecture and propose a Python plugin system built on the existing provider and callback patterns  
**Scope:** `src/zen_ide.py`, `src/navigation/`, `src/ai/`, `src/editor/`, `src/main/`, `~/.zen_ide/`  

---

## Overview

This document captures the current architecture surfaces that are most relevant to extensibility, then proposes a Python plugin system that fits the IDE's existing provider, callback, and settings patterns.

## 1. Application Entry Point & Initialization

### Main Entry Point: `src/zen_ide.py`

**Key Class Hierarchy:**
```
ZenIDEApp (Gtk.Application)
  └─ ZenIDEWindow (Gtk.ApplicationWindow)
      ├─ WindowLayoutMixin
      ├─ WindowStateMixin
      ├─ WindowEventsMixin
      ├─ WindowActionsMixin
      ├─ WindowPanelsMixin
      └─ WindowFontsMixin
```

**Startup Flow:**
1. **Module Level** (Pre-GTK, <100ms):
   - Font registration via CoreText/fontconfig (async preload in thread)
   - GTK initialization & deprecation warning filters
   - Settings loading from `~/.zen_ide/settings.json`
   - Theme initialization
   - Workspace I/O preload (async thread - ~61ms saved)
   - AppKit preload on macOS (200ms, async)

2. **do_activate()** (Window Creation):
   - Preload heavy modules: `editor.editor_view`, `fonts`, `treeview`
   - Create `ZenIDEWindow`
   - Handle CLI arguments (files, workspace, directory)
   - Call `window.present()`

3. **_on_window_mapped()** (First Paint - Synchronized):
   - Create EditorView + Shortcuts + Fonts + Theme (critical path)
   - Create TreeView (replaces placeholder)
   - Setup focus tracking
   - Load workspace and restore files

4. **Post-First Paint** (Deferred):
   - Crash log recovery
   - Exit tracker installation
   - AI process cleanup

### User Directory Structure

**Location:** `~/.zen_ide/`

```
~/.zen_ide/
├── settings.json              # User preferences (persistent, atomic writes)
├── settings.json.bak          # Backup of last known good settings
├── dev_pad.json               # Dev Pad activity history
├── bash_history               # Terminal command history
├── aliases                    # Custom shell aliases (sourced in terminal)
├── crash_log.txt              # Python exception tracebacks
├── native_crash.log           # Native signal crash recovery
├── model_cache.json           # Cached AI model lists
├── font_cache.txt             # Cached Nerd Font detection
├── ai_pids/                   # AI process tracking (ephemeral)
│   └── <pid>.txt              # PID file per IDE instance
├── notes/                     # Dev Pad notes storage
│   └── <note_id>.md           # Individual markdown notes
└── themes/                    # Custom user themes (planned)
    └── *.json                 # JSON theme files
```

---

## 2. Key Architecture Components

### A. Editor System (`src/editor/`)

**Main Classes:**
- `EditorView` - Notebook-based multi-tab editor using GtkSourceView 5
- `SplitPanelManager` - Manages split panels (diff, binary viewer, etc.)
- `LanguageDetect` - Language detection from file extension/content

**Features:**
- GtkSourceView 5 with 25+ language syntax highlighting
- Tree-sitter semantic highlighting integration
- Autocomplete, find & replace, minimap, indent guides
- Format on save with per-language formatters
- Inline completions with AI ghost text

**Callbacks Available:**
```python
# Example from window_events.py
editor_view.on_file_selected = callback  # File opened
editor_view.connect("notify::current-page", callback)  # Tab switched
```

### B. File Explorer / Tree View (`src/treeview/`)

**Main Classes:**
- `TreeView` - Main file explorer with git integration
- `TreePanel` - GtkSnapshot-based custom renderer
- `TreeItem` - Individual file/folder nodes

**Features:**
- Custom GtkSnapshot rendering with Nerd Font icons
- Git status badges
- Drag & drop file operations
- Vim-style navigation (j/k)
- Multi-root workspace support

**Callbacks:**
```python
tree_view.on_file_selected = callback  # File clicked in tree
```

### C. Terminal (`src/terminal/`)

**Main Classes:**
- `TerminalView` - VTE-based terminal wrapper
- `TerminalShell` - Shell environment management
- `TerminalStack` - Multiple terminal tabs

**Features:**
- 256-color ANSI support
- File path linking
- Shell alias sourcing from `~/.zen_ide/aliases`
- Workspace folder picker
- Persistent command history in `~/.zen_ide/bash_history`

### D. AI Integration (`src/ai/`)

**Provider Pattern:**
```python
# Abstract base (if one exists conceptually):
class AIProvider:
    def start_session(self, prompt: str) -> Generator[str, None, None]
    def get_available_models(self) -> List[str]
```

**Concrete Providers:**
- `ClaudeCLIProvider` - Claude via @anthropic-ai/claude-code npm package
- `CopilotCLIProvider` - GitHub Copilot via gh CLI
- `PTYCLIProvider` - Base PTY wrapper for CLI execution

**Features:**
- Streaming responses with ANSI color
- Parallel AI chat sessions (tabs)
- Inline ghost text completions
- Model caching in `~/.zen_ide/model_cache.json`

### E. Navigation System (`src/navigation/`)

**Provider Pattern (EXISTS & EXTENSIBLE):**
```python
# src/navigation/navigation_provider.py
class NavigationProvider(ABC):
    @abstractmethod
    def supports_language(self, file_ext: str) -> bool:
        """Check if provider handles this file extension."""
    
    @abstractmethod
    def parse_imports(self, content: str, file_ext: str) -> Dict[str, str]:
        """Parse import statements → {alias: module_path} mapping."""
    
    @abstractmethod
    def find_symbol_in_content(self, content: str, symbol: str, file_ext: str) -> Optional[int]:
        """Return 1-based line number for symbol definition."""
```

**Concrete Implementations:**
- `CustomProvider` - Custom language-specific logic
- `TerraformProvider` - HCL/Terraform support

**Used by:**
- `CodeNavigation` class for Cmd+Click navigation
- Integrated into `editor_view.py`

---

## 3. Settings & Configuration System

### Settings Manager: `src/shared/settings/settings_manager.py`

**Key Features:**
1. **Atomic Writes**
   - Write to temp file → fsync → atomic rename
   - Prevents corruption on crash

2. **Automatic Backup**
   - Each write backs up to `settings.json.bak`
   - Can restore via `restore_from_backup()`

3. **Deep Merge**
   - User settings override defaults
   - Missing keys use defaults

4. **Path-Based Access**
   ```python
   from shared.settings import get_setting, set_setting
   
   font_size = get_setting("fonts.editor.size", 16)
   set_setting("theme", "zen_dark", persist=True)
   set_setting("editor.tab_size", 2, persist=False)  # Batch mode
   ```

5. **Batch Operations**
   ```python
   from shared.settings import save_layout, save_workspace
   
   save_layout({"main_splitter": 250, "bottom_splitter": 300})
   save_workspace(folders=["/path"], open_files=[...], last_file=...)
   ```

### Settings Categories

| Category | File Location | Example Keys |
|----------|--------------|--------------|
| Theme | `theme` | `theme: "zen_dark"` |
| Editor | `editor.*` | `tab_size`, `font_size`, `show_line_numbers` |
| Terminal | `terminal.*` | `scrollback_lines`, `shell` |
| Fonts | `fonts.*` | `editor.size`, `terminal.family` |
| AI | `ai.*` | `provider`, `show_inline_suggestions` |
| Keybindings | Not in settings.json | Hardcoded in `src/shared/settings/keybindings.py` |
| Formatters | `formatters.*` | `{".py": "black", ".js": "prettier"}` |
| Diagnostics | `diagnostics.*` | `{".py": "pylint", ".js": "eslint"}` |
| Navigation | `navigation.backend` | `"custom"` |
| Layout | `layout.*` | `window_width`, `main_splitter` |
| Workspace | `workspace.*` | `folders`, `open_files`, `last_file` |

---

## 4. Keybindings System

### File: `src/shared/settings/keybindings.py`

**Structure:**
```python
class KeyBindings:
    # Platform-aware modifier keys
    NEW_FILE = f"{_MOD}n"           # Cmd+N on macOS, Ctrl+N on Linux
    OPEN_FILE = f"{_MOD}o"
    SAVE_FILE = f"{_MOD}s"
    # ... 40+ bindings
    
    @classmethod
    def get_shortcut_categories(cls) -> list:
        """Returns structured shortcut data for display"""
        return [
            ("File Operations", [("New File", "Cmd+N"), ...]),
            ("Edit", [...]),
            ...
        ]
```

**Action Registration in `zen_ide.py`:**
```python
def _create_actions(self):
    self._action_mgr.create_actions({
        "new": self._on_new,
        "open": self._on_open,
        "save": self._on_save,
        # ... ~50 actions
    })

def _bind_shortcuts(self):
    self._action_mgr.bind_shortcuts({
        "new": [f"{mod}n"],
        "open": [f"{mod}o"],
        # ... each action gets list of accelerators
    })
```

**Action Manager: `src/main/action_manager.py`**
```python
class ActionManager:
    def create_actions(self, callbacks: dict[str, Callable]):
        """Create Gio.SimpleAction for each callback"""
    
    def bind_shortcuts(self, bindings: dict[str, list[str]]):
        """Bind keyboard shortcuts via set_accels_for_action()"""
```

---

## 5. Event & Signal System

### GTK Signals (Built-in)

The IDE uses GTK4's native signal system through `GObject.Object`:

```python
# Window mapping
self.connect("map", self._on_window_mapped)

# Close request
self.connect("close-request", self._on_close_request)

# Editor tab switching
notebook.connect("notify::page", self._on_editor_tab_switched)

# Tree focus
focus_ctrl = Gtk.EventControllerFocus()
focus_ctrl.connect("enter", lambda c: focus_mgr.set_focus("editor"))
```

### Custom Callbacks (Non-Signal Pattern)

The IDE uses **callback attributes** for cross-component communication:

```python
# Example: Tree → Window communication
tree_view.on_file_selected = window._on_tree_file_selected

# Example: Editor → Window communication
editor_view.on_file_opened = window._on_editor_file_opened

# Example: AI Chat → Window communication
ai_chat.on_response_update = window._on_ai_response_update
```

### Focus Manager (Centralized Event Hub)

**File:** `src/shared/focus_manager.py`

```python
from shared.focus_manager import get_focus_manager

focus_mgr = get_focus_manager()
focus_mgr.set_focus("editor")      # Set focus
current = focus_mgr.get_focus()    # Get current focus
focus_mgr.subscribe(callback)      # Listen for focus changes
```

This is a **singleton event bus** for focus-related events across the IDE.

---

## 6. Extensibility Patterns Found in Codebase

### A. Navigation Provider Pattern (PROVEN EXTENSIBLE)

**Location:** `src/navigation/`

This is the clearest existing plugin pattern:

```python
# Base class
class NavigationProvider(ABC):
    @abstractmethod
    def supports_language(self, file_ext: str) -> bool: ...
    
    @abstractmethod
    def parse_imports(self, content: str, file_ext: str) -> Dict[str, str]: ...
    
    @abstractmethod
    def find_symbol_in_content(self, content: str, symbol: str, file_ext: str) -> Optional[int]: ...
```

**Implementations:**
- `CustomProvider` - Tree-sitter-based navigation
- `TerraformProvider` - HCL-specific logic

**Usage:**
```python
# CodeNavigation class composes multiple providers
class CodeNavigation:
    def __init__(self, editor_view):
        self.providers = [
            CustomProvider(),
            TerraformProvider(),
        ]
```

### B. AI Provider Pattern (COULD BE FORMALIZED)

**Location:** `src/ai/`

Each AI provider has similar interface:
```python
class ClaudeCLIProvider:
    def start_session(self, prompt: str, cwd: str = None) -> Generator[str, None, None]:
        """Start streaming response"""
    
    def get_available_models(self) -> List[str]:
        """Return available models"""
    
    @staticmethod
    def is_available() -> bool:
        """Check if CLI is installed"""
```

### C. Formatter Registration (DECLARATIVE SETTINGS)

**Pattern:** Per-extension formatters in settings

```json
{
  "formatters": {
    ".py": "black --line-length 88",
    ".js": "prettier",
    ".go": "gofmt"
  }
}
```

**Usage:**
```python
# src/editor/format_manager.py
def format_file(file_path, content):
    ext = os.path.splitext(file_path)[1]
    formatter = settings.get(f"formatters.{ext}")
    if formatter:
        return subprocess.run(formatter, input=content)
```

### D. Diagnostic Linter Registration (SAME PATTERN)

```json
{
  "diagnostics": {
    ".py": ["pylint", "mypy"],
    ".js": "eslint"
  }
}
```

---

## 7. Proposed Python Plugin System Architecture

### Directory Structure for Plugins

```
~/.zen_ide/plugins/
├── manifest.json                # Plugin registry
├── enabled.json                 # Enabled plugins list
├── my_python_plugin/            # Individual plugin
│   ├── plugin.yaml              # Plugin metadata
│   ├── main.py                  # Entry point (required)
│   ├── requirements.txt          # Python deps (optional)
│   └── resources/               # Assets, icons, etc.
└── another_plugin/
    └── ...
```

### Plugin Manifest Structure

```yaml
# ~/.zen_ide/plugins/my_plugin/plugin.yaml
name: "My Code Generator"
version: "1.0.0"
author: "Your Name"
description: "Generate boilerplate code"
entry_point: "main.py"

# Register hooks
hooks:
  - type: "action"
    name: "generate_boilerplate"
    label: "Generate Boilerplate"
    keybinding: "Cmd+Shift+G"
    
  - type: "provider"
    interface: "NavigationProvider"  # Implement navigation
    
  - type: "formatter"
    for_extensions: [".my", ".custom"]
    
  - type: "settings_tab"
    label: "My Plugin Settings"

# Settings schema
settings:
  my_setting:
    type: "string"
    default: "value"
    description: "A configurable setting"
```

### Plugin Base Classes

```python
# src/plugins/plugin_base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, List

class ZenIDEPlugin(ABC):
    """Base class for all Zen IDE plugins."""
    
    def __init__(self, plugin_dir: str, ide_context: "IDEContext"):
        self.plugin_dir = plugin_dir
        self.ide = ide_context
        self.settings = {}
    
    @abstractmethod
    def activate(self) -> None:
        """Called when plugin is activated."""
        pass
    
    @abstractmethod
    def deactivate(self) -> None:
        """Called when plugin is deactivated."""
        pass
    
    def register_action(self, name: str, callback: Callable, 
                       label: str, keybinding: str = None) -> None:
        """Register a custom action (menu item + keybinding)."""
        self.ide.action_manager.register_action(name, callback, label)
        if keybinding:
            self.ide.action_manager.bind_shortcut(name, keybinding)
    
    def subscribe_event(self, event_type: str, callback: Callable) -> None:
        """Subscribe to IDE events."""
        self.ide.event_bus.subscribe(event_type, callback)
    
    def get_setting(self, key: str, default=None) -> Any:
        """Get plugin-specific setting."""
        return self.ide.settings.get(f"plugins.{self.name}.{key}", default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set plugin-specific setting."""
        self.ide.settings.set(f"plugins.{self.name}.{key}", value)

class NavigationProviderPlugin(ZenIDEPlugin):
    """Base for navigation provider plugins."""
    
    @abstractmethod
    def get_provider(self) -> "NavigationProvider":
        """Return NavigationProvider instance."""
        pass

class FormatterPlugin(ZenIDEPlugin):
    """Base for custom formatter plugins."""
    
    @abstractmethod
    def format(self, content: str, file_path: str) -> str:
        """Format code and return result."""
        pass

class LinterPlugin(ZenIDEPlugin):
    """Base for diagnostic/linter plugins."""
    
    @abstractmethod
    def lint(self, file_path: str) -> List["Diagnostic"]:
        """Run linter and return diagnostics."""
        pass
```

### IDE Context / Plugin API

```python
# src/plugins/ide_context.py

class IDEContext:
    """API exposed to plugins for IDE interaction."""
    
    def __init__(self, window: ZenIDEWindow):
        self.window = window
        self.editor = window.editor_view
        self.tree = window.tree_view
        self.terminal = window.terminal_view
        self.ai = window.ai_chat
        self.settings = window.settings_manager
        self.action_manager = window.action_manager
        self.event_bus = self._create_event_bus()
    
    def open_file(self, file_path: str) -> None:
        """Open a file in the editor."""
        self.editor.open_file(file_path)
    
    def get_current_file(self) -> str:
        """Get currently active file path."""
        return self.editor.get_current_file()
    
    def get_selection(self) -> str:
        """Get currently selected text."""
        return self.editor.get_selection()
    
    def insert_text(self, text: str) -> None:
        """Insert text at cursor."""
        self.editor.insert_text(text)
    
    def run_terminal_command(self, cmd: str) -> None:
        """Execute command in integrated terminal."""
        self.terminal.run_command(cmd)
    
    def show_notification(self, message: str, type: str = "info") -> None:
        """Show notification toast."""
        # Implementation TBD
        pass
    
    def show_dialog(self, title: str, message: str, buttons: List[str]) -> str:
        """Show modal dialog."""
        # Implementation TBD
        pass

# Event types that plugins can subscribe to
PLUGIN_EVENTS = {
    "file_opened": {"file_path": str},
    "file_closed": {"file_path": str},
    "file_saved": {"file_path": str},
    "file_modified": {"file_path": str},
    "editor_focus": {},
    "terminal_focus": {},
    "text_selected": {"text": str},
    "format_requested": {"file_path": str},
    "lint_requested": {"file_path": str},
}
```

### Plugin Manager

```python
# src/plugins/plugin_manager.py

class PluginManager:
    """Manages plugin lifecycle."""
    
    def __init__(self, ide_context: IDEContext, plugin_dir: str):
        self.ide = ide_context
        self.plugin_dir = plugin_dir
        self.plugins: Dict[str, ZenIDEPlugin] = {}
        self.enabled_plugins: Set[str] = set()
    
    def load_plugins(self) -> None:
        """Discover and load plugins from ~/.zen_ide/plugins/"""
        enabled = self._load_enabled_list()
        
        for plugin_name in os.listdir(self.plugin_dir):
            if plugin_name.startswith("_"):
                continue
            
            plugin_path = os.path.join(self.plugin_dir, plugin_name)
            if not os.path.isdir(plugin_path):
                continue
            
            try:
                manifest = self._load_manifest(plugin_path)
                plugin = self._import_plugin(plugin_path, manifest)
                self.plugins[plugin_name] = plugin
                
                if plugin_name in enabled:
                    plugin.activate()
                    self.enabled_plugins.add(plugin_name)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
    
    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin."""
        if name not in self.plugins:
            return False
        self.plugins[name].activate()
        self.enabled_plugins.add(name)
        self._save_enabled_list()
        return True
    
    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin."""
        if name not in self.plugins:
            return False
        self.plugins[name].deactivate()
        self.enabled_plugins.discard(name)
        self._save_enabled_list()
        return True
    
    def _load_manifest(self, plugin_path: str) -> Dict:
        """Load plugin.yaml manifest."""
        import yaml
        with open(os.path.join(plugin_path, "plugin.yaml")) as f:
            return yaml.safe_load(f)
    
    def _import_plugin(self, plugin_path: str, manifest: Dict) -> ZenIDEPlugin:
        """Dynamically import plugin module."""
        import sys, importlib.util
        
        entry_point = manifest.get("entry_point", "main.py")
        module_path = os.path.join(plugin_path, entry_point)
        
        spec = importlib.util.spec_from_file_location("plugin_module", module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"plugin_{id(module)}"] = module
        spec.loader.exec_module(module)
        
        # Find ZenIDEPlugin subclass
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, ZenIDEPlugin) and obj != ZenIDEPlugin:
                return obj(plugin_path, self.ide)
        
        raise ValueError(f"No ZenIDEPlugin subclass found in {entry_point}")
```

### Example Plugin Implementation

```python
# ~/.zen_ide/plugins/example_generator/main.py

import os
from src.plugins.plugin_base import ZenIDEPlugin

class ExampleGeneratorPlugin(ZenIDEPlugin):
    """Plugin that generates example code."""
    
    def activate(self) -> None:
        """Setup plugin."""
        # Register action with keybinding
        self.register_action(
            name="generate_example",
            callback=self._on_generate,
            label="Generate Example Code",
            keybinding="Cmd+Shift+G"
        )
        
        # Subscribe to events
        self.subscribe_event("file_opened", self._on_file_opened)
        self.subscribe_event("text_selected", self._on_text_selected)
        
        print("Example Generator Plugin activated!")
    
    def deactivate(self) -> None:
        """Cleanup plugin."""
        print("Example Generator Plugin deactivated!")
    
    def _on_generate(self, action, param) -> None:
        """Generate example code."""
        file_path = self.ide.get_current_file()
        if not file_path:
            self.ide.show_notification("No file open", "error")
            return
        
        # Generate content based on file type
        example = self._generate_example(file_path)
        self.ide.insert_text(example)
    
    def _on_file_opened(self, event) -> None:
        """Called when file is opened."""
        file_path = event.get("file_path")
        print(f"File opened: {file_path}")
    
    def _on_text_selected(self, event) -> None:
        """Called when text is selected."""
        selected = event.get("text")
        print(f"Selected: {selected}")
    
    def _generate_example(self, file_path: str) -> str:
        """Generate example based on file extension."""
        _, ext = os.path.splitext(file_path)
        
        examples = {
            ".py": 'def hello_world():\n    print("Hello, World!")\n',
            ".js": 'function helloWorld() {\n  console.log("Hello, World!");\n}\n',
            ".go": 'func HelloWorld() {\n  fmt.Println("Hello, World!")\n}\n',
        }
        
        return examples.get(ext, "// No example for this file type")
```

---

## 8. Implementation Roadmap for Plugin System

### Phase 1: Foundation
- [ ] Create `src/plugins/` module structure
- [ ] Implement `ZenIDEPlugin` base class
- [ ] Implement `IDEContext` API wrapper
- [ ] Create `PluginManager` class
- [ ] Add plugin directory to `~/.zen_ide/plugins/`

### Phase 2: Integration
- [ ] Expose `IDEContext` from `ZenIDEWindow`
- [ ] Initialize `PluginManager` in `do_activate()`
- [ ] Register plugins in action/keybinding system
- [ ] Add "Plugins" menu to menu bar

### Phase 3: Management UI
- [ ] Plugin settings dialog (show enabled/disabled)
- [ ] Per-plugin configuration UI
- [ ] Plugin install/uninstall buttons

### Phase 4: Specialized Plugins
- [ ] Formalize `NavigationProviderPlugin` interface
- [ ] Formalize `FormatterPlugin` interface
- [ ] Formalize `LinterPlugin` interface
- [ ] Create example plugins for each type

---

## 9. Key Design Decisions

### Why This Approach?

1. **Callback-Based** (Not Signal-Based)
   - Simple, explicit
   - No GObject overhead
   - Familiar to Python devs

2. **Directory-Based** (Not Manifest-Based)
   - One manifest per plugin (minimal friction)
   - Can be YAML or JSON
   - Easy to version control

3. **Singleton IDEContext**
   - Plugins don't need to search for IDE references
   - Provides unified API
   - Can evolve without breaking plugins

4. **Explicit activate()/deactivate()**
   - Clear lifecycle
   - Easier to debug
   - Can do cleanup on deactivate

### Security Considerations

- Plugins run in same process as IDE (performance)
- No sandboxing (could add in future with subprocess)
- Plugin requirements.txt installed in venv (not isolated)
- Plugins can access full IDE state (by design)

---

## 10. Existing Extensibility Already in the IDE

| Feature | Location | How to Extend |
|---------|----------|---------------|
| **Navigation** | `src/navigation/` | Subclass `NavigationProvider` |
| **Formatters** | `src/editor/format_manager.py` | Add to `formatters` in settings |
| **Linters** | `src/shared/diagnostics_manager.py` | Add to `diagnostics` in settings |
| **Themes** | `src/themes/` | Add JSON to `~/.zen_ide/themes/` (planned) |
| **Terminal Aliases** | `src/terminal/terminal_shell.py` | Create `~/.zen_ide/aliases` file |
| **Keybindings** | `src/shared/settings/keybindings.py` | Hardcoded (would need refactor) |
| **AI Providers** | `src/ai/` | Subclass `PTYCLIProvider` or create new |
| **Actions** | `src/main/action_manager.py` | Call `app.add_action()` (private currently) |

