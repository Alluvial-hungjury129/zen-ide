# Zen IDE Inline Completion System — Comprehensive Documentation

**Created_at:** 2026-03-10  
**Updated_at:** 2026-03-12  
**Status:** Active  
**Goal:** Provide a comprehensive reference for the inline completion system lifecycle, architecture, behavior, and integration points.  
**Scope:** `src/editor/inline_completion/`, `src/ai/`, `tests/editor/inline_completion/`  

---

**Last Updated:** 2026-03-09 | **Status:** Current Implementation

---

## Executive Summary

The Zen IDE inline completion (ghost text / autosuggestion) system provides AI-powered code suggestions displayed as dimmed, italic text at the cursor position. It's built on a modular architecture: **EditorTab → InlineCompletionManager → ContextGatherer + Provider → GhostTextRenderer → GTK4 Snapshot**.

**Key Features:**
- ✅ Adaptive debouncing (250–800ms based on typing speed)
- ✅ FIM-style (Fill-in-Middle) prompting optimized for code completion
- ✅ Direct Copilot HTTP API (~1s) with graceful fallback
- ✅ Cross-file context gathering (open tabs, imports)
- ✅ LRU response caching (50 entries)
- ✅ Streaming token display (progressive ghost text)
- ✅ Multi-suggestion cycling (Alt+]/Alt+[)
- ✅ Sophisticated edge-case filtering (trailing whitespace detection)
- ✅ Multi-line suggestion support with custom positioning
- ✅ Full undo/redo preservation (ghost text never touches buffer until accepted)

---

## 1. COMPLETE FILE MANIFEST

### Core Inline Completion Files

| File | Purpose | Lines |
|------|---------|-------|
| `src/editor/inline_completion/inline_completion_manager.py` | Main coordinator: debouncing, keystroke handling, lifecycle management | 322 |
| `src/editor/inline_completion/inline_completion_provider.py` | AI request handler: prompt building, response cleaning, caching, FIM/chat fallback | 434 |
| `src/editor/inline_completion/ghost_text_renderer.py` | GTK4 visual overlay: rendering, accept/dismiss, streaming append | 271 |
| `src/editor/inline_completion/context_gatherer.py` | Context extraction: prefix/suffix gathering, cross-file imports, open tabs | 203 |
| `src/editor/inline_completion/copilot_api.py` | HTTP client: authentication, FIM endpoint, streaming, session token management | 358 |
| `src/editor/inline_completion/__init__.py` | Package exports | 6 |

### Integration Points

| File | Integration Type |
|------|------------------|
| `src/editor/editor_view.py` (EditorTab class) | Initialization, key press handling, snapshot rendering, destroy |
| `src/shared/settings/default_settings.py` | Configuration: enable/disable, trigger delay, model selection |
| `tests/editor/inline_completion/test_inline_completion_manager.py` | Unit tests for manager |
| `tests/editor/inline_completion/test_inline_completion_provider.py` | Unit tests for provider |

---

## 2. COMPLETE LIFECYCLE: TRIGGER → RENDER → ACCEPT

### 2.1 Triggering (What causes a completion request)

```
User types a character
    ↓
EditorTab._on_key_pressed() called
    ↓
InlineCompletionManager._on_buffer_changed() fired
    ↓
Check if enabled (ai.is_enabled AND ai.show_inline_suggestions)
    ↓
Clear any existing ghost text immediately
    ↓
Record keystroke for adaptive debouncing
    ↓
Schedule timer (GLib.timeout_add) with adaptive delay
    ↓ (after 250–800ms of no more typing)
InlineCompletionManager._trigger_completion()
```

**Filtering/Skip Conditions (before API call):**
- ❌ Autocomplete popup is visible
- ❌ Inline suggestions disabled in settings
- ❌ Prefix line is empty (nothing typed)
- ❌ Line ends with trailing whitespace after a "complete" character (e.g., `return True `)
  - Exception: Allow if line ends with continuation operators: `=([{,.:+-*/%\|&<>!^~@#`
  - This prevents hallucinated suggestions after finished statements

### 2.2 Context Gathering

**`gather_context(editor_tab)` → `CompletionContext`**

```
File: src/editor/inline_completion/context_gatherer.py

CompletionContext:
  prefix: str              # Last 3000 chars before cursor
  suffix: str              # First 1500 chars after cursor
  file_path: str           # Current file path
  language: str            # Language ID (e.g., "python", "javascript")
  cursor_line: int         # 1-indexed line number
  cursor_col: int          # Column offset
  related_snippets: list   # Cross-file context (up to 10)

Related Snippets gathered from:
  1. Open tabs (first 300 chars of each non-current tab)
  2. Import statements in current file (first 200 chars each)
  3. Attempts relative path resolution (module.py, module/__init__.py)
```

