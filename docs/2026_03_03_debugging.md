# Debugging — Design Document

**Created_at:** 2026-03-03  
**Updated_at:** 2026-03-08  
**Status:** Planned  
**Goal:** Implement Debug Adapter Protocol (DAP) support for multi-language debugging  
**Scope:** `src/debug/`, Python/JavaScript/Go/Rust debugger adapters  

---

## Overview

Zen IDE debugging integration via the **Debug Adapter Protocol (DAP)** — the same open standard used by Neovim (nvim-dap), Emacs, and other modern editors. DAP decouples the IDE UI from language-specific debuggers, so one implementation unlocks debugging for Python, JavaScript, Go, Rust, and any language with a DAP adapter.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       Zen IDE                           │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Breakpoint   │  │  Debug Panel │  │ Editor Gutter │  │
│  │ Manager      │  │  (variables, │  │ (breakpoint   │  │
│  │              │  │   call stack, │  │  markers,     │  │
│  │              │  │   watches,    │  │  current line │  │
│  │              │  │   output)     │  │  highlight)   │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                 │                   │          │
│         └────────┬────────┘───────────────────┘          │
│                  │                                       │
│         ┌────────▼────────┐                              │
│         │   DAP Client    │    JSON messages over stdio  │
│         │  (dap_client.py)│◄────────────────────────┐    │
│         └────────┬────────┘                         │    │
│                  │                                  │    │
└──────────────────┼──────────────────────────────────┼────┘
                   │ subprocess (stdio)               │
          ┌────────▼────────────────────────────────────┐
          │            Debug Adapter                     │
          │  (debugpy, dlv dap, codelldb, js-debug)       │
          └────────┬─────────────────────────────────────┘
                   │
          ┌────────▼────────┐
          │   Debuggee      │
          │  (user program) │
          └─────────────────┘
```

### Why DAP?

| Approach | Pros | Cons |
|----------|------|------|
| **DAP (chosen)** | Multi-language, battle-tested protocol, reuse existing adapters | Moderate implementation effort |
| Direct subprocess/pdb | Simple, Python-only | Single language, brittle parsing |
| GDB/MI protocol | Powerful for C/C++/Rust | Not language-agnostic, complex |

DAP gives us Python debugging on day one (via `debugpy`) and a clear path to JavaScript, Go, Rust, C/C++ later — all through the same UI.

## Components

### 1. DAP Client (`src/debug/dap_client.py`)

The protocol layer. Communicates with debug adapters via JSON over stdio.

**Responsibilities:**
- Launch debug adapter as subprocess
- Send DAP requests (initialize, setBreakpoints, launch, continue, stepIn, etc.)
- Parse DAP responses and events
- Emit signals to UI components via callbacks

**Key classes:**

```python
class DAPClient:
    """Manages communication with a debug adapter subprocess."""

    def __init__(self, adapter_command: list[str], on_event: Callable):
        self._process: subprocess.Popen | None = None
        self._seq = 0
        self._pending: dict[int, Future] = {}
        self._on_event = on_event  # callback for DAP events

    # Lifecycle
    def start(self) -> None: ...       # Launch adapter subprocess
    def stop(self) -> None: ...        # Terminate adapter

    # DAP Requests
    def initialize(self) -> dict: ...
    def launch(self, program: str, **kwargs) -> dict: ...
    def attach(self, port: int) -> dict: ...
    def set_breakpoints(self, source: str, lines: list[int]) -> dict: ...
    def continue_(self, thread_id: int) -> dict: ...
    def next(self, thread_id: int) -> dict: ...       # Step over
    def step_in(self, thread_id: int) -> dict: ...
    def step_out(self, thread_id: int) -> dict: ...
    def pause(self, thread_id: int) -> dict: ...
    def disconnect(self) -> dict: ...

    # Inspection
    def stack_trace(self, thread_id: int) -> list[StackFrame]: ...
    def scopes(self, frame_id: int) -> list[Scope]: ...
    def variables(self, ref: int) -> list[Variable]: ...
    def evaluate(self, expression: str, frame_id: int) -> str: ...