**Cross-File Context Strategy:**
- Parses Python `import` and `from X import Y` statements
- Resolves relative paths: `models.user` → `src/models/user.py`
- Falls back gracefully if imports can't be resolved
- Caps at 10 related snippets total

### 2.3 Provider Request (Multi-Stage Pipeline)

**`InlineCompletionProvider.request_completion()` → Background Thread**

```python
Thread Flow:
  1. Check cache (LRU by context hash)
     → HIT: return cached result immediately via GLib.idle_add()
     → MISS: proceed to API

  2. Try FIM Endpoint (Fast, ~1s)
     - CopilotAPI.complete_fim(prefix, suffix, language, file_path)
     - Parameters: max_tokens=150, temperature=0, stop=["\n\n"]
     - URL: https://api.githubcopilot.com/v1/completions
     - Custom headers: X-Copilot-Language, X-Copilot-Filename
     - Returns raw code (no markdown)

  3. Fallback to Chat Endpoint (Flexible, ~2-3s)
     - CopilotAPI.complete() or complete_stream()
     - Sends FIM-style prompt via chat API
     - System prompt instructs "raw code only"
     - Supports streaming (on_chunk callbacks)

  4. Cache the result (LRU, max 50 entries)
     - Key: MD5(last 200 chars of prefix + first 100 of suffix + language)
     - Tolerates edits far from cursor

  5. Return to Main Thread via GLib.idle_add()
     - on_result(completion_text)
     - on_chunk(token) called progressively if streaming
```

**API Authentication (copilot_api.py):**
```
1. Read OAuth token from ~/.config/github-copilot/apps.json
2. Exchange for session token via https://api.github.com/copilot_internal/v2/token
3. Session token cached with 60s refresh margin
4. All requests include Bearer token in Authorization header
```

### 2.4 Response Processing

**Cleaning Pipeline (Provider → Renderer):**

```python
Raw API Response
    ↓
_clean_response():
  - Strip leading/trailing whitespace
  - Remove markdown code fences (```python ... ```)
  - Remove FIM cursor marker (█) if echoed back
  - Reject prose responses (heuristic: natural language detection)
    ↓
_deduplicate():
  - Strip leading lines that already exist in prefix
  - Strip trailing lines that already exist in suffix
  - Prevents garbled output after acceptance
    ↓
_is_prose_response():
  - Check for prose indicators (e.g., "well-structured", "i suggest")
  - Analyze word length and space ratios on first line
    ↓
Cleaned Completion Text
```

### 2.5 Ghost Text Rendering

**`GhostTextRenderer.show(text)` → Visual Overlay**

```
Storage (no buffer modification):
  _ghost_text: str          # The suggestion text
  _cursor_offset: int       # Position where inserted (buffer offset)
  _active: bool             # Whether visible
  _inserting: bool          # Guard flag during accept (prevent re-entrant buffer-changed)

Rendering (in EditorTab.do_snapshot()):
  1. Get cursor position in window coordinates
  2. Split ghost text by newlines
  3. For each line:
     - First line: render at cursor position
     - Subsequent lines: render at left margin of next lines
  4. Layout with pango (italic, 55% alpha, theme's fg_dim color)
  5. Translate and append to snapshot

Styling:
  - Color: theme.fg_dim (typically ~60% brightness)
  - Alpha: 0.55 (55% opacity)
  - Font: italic variant of current font
```

### 2.6 Keystroke Handling (When Ghost Text is Visible)

**`InlineCompletionManager.handle_key(keyval, state)` → Action**

| Keybinding | Action | Implementation |
|------------|--------|----------------|
| `Tab` | Accept full suggestion | `accept()` → buffer insert via `begin_user_action()` |
| `Escape` | Dismiss ghost text | `dismiss()` → clear visual state |
| `Cmd+Right` (macOS) / `Ctrl+Right` | Accept next word | `accept_word()` → find next word boundary, insert |
| `Cmd+Down` (macOS) / `Ctrl+Down` | Accept next line | `accept_line()` → insert until first newline |
| `Alt+]` | Cycle to next suggestion | `cycle_next()` → show next in `_suggestions` list |
| `Alt+[` | Cycle to previous suggestion | `cycle_prev()` → show previous in `_suggestions` list |
| `Alt+\` (from key handler) | Manual trigger | `trigger_now()` → bypass debounce, request immediately |
| Any other key | Dismiss and process normally | `dismiss()` → return False to allow normal key handling |

### 2.7 Accepting/Dismissing

**Accept Flow:**
```python
GhostTextRenderer.accept():
  1. Get ghost text and stored cursor offset
  2. Clear visual state immediately
  3. Begin GTK user action (preserves undo/redo)
  4. Insert text into buffer at stored offset
  5. Move cursor to end of inserted text
  6. End user action
  7. Queue redraw
  → Result: Undo stack has one entry "Accept suggestion"

GhostTextRenderer.accept_word():
  1. Find next word boundary in ghost text
  2. Insert just that word (same user_action wrapping)
  3. Keep remaining ghost text visible (with updated cursor offset)

GhostTextRenderer.accept_line():
  1. Find first newline in ghost text
  2. Insert up to and including that newline
  3. Keep remaining ghost text visible

Dismiss Flow:
GhostTextRenderer.clear():
  1. Set _active = False
  2. Clear _ghost_text
  3. Queue redraw
  → No buffer modifications, no undo entry
```

---

## 3. PROVIDER ARCHITECTURE

### 3.1 CopilotAPI (HTTP Direct Client)

**File:** `src/editor/inline_completion/copilot_api.py`

**Endpoints:**
- **FIM (Fill-in-Middle):** `https://api.githubcopilot.com/v1/completions` (fastest)
- **Chat:** `https://api.githubcopilot.com/chat/completions` (flexible)

**Methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `complete_fim(prefix, suffix, language, file_path, max_tokens, timeout)` | FIM endpoint request (raw code) | `str \| None` |
| `complete(prompt, model, max_tokens, timeout)` | Chat endpoint request (non-streaming) | `str \| None` |
| `complete_stream(prompt, model, max_tokens, timeout, on_chunk, on_done)` | Chat endpoint with SSE streaming | `str \| None` (assembled text) |
| `is_available()` | Check if Copilot credentials exist | `bool` |

**FIM vs Chat:**
- **FIM** (preferred): Designed for inline completion, no markdown wrapping, faster
- **Chat** (fallback): More flexible, supports streaming, requires post-processing

### 3.2 InlineCompletionProvider (Orchestrator)

**File:** `src/editor/inline_completion/inline_completion_provider.py`

**Logic:**
```
1. Cache check (LRU by context)
2. Try FIM endpoint (if available)
   └─ If successful, cache and return
   └─ If failed, continue
3. Try Chat endpoint
   └─ Optional: use streaming (on_chunk callbacks)
   └─ Clean response (remove markdown, prose filter)
   └─ Deduplicate against prefix/suffix
   └─ Cache and return
4. No fallback (API-only mode, no CLI)
5. Error → on_error callback on main thread
```

**Stop Conditions:**
- User continues typing before response arrives → `_stop_requested = True`
- Cancellation via `cancel()` method
- Prevents race conditions where old completions overwrite new ones

### 3.3 Fallback Strategy (No CLI)

Unlike earlier versions, **no Copilot CLI or Claude CLI fallback** is implemented. The provider is:
- ✅ Fast (direct HTTP, no Node.js startup)
- ✅ Resilient (tries both FIM and chat endpoints)
- ❌ Degraded when API is down (no fallback)

---

## 4. DEBOUNCING & THROTTLING

### 4.1 Adaptive Debounce Implementation

**Class:** `AdaptiveDebounce` in `inline_completion_manager.py`

```python
class AdaptiveDebounce:
  def __init__(self, min_ms=250, max_ms=800, window_size=5):
    self._min_ms = 250     # Shortest delay (user is thinking)
    self._max_ms = 800     # Longest delay (user is typing fast)
    self._window = 5       # Number of recent keystrokes to track
    self._timestamps: list[float] = []

  def record_keystroke():
    # Track 5 most recent keystroke times

  def get_delay_ms() -> int:
    # Calculate average inter-keystroke interval
    # Fast typing (<100ms avg) → longer delay (800ms)
    # Slow typing (>500ms avg) → shorter delay (250ms)
    # Linear interpolation between
```

**Example:**
```
User types fast: a, b, c (each 50ms apart)
  → avg interval = 50ms
  → delay = 800ms (wait for user to pause)

User types slowly: x [1000ms pause] y [1000ms pause] z
  → avg interval = 1000ms
  → delay = 250ms (user is deliberate, respond quickly)
```

### 4.2 Trigger Mechanics

**GLib Timer Integration (main thread):**
```python
_on_buffer_changed():
  # Called on every keystroke
  self._debounce.record_keystroke()
  self._cancel_pending()  # Clear previous timer
  delay = self._debounce.get_delay_ms()
  self._trigger_timer_id = GLib.timeout_add(delay, self._trigger_completion)

_trigger_completion():
  # Called after debounce expires
  # Returns False to prevent GLib from repeating
```

**Default Delay:** 200ms (from settings: `ai.inline_completion.trigger_delay_ms`)

---

## 5. GHOST TEXT RENDERING & DISPLAY

### 5.1 Visual Styling

```python
Color:      theme.fg_dim          # ~60% brightness, theme-aware
Alpha:      0.55                  # 55% opacity (semi-transparent)
Font:       Italic variant        # Italic version of editor font
Positioning: First line at cursor  # Subsequent lines at left margin
```

### 5.2 Rendering Pipeline (GtkSnapshot)