```

**Transport protocol** — DAP uses HTTP-like headers over stdio:

```
Content-Length: 119\r\n
\r\n
{"seq":1,"type":"request","command":"initialize","arguments":{"adapterID":"python","clientID":"zen-ide",...}}
```

**Threading model:**
- Reader thread reads adapter stdout continuously, parses JSON messages
- Responses matched to pending requests by `seq` / `request_seq`
- Events dispatched to main GTK thread via `GLib.idle_add()`
- All UI updates happen on main thread (GTK requirement)

### 2. Debug Session Manager (`src/debug/debug_session.py`)

Orchestrates the debug lifecycle. Sits between UI and DAP client.

```python
class DebugSession:
    """Manages a single debug session lifecycle."""

    class State(Enum):
        IDLE = "idle"
        INITIALIZING = "initializing"
        RUNNING = "running"
        STOPPED = "stopped"       # Hit breakpoint / step completed
        TERMINATED = "terminated"

    def __init__(self, config: DebugConfig):
        self.state = State.IDLE
        self._client: DAPClient | None = None
        self._config = config
        self._threads: dict[int, ThreadInfo] = {}
        self._stopped_thread_id: int | None = None

    # Lifecycle
    def start(self) -> None: ...
    def stop(self) -> None: ...

    # Execution control
    def continue_(self) -> None: ...
    def step_over(self) -> None: ...
    def step_into(self) -> None: ...
    def step_out(self) -> None: ...
    def pause(self) -> None: ...
    def restart(self) -> None: ...

    # Inspection (fetches from adapter, caches)
    def get_call_stack(self) -> list[StackFrame]: ...
    def get_variables(self, scope: str) -> list[Variable]: ...
    def evaluate(self, expr: str) -> str: ...

    # DAP event handlers
    def _on_stopped(self, event: dict) -> None: ...
    def _on_terminated(self, event: dict) -> None: ...
    def _on_output(self, event: dict) -> None: ...
```

### 3. Breakpoint Manager (`src/debug/breakpoint_manager.py`)

Persistent breakpoint tracking, independent of debug sessions.

```python
class BreakpointManager:
    """Manages breakpoints across files. Persists to ~/.zen_ide/breakpoints.json."""

    def toggle(self, file_path: str, line: int) -> bool: ...
    def add(self, file_path: str, line: int, condition: str = "") -> Breakpoint: ...
    def remove(self, file_path: str, line: int) -> None: ...
    def get_for_file(self, file_path: str) -> list[Breakpoint]: ...
    def get_all(self) -> dict[str, list[Breakpoint]]: ...
    def clear_file(self, file_path: str) -> None: ...
    def clear_all(self) -> None: ...

    # Persistence
    def save(self) -> None: ...
    def load(self) -> None: ...

    # Change notification
    def subscribe(self, callback: Callable) -> None: ...