**Location:** `EditorTab.view.do_snapshot()` → `GhostTextRenderer.draw(snapshot)`

```
do_snapshot():
  1. Call parent GtkSource.View.do_snapshot() → render normal text
  2. Draw indent guides
  3. Draw gutter diff indicators
  4. Draw color preview swatches
  5. Draw ghost text overlay ← HERE
  6. Draw custom block cursor (if enabled)

GhostTextRenderer.draw(snapshot):
  1. Get cursor iter from stored _cursor_offset
  2. Get cursor position via get_iter_location()
  3. Convert to window coordinates via buffer_to_window_coords()
  4. For each line in ghost text:
     - Create Pango.Layout with text
     - Set font to italic
     - Calculate position (first line = cursor, rest = left margin)
     - snapshot.translate() and snapshot.append_layout()
  5. Restore snapshot state
```

### 5.3 Multi-Line Handling

Ghost text correctly handles multi-line suggestions:
```
Cursor at (col 15):

def hello(name█
         world=None
         ):
    pass

Ghost text: "\n    world=None\n    ):"

Rendering:
  Line 0: "█" position stays at cursor (col 15)
  Line 1: "    world=None" at left margin (col 0) of next line
  Line 2: "    ):" at left margin (col 0) of next line
```

---

## 6. KEY BINDINGS & USER CONTROL

### 6.1 Available Keybindings

**Programmed in:** `src/editor/editor_view.py` EditorTab._on_key_pressed()

| Binding | Action | Context | Scope |
|---------|--------|---------|-------|
| `Tab` | Accept all | Ghost text visible | Local |
| `Cmd+Right` (macOS) / `Ctrl+Right` | Accept word | Ghost text visible | Local |
| `Cmd+Down` (macOS) / `Ctrl+Down` | Accept line | Ghost text visible | Local |
| `Escape` | Dismiss | Ghost text visible | Local |
| `Alt+]` | Cycle next | Ghost text visible, >1 suggestion | Local |
| `Alt+[` | Cycle previous | Ghost text visible, >1 suggestion | Local |
| `Alt+\` | Manual trigger | Anytime | Keyboard handler |

### 6.2 Key Handler Flow

```python
_on_key_pressed(keyval, state):
  1. If ghost text active and consumed by handle_key() → return True (prevent normal handling)
  2. Lazy init InlineCompletionManager on first keypress
  3. If autocomplete visible → delegate to autocomplete
  4. ... other handlers ...
```

---

## 7. SETTINGS & CONFIGURATION

### 7.1 AI Settings Structure

**File:** `src/shared/settings/default_settings.py`

```python
"ai": {
  "is_enabled": True,                    # Master toggle (AI chat + inline)
  "provider": "",                        # "" (auto-detect), "copilot", "claude_cli"
  "show_inline_suggestions": True,       # Enable ghost text
  "model": {
    "copilot": "claude-opus-4.5",       # For chat (not inline)
    "claude_cli": "sonnet"
  },
  "inline_completion": {
    "trigger_delay_ms": 200,            # Base debounce (overridden by adaptive debounce)
    "model": "gpt-4.1"                  # Model for inline completions
  }
}
```

### 7.2 Settings Usage

| Setting | Used By | Effect |
|---------|---------|--------|
| `ai.is_enabled` | InlineCompletionManager.is_enabled() | Disables all inline completions if False |
| `ai.show_inline_suggestions` | InlineCompletionManager.is_enabled() | Disables ghost text if False |
| `ai.inline_completion.model` | InlineCompletionProvider._run() | Which AI model to use for chat endpoint |

**Settings are checked at trigger time, not cached** → Dynamic enabling/disabling works without restart.

---

## 8. CONTEXT GATHERING DETAILS

### 8.1 What Data is Sent to AI

**Per CompletionContext:**

```
prefix (str)
  ├─ Last 3000 characters before cursor
  └─ Typically function/class signature + surrounding code
  
suffix (str)
  ├─ First 1500 characters after cursor
  └─ Next function/block to guide suggestion
  
file_path (str)
  └─ For context (filename in prompt)
  
language (str)
  └─ "python", "javascript", "rust", etc. — normalized (python3 → python)
  
cursor_line (int)
  └─ 1-indexed line number (informational)
  
cursor_col (int)
  └─ Column offset in current line
  
related_snippets (list[RelatedSnippet])
  ├─ file_path (str)
  ├─ content (str) — first 200-300 chars of related file
  └─ relevance (str) — "open_tab" | "import" | "same_dir"