```

**Breakpoint types (phased):**

| Type | Phase | Description |
|------|-------|-------------|
| Line breakpoint | Phase 1 | Break at line N |
| Conditional breakpoint | Phase 2 | Break when expression is true |
| Logpoint | Phase 2 | Log message instead of breaking |
| Exception breakpoint | Phase 3 | Break on raised/uncaught exceptions |
| Function breakpoint | Phase 3 | Break when function is entered |

### 4. Debug Panel (`src/debug/debug_panel.py`)

Bottom panel UI showing debug state. Follows the `SplitPanelManager` registration pattern.

```
┌──────────────────────────────────────────────────────┐
│ ▶ Continue │ ⏭ Step Over │ ⏬ Step In │ ⏫ Step Out │ ⏹ Stop │ 🔄 Restart │
├──────────────────────┬───────────────────────────────┤
│ CALL STACK           │ VARIABLES                     │
│                      │                               │
│ ▸ main()     line 42 │ ▸ Locals                      │
│   foo()      line 17 │   x = 42                      │
│   bar()      line 8  │   name = "hello"              │
│                      │   items = [1, 2, 3]           │
│                      │ ▸ Globals                     │
│                      │   __name__ = "__main__"       │
├──────────────────────┼───────────────────────────────┤
│ BREAKPOINTS          │ DEBUG CONSOLE                 │
│                      │                               │
│ ● main.py:42         │ > print(x)                   │
│ ● utils.py:17        │ 42                            │
│ ○ test.py:8 (disabled│ > len(items)                  │
│                      │ 3                              │
└──────────────────────┴───────────────────────────────┘
```

**Sub-panels:**

| Panel | Content | Interaction |
|-------|---------|-------------|
| **Call Stack** | Stack frames with file:line | Click to navigate to frame |
| **Variables** | Expandable tree: locals, globals, closures | Expand objects, hover for type info |
| **Breakpoints** | All breakpoints with enable/disable toggles | Click to navigate, checkbox to toggle |
| **Debug Console** | Program output + REPL for evaluating expressions | Type expression, Enter to evaluate |

**Implementation pattern — lazy `@property` initialization:**

```python
# In ZenIDEWindow
@property
def debug_panel(self):
    if self._debug_panel is None:
        from debug.debug_panel import DebugPanel
        self._debug_panel = DebugPanel(self)
        self.split_panel_manager.register("debug", self._debug_panel, ...)
    return self._debug_panel
```

### 5. Breakpoint Gutter Renderer (`src/debug/breakpoint_renderer.py`)

Visual breakpoint markers in the editor gutter. Follows the `GutterDiffRenderer` pattern.

```python
class BreakpointRenderer:
    """Draws breakpoint markers and current-line highlight in the editor gutter."""

    def __init__(self, view: ZenSourceView, breakpoint_mgr: BreakpointManager):
        self._view = view
        self._breakpoint_mgr = breakpoint_mgr
        self._current_line: int | None = None  # execution pointer

    def draw(self, snapshot, cr):
        """Called from ZenSourceView.do_snapshot(). Draws:
        - Red circles for breakpoints
        - Yellow arrow for current execution line
        - Yellow background highlight on current line
        """
        ...

    def set_current_line(self, line: int | None):
        """Set/clear the current execution pointer."""
        self._current_line = line
        self._view.queue_draw()
```

**Click-to-toggle breakpoints:**

```python
# In ZenSourceView — add click handler on gutter area
def _on_gutter_click(self, gesture, n_press, x, y):
    """Toggle breakpoint when user clicks in the gutter area."""
    if x < GUTTER_BREAKPOINT_AREA_WIDTH:
        buffer = self.get_buffer()
        iter_at_y, _ = self.get_line_at_y(int(y))
        line = iter_at_y.get_line() + 1
        self._breakpoint_mgr.toggle(self._file_path, line)
```

### 6. Debug Configuration (`src/debug/debug_config.py`)

Launch configurations stored per-workspace in `.zen/launch.json`.

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal"
    },
    {
      "name": "Python: Attach",
      "type": "python",
      "request": "attach",
      "connect": { "host": "localhost", "port": 5678 }
    },
    {
      "name": "Node.js: Current File",
      "type": "node",
      "request": "launch",
      "program": "${file}"
    }
  ]
}
```

**Built-in adapter registry:**

| Language | Adapter | Command | Auto-detect |
|----------|---------|---------|-------------|
| Python | debugpy | `python -m debugpy --listen 0 --wait-for-client {program}` | `*.py` files |
| JavaScript/TypeScript | js-debug | `node js-debug-adapter` | `*.js`, `*.ts` |
| Go | Delve | `dlv dap` | `*.go`, `go.mod` present |
| Rust | CodeLLDB | `codelldb --port 0` | `*.rs`, `Cargo.toml` present |
| C/C++ | CodeLLDB / cppdbg | `codelldb --port 0` | `*.c`, `*.cpp`, `Makefile` |

**Zero-config mode:** When no `launch.json` exists, Zen auto-detects the language from the current file and generates a default configuration. User just presses F5.

## UI Integration

### Keybindings

| Action | macOS | Linux | Rationale |
|--------|-------|-------|-----------|
| Start/Continue debugging | `Cmd+F5` | `Ctrl+F5` | Standard across IDEs |
| Stop debugging | `Cmd+Shift+F5` | `Ctrl+Shift+F5` | Standard |
| Step Over | `F10` | `F10` | Universal debugger convention |
| Step Into | `F11` | `F11` | Universal |
| Step Out | `Shift+F11` | `Shift+F11` | Universal |
| Toggle Breakpoint | `F9` | `F9` | Universal |
| Toggle Debug Panel | `Cmd+Shift+Y` | `Ctrl+Shift+Y` | Standard convention |
| Debug Console focus | `Cmd+Shift+D` | `Ctrl+Shift+D` | — |

> **Conflict note:** `Cmd+Shift+D` is currently bound to Sketch Pad toggle. Reassign Sketch Pad to `Cmd+Shift+K` or use `Cmd+Shift+B` for debug panel instead.

### Editor Decorations

When a debug session is active and stopped at a breakpoint:

```
   1  │ def calculate(x, y):
   2  │     result = x + y
 ● 3  │     if result > 10:        ← breakpoint (red dot in gutter)
 → 4  │         print("big!")      ← current line (yellow arrow + highlight)
   5  │     return result
```

- **Red dot (●):** Breakpoint set at this line
- **Yellow arrow (→):** Current execution position
- **Line highlight:** Subtle yellow background on the current execution line
- **Grayed dot (○):** Disabled breakpoint

### Status Bar Integration

During active debug session, the status bar shows:

```
[🐛 Debugging: main.py] [Stopped at line 42] [Thread 1]
```

### Dev Pad Integration

Debug sessions are logged as activities:

```
🐛 Debug session started — main.py (Python)
⏸ Breakpoint hit — main.py:42
⏹ Debug session ended — 2m 34s
```

## File Structure

```
src/debug/
├── __init__.py
├── dap_client.py           # DAP protocol transport + message handling
├── debug_session.py         # Session lifecycle orchestration
├── debug_config.py          # Launch configuration loading + adapter registry
├── breakpoint_manager.py    # Breakpoint state + persistence
├── debug_panel.py           # Bottom panel UI (call stack, variables, console)
├── breakpoint_renderer.py   # Gutter overlay for breakpoint markers
└── debug_console.py         # REPL-style expression evaluator widget
```

## Implementation Phases

### Phase 1 — Foundation (MVP)

**Goal:** Debug a Python file with breakpoints, step through code, inspect variables.

| Task | Effort | Description |
|------|--------|-------------|
| DAP Client | 3 days | JSON/stdio transport, request/response/event handling |
| Debug Session Manager | 2 days | Lifecycle, state machine, thread management |
| Breakpoint Manager | 1 day | Toggle/persist breakpoints, change notifications |
| Breakpoint Gutter Renderer | 1 day | Red dots in gutter, click to toggle |
| Current Line Highlight | 0.5 days | Yellow arrow + line highlight during stopped state |
| Debug Panel (basic) | 2 days | Call stack + variables tree + toolbar |
| Keybindings | 0.5 days | F5, F9, F10, F11, Shift+F11 |
| Python adapter integration | 1 day | debugpy launch, zero-config for `*.py` |
| **Total Phase 1** | **~11 days** | |

**Phase 1 delivers:** Click gutter to set breakpoint → F5 to debug → steps through code → see variables and call stack.

### Phase 2 — Polish

| Task | Effort | Description |
|------|--------|-------------|
| Debug Console (REPL) | 2 days | Evaluate expressions while stopped |
| Conditional breakpoints | 1 day | Right-click breakpoint → add condition |
| Logpoints | 0.5 days | Log messages without stopping |
| `launch.json` support | 1.5 days | Load/save configurations, config picker |
| Hover variable inspection | 1 day | Hover over variable in editor → tooltip with value |
| Status bar integration | 0.5 days | Debug state in status bar |
| Dev Pad logging | 0.5 days | Log debug session activities |
| **Total Phase 2** | **~7 days** | |

### Phase 3 — Multi-language

| Task | Effort | Description |
|------|--------|-------------|
| Node.js/JavaScript adapter | 1 day | js-debug integration |
| Go adapter (Delve) | 1 day | `dlv dap` integration |
| Rust/C++ adapter (CodeLLDB) | 1 day | CodeLLDB integration |
| Exception breakpoints | 1 day | Break on caught/uncaught exceptions |
| Multi-thread debugging | 1.5 days | Thread picker, per-thread stepping |
| Watch expressions panel | 1 day | Persistent expression watches |
| **Total Phase 3** | **~6.5 days** | |

### Phase 4 — Advanced

| Task | Description |
|------|-------------|
| Remote debugging | Attach to remote processes (SSH tunnel) |
| Debug configurations UI | Visual editor for `launch.json` |
| Inline variable values | Show variable values inline after statements |
| Data breakpoints | Break when a variable's value changes |
| Disassembly view | Low-level view for C/C++/Rust |
| Performance profiling | Integrate with profiler adapters |

## Startup Impact

**Zero impact on startup.** All debug code is lazily loaded:

- No module-level imports of `src/debug/` anywhere in the startup path
- Debug panel created only on first F5 press or Cmd+Shift+Y
- `BreakpointRenderer` attached only when a file with breakpoints is opened
- DAP client subprocess spawned only when debugging starts

**Verification:** Run `make startup-time` before and after — numbers must not change.

## Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| (none for Phase 1) | DAP client is pure Python — just JSON over stdio | — |
| `debugpy` | Python debug adapter (user must install) | `pip install debugpy` |

The DAP client itself requires **no additional dependencies** — it's pure Python using `subprocess`, `json`, `threading`, and `socket` from the standard library. Debug adapters are external tools the user installs per-language.

## Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `launch.json` | Debug launch configs | `.zen/launch.json` in workspace root |
| `breakpoints.json` | Persisted breakpoints | `~/.zen_ide/breakpoints.json` |

## Open Questions

1. **Panel placement:** Bottom panel (alongside terminal) vs. right split panel (alongside editor)? Bottom panel is recommended since debugging needs horizontal space for variables + call stack side by side, and it mirrors the layout users are familiar with from other IDEs.

2. **Adapter installation:** Should Zen auto-install debug adapters (e.g., `pip install debugpy`) or require manual setup? Recommendation: prompt the user to install on first use, with a one-click install button.

3. **Legacy compatibility:** Should we support `.code-workspace` `launch.json` formats in addition to `.zen/launch.json`? Recommendation: yes, read as fallback for easier migration.

4. **Terminal integration:** Should debug output go to the debug console panel, the integrated terminal, or both? Recommendation: program stdout/stderr goes to Debug Console panel; allow `"console": "integratedTerminal"` option to redirect to the terminal instead.