```

### 8.2 Related File Gathering Logic

**`_gather_cross_file_context(editor_tab, current_file)`**

```
Priority Order:
  1. Open Tabs
     - Get all open editor tabs from window._editor_view.tabs
     - Extract first 300 chars from each (signatures, class definitions)
     - Relevance: "open_tab"

  2. Import Statements
     - Parse current file with regex: from X import Y / import X
     - Resolve to file paths: models.user → src/models/user.py
     - Try both .py files and __init__.py in packages
     - Read first 200 chars of each resolved file
     - Relevance: "import"

  3. Same-directory siblings (future optimization, not implemented)

Constraints:
  - Max 10 related snippets total
  - Max 300 chars per snippet (open tabs)
  - Max 200 chars per snippet (imports)
  - Non-existent imports silently skipped
```

### 8.3 FIM-Style Prompt Format

**`_build_prompt(context) → str`**

```
# Related files:
# --- models.py (import) ---
class User:
    def __init__(self, name: str): ...

# --- auth_routes.py (open_tab) ---
@app.post("/login")
def login(credentials):

# File: services/auth_service.py
```python
from models import User

def authenticate(credentials):
    █
    return user
```
```

**Key Design:**
- No English instructions in prompt (handled by system message)
- Raw code visibility to model
- FIM cursor marker (█) at completion point
- Language tag (python, javascript) for code-aware formatting
- System prompt instructs: "raw code only, no markdown, no explanation"

---

## 9. CACHING IMPLEMENTATION

### 9.1 LRU Cache Design

**Class:** `CompletionCache` in `inline_completion_provider.py`

```python
class CompletionCache:
  def __init__(self, max_size: int = 50):
    self._cache: OrderedDict[str, list[str]] = OrderedDict()
    self._max_size = 50  # Max entries

  def get(context) -> list[str] | None:
    key = _make_key(context)
    if key in cache:
      move_to_end(key)  # Mark as recently used
      return cached completions

  def put(context, completions):
    cache[key] = completions
    if len(cache) > max_size:
      pop least-recently-used item

  def _make_key(context) -> str:
    # Hash of last 200 chars of prefix + first 100 of suffix + language
    # Tolerates edits far from cursor
    return hashlib.md5(...)
```

### 9.2 Cache Hit Conditions

**Cache HIT if:**
- User makes trivial edit (whitespace, comment) far from active completion context
- User navigates back to same code position
- Prefix/suffix context near cursor matches within 200/100 char window

**Cache MISS if:**
- New file
- Significant change near cursor
- Different language/file

### 9.3 Cache Performance

- **Hit:** ~0ms (instant display)
- **Miss:** ~1s (FIM API) or ~2-3s (chat fallback)
- **Eviction:** LRU when 50 entries exceeded

---

## 10. EDGE CASES & SPECIAL HANDLING

### 10.1 Trailing Whitespace Detection

**Problem:** Chat models often hallucinate when line ends with trailing space after a "finished" statement.

**Solution:** Smart heuristic in `_trigger_completion()`:

```python
if prefix_line and prefix_line[-1] in (" ", "\t"):
    rstripped = prefix_line.rstrip()
    if rstripped:
        last_char = rstripped[-1]
        # CONTINUATION_CHARS = "=([{,.:+-*/%\|&<>!^~@#"
        if last_char not in CONTINUATION_CHARS:
            # Skip — line looks complete (e.g. "return True ")
            return False

# Allow if line ends with operators that expect more code:
#   "x = "     ✅ (assignment, expects value)
#   "if ("     ✅ (conditional, expects condition)
#   "items."   ✅ (method call, expects method name)
#   "return True "  ❌ (statement complete, skip)
```

### 10.2 Autocomplete Popup Coexistence

**Conflict:** Both inline completion and autocomplete use same editor view.

**Solution:**
```python
# Check visible BEFORE requesting
if self._tab._autocomplete.is_visible():
    return False  # Don't request if autocomplete is showing

# Check visible BEFORE displaying
if self._tab._autocomplete.is_visible():
    return  # Don't show ghost text
```

### 10.3 Multi-Line Suggestion Handling

**Accepted multi-line suggestion:**
```
Original buffer:
  def hello(name█
      pass

Accept suggestion: "\n    greeting = f'Hi {name}'\n    return greeting"

Result (after accept):
  def hello(name
      greeting = f'Hi {name}'
      return greeting
      pass
```

**Ghost text rendering:**
- First line rendered at cursor
- Subsequent lines at left margin (0 column)
- Proper line-height spacing between lines

### 10.4 Undo/Redo Preservation

**Design:** Ghost text is NEVER in the buffer until accepted.

```python
# Ghost text is stored in GhostTextRenderer._ghost_text
# Buffer is untouched during display

# When accepted:
buffer.begin_user_action()
  buffer.insert(cursor_offset, ghost_text)
buffer.end_user_action()

# GTK groups this as one undo entry
# User can press Cmd+Z to undo the acceptance
```

### 10.5 Concurrent Request Cancellation

**Flow:**
```
User types: "def h[PAUSE 300ms]ello(na[type continues]me"

  1. Keystroke 'd' → timer scheduled (500ms delay)
  2. Keystroke 'e' → cancel previous timer, schedule new
  3. [Continue typing before timer fires]
  4. [PAUSE 500ms] → timer fires, request sent to API
  5. [While API is processing] User types 'm'
     → cancel() called, sets _stop_requested = True
     → Background thread checks flag, returns early
     → Response discarded (main thread not called)
```

### 10.6 Prose/Commentary Detection

**Problem:** Chat models sometimes respond with natural language instead of code.

**Solution:** Multi-layer detection in `_is_prose_response()`:

```python
# Layer 1: Keyword matching
prose_indicators = (
  "well-structured", "i suggest", "you should", 
  "code review", "looks good", "here is", ...
)
if any_indicator_matches:
    return True

# Layer 2: Statistical heuristic
# High space ratio + short words = prose
first_line_ratio = spaces / total_chars
avg_word_length = total_chars / word_count
if space_ratio > 0.35 and avg_word_len < 5 and word_count > 8:
    return True
```

### 10.7 Session Token Refresh

**Problem:** Copilot session tokens expire after ~8 hours.

**Solution:** Automatic refresh with margin:

```python
def _get_session_token():
    if self._session_token and time.time() < (expires_at - 60s):
        return self._session_token  # Still valid
    
    # Refresh: exchange OAuth token for new session token
    req to https://api.github.com/copilot_internal/v2/token
    store session_token and expires_at
```

### 10.8 API Availability Tracking

```python
_api_available: Optional[bool] = None  # None = untested, True = works, False = failed

# On FIM success: _api_available = True
# On chat 404/403: _fim_available = False (endpoint missing for account)
# On chat failure: _api_available = False
# Retry after 30s cooldown (_API_RETRY_COOLDOWN_S)
```

---

## 11. LIFECYCLE DIAGRAMS

### 11.1 Full Request Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                  User Types Character                        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│        _on_buffer_changed() fired                            │
│        - Record keystroke for adaptive debounce             │
│        - Clear existing ghost text                          │
│        - Cancel pending timer                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │  Is inline completion disabled? │
        │  Is autocomplete visible?       │
        └──────┬────────────────┘
               │ YES
               ▼
        ┌─────────────┐
        │   Return    │
        │   (skip)    │
        └─────────────┘
               │ NO
               ▼
    ┌──────────────────────────┐
    │ Schedule adaptive timer  │
    │ (250–800ms)              │
    │ GLib.timeout_add()       │
    └───────────┬──────────────┘
                │
      ┌─────────┴──────────┐
      │ More keystrokes?   │
      │ (timer fires?)     │
      └─────┬──────────────┘
            │ NO (timer fires)
            ▼
    ┌──────────────────────────────────┐
    │ _trigger_completion()            │
    │ - Gather context                 │
    │ - Check skip conditions          │
    │   (trailing whitespace, etc)     │
    └──────────┬──────────────────────┘
               │
        ┌──────┴──────┐
        │ Skip?       │
        └──────┬──────┘
               │ YES
               ▼
        ┌─────────────┐
        │   Return    │
        │   (skip)    │
        └─────────────┘
               │ NO
               ▼
    ┌──────────────────────────────────┐
    │ Provider.request_completion()    │
    │ (starts background thread)       │
    └──────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ Background Thread:               │
    │ 1. Check cache                   │
    │ 2. Try FIM endpoint              │
    │ 3. Try Chat endpoint (streaming) │
    │ 4. Cache result                  │
    │ 5. GLib.idle_add(on_result)      │
    └──────────┬──────────────────────┘
               │
    ┌──────────┴──────────────┐
    │ User types (cancel)?    │
    │ (_stop_requested = True)│
    └──────┬─────────────────┘
           │ YES
           ▼
    ┌─────────────┐
    │ Discard     │
    │ (return)    │
    └─────────────┘
           │ NO
           ▼
    ┌──────────────────────────────────┐
    │ _on_completion_received()        │
    │ (main thread)                    │
    │ - Store in _suggestions          │
    │ - Renderer.clear()               │
    │ - Renderer.show(text)            │
    │ - queue_draw()                   │
    └──────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ GTK do_snapshot() → render        │
    │ GhostTextRenderer.draw()         │
    │ - Calculate positions            │
    │ - Create Pango layout (italic)   │
    │ - Append to snapshot             │
    └──────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ Ghost text visible on screen     │
    │ Waiting for user action          │
    └──────────┬──────────────────────┘
               │
    ┌──────────┴────────────────────┐
    │ User presses?                 │
    │ Tab / Escape / Cmd+Right / .. │
    └──────┬──────────────────────┘
           │
    ┌──────┴────────────┐
    │ Action:           │
    │ - Accept all      │
    │ - Accept word     │
    │ - Dismiss         │
    │ - Cycle next      │
    │ - Cycle prev      │
    └──────┬────────────┘
           │
           ▼
    ┌──────────────────────────────────┐
    │ Renderer.accept() / dismiss() /   │
    │ cycle_next() / etc.              │
    │ (visual state cleared)            │
    └──────────┬──────────────────────┘
               │
    ┌──────────┴──────────────┐
    │ Accept?                 │
    │ (buffer insert needed)  │
    └──────┬──────────────────┘
           │ YES
           ▼
    ┌──────────────────────────────────┐
    │ begin_user_action()              │
    │ buffer.insert(offset, text)      │
    │ end_user_action()                │
    │ (undo entry created)             │
    └──────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ Suggestion accepted and inserted │
    │ User can undo with Cmd+Z         │
    └──────────────────────────────────┘
```

---

## 12. FILE STRUCTURE & CLASS RELATIONSHIPS

```
EditorTab (editor_view.py)
  ├─ _inline_completion: InlineCompletionManager
  ├─ view: ZenSourceView
  │   ├─ _ghost_text_renderer: GhostTextRenderer ←  set by manager
  │   ├─ on_key_pressed → InlineCompletionManager.handle_key()
  │   └─ do_snapshot() → GhostTextRenderer.draw()
  └─ buffer: GtkSource.Buffer

InlineCompletionManager (inline_completion_manager.py)
  ├─ _renderer: GhostTextRenderer
  ├─ _provider: InlineCompletionProvider
  ├─ _debounce: AdaptiveDebounce
  ├─ _suggestions: list[str]
  ├─ _suggestion_index: int
  ├─ _trigger_timer_id: int (GLib timer ID)
  └─ Methods:
      ├─ is_enabled()
      ├─ handle_key(keyval, state) → bool
      ├─ accept() / accept_word() / dismiss()
      ├─ cycle_next() / cycle_prev()
      ├─ trigger_now()
      ├─ _on_buffer_changed()
      ├─ _trigger_completion()
      ├─ _on_completion_received(text)
      ├─ _on_streaming_chunk(chunk)
      └─ _on_completion_error(error)

InlineCompletionProvider (inline_completion_provider.py)
  ├─ _api: CopilotAPI
  ├─ _cache: CompletionCache (LRU, 50 entries)
  ├─ _stop_requested: bool
  ├─ _api_available: Optional[bool]
  ├─ _api_fail_time: float
  └─ Methods:
      ├─ request_completion(context, on_result, on_error, on_chunk)
      ├─ cancel()
      ├─ _run()
      ├─ _try_fim(context, t0)
      ├─ _try_chat(context, model, t0, on_chunk)
      ├─ _build_prompt(context)
      ├─ _clean_response(text)
      ├─ _deduplicate(completion, context)
      └─ _is_prose_response(text)

GhostTextRenderer (ghost_text_renderer.py)
  ├─ _view: GtkSource.View
  ├─ _buffer: GtkSource.Buffer
  ├─ _ghost_text: str
  ├─ _cursor_offset: int
  ├─ _active: bool
  ├─ _inserting: bool (re-entrant guard)
  ├─ _ghost_color: Gdk.RGBA
  └─ Methods:
      ├─ is_active: property
      ├─ text: property
      ├─ show(text)
      ├─ append(text)  ← for streaming
      ├─ clear()
      ├─ accept() / accept_word() / accept_line()
      ├─ draw(snapshot)
      └─ _get_ghost_color()

CopilotAPI (copilot_api.py)
  ├─ _oauth_token: Optional[str]
  ├─ _session_token: Optional[str]
  ├─ _token_expires_at: float
  ├─ _api_base_url: Optional[str]
  ├─ _fim_available: Optional[bool]
  ├─ _lock: threading.Lock (for token sync)
  └─ Methods:
      ├─ is_available() → bool
      ├─ complete_fim(prefix, suffix, ...) → str | None
      ├─ complete(prompt, model, ...) → str | None
      ├─ complete_stream(prompt, ..., on_chunk, on_done) → str | None
      ├─ _get_oauth_token() → Optional[str]
      └─ _get_session_token() → Optional[str]

ContextGatherer (context_gatherer.py)
  ├─ gather_context(editor_tab) → CompletionContext
  ├─ _gather_cross_file_context(editor_tab, file_path) → list[RelatedSnippet]
  ├─ _parse_imports(source, current_file) → list[str]
  ├─ _extract_header(buffer, max_chars) → str
  └─ _read_file_header(file_path, max_chars) → str

CompletionContext (dataclass)
  ├─ prefix: str
  ├─ suffix: str
  ├─ file_path: str
  ├─ language: str
  ├─ cursor_line: int
  ├─ cursor_col: int
  └─ related_snippets: list[RelatedSnippet]

RelatedSnippet (dataclass)
  ├─ file_path: str
  ├─ content: str
  └─ relevance: str
```

---

## 13. TESTING STRATEGY

### 13.1 Unit Tests

**`tests/editor/inline_completion/test_inline_completion_manager.py`**
- `TestIsEnabled`: Settings checks
- `TestHandleKey`: Keystroke handling (Tab, Escape, Alt+], etc.)
- `TestCycling`: Multi-suggestion cycling
- `TestDebounce`: Adaptive debouncing behavior

**`tests/editor/inline_completion/test_inline_completion_provider.py`**
- `TestBuildPrompt`: Prompt format (FIM style, filename, cursor marker)
- `TestCleanResponse`: Response cleaning (markdown removal, prose detection)
- `TestDeduplicate`: Deduplication logic
- `TestCache`: LRU cache hit/miss

### 13.2 Manual Testing Checklist

```
✓ Keystroke triggers suggestion (500ms debounce)
✓ Tab accepts full suggestion
✓ Escape dismisses
✓ Cmd+Right accepts word
✓ Alt+] cycles to next suggestion (if multiple)
✓ Manual trigger via Alt+\
✓ Autocomplete popup doesn't interfere
✓ Multi-line suggestions render correctly
✓ Undo after accept works (Cmd+Z)
✓ Ghost text cleared on buffer changes
✓ Ghost text respects theme colors
✓ Trailing whitespace heuristic prevents junk suggestions
✓ Settings disable/enable works without restart
✓ Streaming chunks display progressively
✓ Cache hits return instantly
✓ Token refresh on expiry
```

---

## 14. TRACE LOGGING

All inline completion activity is logged with `[IC]` prefix for debugging.

**Enable via:** `_IC_TRACE = True` in any inline_completion module

**Example Output:**
```
[IC] _trigger_completion: requesting completion for 'def hello(na'
[IC] provider._run: cache hit (1 completions)
[IC] _on_completion_received: showing 52 chars: 'me: str) -> str:\n    return f"Hello {name}"'
[IC] cycle_next: showing suggestion 2/2
[IC] GhostTextRenderer.accept: 52 chars accepted
```

---

## 15. PERFORMANCE CHARACTERISTICS

| Operation | Latency | Notes |
|-----------|---------|-------|
| Keystroke → timer scheduled | ~0ms | GLib event |
| Timer fired → context gathered | ~5ms | Buffer iteration |
| Context → prompt built | ~2ms | String formatting |
| Prompt → cache lookup | ~0.5ms | MD5 hash |
| Cache hit → ghost text shown | ~5ms | GLib.idle_add + draw |
| Cache miss → FIM API call | ~800–1200ms | Network + AI inference |
| Cache miss → Chat API call | ~2000–3000ms | Network + AI inference + post-processing |
| Cache miss → Chat streaming (first token) | ~400ms | Progressive display |
| Ghost text → visual update | ~2ms | Pango layout + snapshot |
| Accept → buffer insert | ~3ms | GTK user action grouping |

**End-to-End (cold start):** ~1.5s (FIM) or ~3s (chat fallback)
**End-to-End (cache hit):** ~15ms

---

## 16. FUTURE ENHANCEMENTS

From the migration docs:

| Feature | Impact | Status |
|---------|--------|--------|
| Response caching | Medium | ✅ Implemented |
| Streaming display | Medium | ✅ Implemented |
| Multi-suggestion cycling | Low | ✅ Implemented |
| Adaptive debouncing | Low | ✅ Implemented |
| Cross-file context | High | ✅ Implemented |
| FIM-style prompts | High | ✅ Implemented |
| Tree-sitter AST awareness | High | 🔄 Future |
| Fine-tuned models | High | 🔄 Future |
| Server-side caching | Medium | ❌ Infrastructure needed |

---

## 17. SUMMARY TABLE

| Aspect | Details |
|--------|---------|
| **Architecture** | Manager → Provider → Renderer (modular, composable) |
| **Trigger** | Adaptive debounce (250–800ms, typing-aware) |
| **Context** | 3000 prefix + 1500 suffix + related files (imports, open tabs) |
| **Provider** | Copilot API (direct HTTP, no CLI) with FIM + chat fallback |
| **Caching** | LRU, 50 entries, keyed by context hash |
| **Rendering** | GTK4 snapshot overlay (italic, 55% alpha, theme-aware) |
| **Acceptance** | Tab, Cmd+Right, Cmd+Down with word/line variants |
| **Dismissal** | Escape or any other keystroke |
| **Cycling** | Alt+] / Alt+[ for alternative suggestions |
| **Undo** | Full preservation (ghost text never in buffer until accepted) |
| **Streaming** | Progressive token display via on_chunk callbacks |
| **Edge Cases** | Trailing whitespace filtering, prose detection, concurrent cancellation |
| **Testing** | Unit tests + manual checklist |

---

**End of Documentation**
