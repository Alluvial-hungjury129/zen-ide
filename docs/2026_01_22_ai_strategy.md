# Zen AI Strategy

**Created_at:** 2026-01-22  
**Updated_at:** 2026-06-20  
**Status:** Active  
**Goal:** Document how Zen IDE AI chat works — HTTP providers, tool use, system prompt, rendering  
**Scope:** `src/ai/`  

---

## Overview

Zen IDE's AI chat is an **agentic coding assistant** built into the IDE. It communicates with AI providers via **direct HTTP API calls** (no CLI tools, no subprocesses, no Node.js). The assistant can read/write/edit files, search code, and run shell commands through a tool-use loop.

### Key Design Decisions

- **HTTP-only** — All providers use direct HTTP streaming. No subprocess spawning, no CLI wrappers.
- **Tool use** — The AI has 6 tools (read_file, write_file, edit_file, list_files, search_files, run_command) and executes them in an agentic loop until the task is complete.
- **Yolo mode** — By default, there is no tool call limit. The AI continues until done.
- **Multiple parallel sessions** — Each chat tab is an independent session with its own history, provider, and model.
- **ChatCanvas rendering** — AI output is rendered on a DrawingArea (GtkSnapshot), not a VTE terminal. Markdown is converted to ANSI-styled text.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Zen IDE                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                    AI Chat Tabs                            │   │
│  │  Multiple independent chat sessions (vertical stack)      │   │
│  │  Each session: own history, own provider, own model        │   │
│  └───────────────────────────┬───────────────────────────────┘   │
│                              │                                    │
│                              ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │              AIChatTerminalView (per session)              │   │
│  │                                                            │   │
│  │  1. Builds system prompt (workspace dirs, focused file)    │   │
│  │  2. Builds api_messages[] from conversation history        │   │
│  │  3. Sends to HTTP provider in background thread            │   │
│  │  4. Streams chunks → markdown renderer → ChatCanvas        │   │
│  │  5. On tool_use → executes tool → sends results → loop     │   │
│  └───────────────────────────┬───────────────────────────────┘   │
│                              │                                    │
│              ┌───────────────┼───────────────┐                    │
│              ▼               ▼               ▼                    │
│  ┌────────────────┐ ┌───────────────┐ ┌────────────────┐        │
│  │  Anthropic API  │ │  Copilot API  │ │  OpenAI API    │        │
│  │  (Messages)     │ │  (Chat)       │ │  (Chat)        │        │
│  └────────────────┘ └───────────────┘ └────────────────┘        │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## How a Message Flows

### 1. User sends a message

`_on_send()` appends `{"role": "user", "content": message}` to `self.messages` and calls `_run_ai_http(message)`.

### 2. System prompt is built

`_run_ai_http()` constructs the system prompt from:

| Source | Content |
|--------|---------|
| Static | "You are a coding assistant integrated into Zen IDE..." |
| `get_workspace_folders()` | Working directories (e.g. `/path/to/project-a, /path/to/project-b`) |
| `get_current_file()` | Currently focused file path in the editor |
| Yolo mode | "You have UNLIMITED tool calls" or "You have a limit of 25 tool calls" |

**Note:** The system prompt does NOT include file contents, terminal output, or editor content. The AI discovers context by using its tools (read_file, search_files, etc.).

### 3. Conversation history is sent as structured API messages

```python
api_messages = []
for msg in self.messages[:-1]:  # All previous messages
    api_messages.append({"role": role, "content": content})
api_messages.append({"role": "user", "content": current_message})
```

Each message is a properly structured `{"role", "content"}` dict — no flattened text, no context duplication.

### 4. HTTP provider streams the response

The provider (e.g. `AnthropicHTTPProvider`) starts a background thread that:
- POSTs to the API with `stream: True`
- Reads SSE (Server-Sent Events) line by line
- Calls `on_chunk(text)` for each text/thinking delta → scheduled on GTK main thread via `GLib.idle_add()`
- Calls `on_tool_use(tool_calls, text)` if the model requests tool execution
- Calls `on_complete(full_text)` or `on_error(msg)` when done

### 5. Tool use loop (agentic)

When the model requests tools:

1. `_on_tool_use()` receives the tool call list
2. Each tool is executed by `ToolExecutor` (runs in the main thread)
3. Results are displayed in the chat
4. `provider.continue_with_tool_results()` sends results back to the API
5. The model generates more text or requests more tools — repeat until `on_complete`

In **yolo mode** (default), there is no limit on iterations. The model can make hundreds of tool calls in a single conversation turn.

### 6. Rendering pipeline

```
Stream chunk (text)
  → _render_stream_chunk()
    → Split thinking/content markers
    → Thinking: throttled, collapsible block
    → Content: _md_renderer.feed(text) → ANSI-formatted string
      → ChatCanvas.feed(ansi_text) → AnsiBuffer → DrawingArea
```

The `TerminalMarkdownRenderer` converts markdown to ANSI escape codes (bold, italic, colors, code blocks with syntax highlighting via Pygments). The `ChatCanvas` (a `Gtk.DrawingArea`) renders styled text using `GtkSnapshot`.

## AI Providers

All three providers implement the same interface: `send_message_stream()`, `continue_with_tool_results()`, `stop()`, `get_available_models()`.

| Provider | Class | API Endpoint | Auth |
|----------|-------|-------------|------|
| Copilot | `CopilotHTTPProvider` | `api.githubcopilot.com/chat/completions` | GitHub OAuth → session token exchange |
| Anthropic | `AnthropicHTTPProvider` | `api.anthropic.com/v1/messages` | API key (`ANTHROPIC_API_KEY` or `~/.zen_ide/api_keys.json`) |
| OpenAI | `OpenAIHTTPProvider` | `api.openai.com/v1/chat/completions` | API key (`OPENAI_API_KEY` or `~/.zen_ide/api_keys.json`) |

### Provider auto-detection

On startup, providers are checked for availability (API key present). The priority is: Copilot > Anthropic > OpenAI. Users can override via settings or the UI dropdown.

### Model discovery

Each provider fetches models from its API or uses a curated known-good list. Models are never hardcoded in the main application.

### Copilot auth flow

1. Find GitHub token from `~/.config/github-copilot/apps.json`, `~/.zen_ide/api_keys.json`, or `GITHUB_TOKEN` env
2. Exchange for session token via `api.github.com/copilot_internal/v2/token`
3. Use session token as Bearer auth for API calls (cached, auto-refreshed)

## Tools

Defined in `tool_definitions.py`, executed by `tool_executor.py`:

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents (max 512 KB) |
| `write_file` | Create or overwrite a file |
| `edit_file` | Find-and-replace a unique text match in a file |
| `list_files` | Glob pattern file discovery |
| `search_files` | Regex search in file contents (uses ripgrep/grep) |
| `run_command` | Run a shell command (30s timeout) |

All paths are resolved relative to the workspace root. Path traversal outside the workspace is blocked.

## Chat Persistence

Each chat session is saved to `~/.zen_ide/ai_chat/chat_{session_id}.json`:

```json
[
  {"role": "user", "content": "Fix the bug in auth.py"},
  {"role": "assistant", "content": "I'll look at the file...", "thinking": "Let me read..."},
  ...
]
```

Sessions are restored on IDE restart. Maximum 100 messages per session.

## Auto-Scroll

During streaming, auto-scroll keeps the viewport at the bottom. If the user scrolls away manually, auto-scroll pauses (showing a "Jump to bottom" indicator). Scrolling back near the bottom re-engages auto-scroll.

## Thinking Blocks

For Anthropic models that support extended thinking (Opus, Sonnet), thinking text is:
- Displayed in a dim, collapsible block
- Throttled at 50ms intervals to avoid saturating the main loop
- Collapsed to a single "Thinking..." summary line when content text begins

## Inline Autosuggestion

Separate from the chat system. Provides ghost-text completions in the editor:
- Trigger: after typing pause
- Provider: Copilot API (inline completion endpoint)
- Accept: Tab key
- Dismiss: Escape key

See `src/editor/inline_completion/` for details.

## Files

| File | Purpose |
|------|---------|
| `src/ai/__init__.py` | Module init with lazy imports |
| `src/ai/ai_chat_tabs.py` | Multi-session tab management (vertical stack) |
| `src/ai/ai_chat_terminal.py` | Core chat view: prompt building, HTTP streaming, tool loop, rendering |
| `src/ai/anthropic_http_provider.py` | Anthropic Messages API — streaming, thinking blocks, tool use |
| `src/ai/openai_http_provider.py` | OpenAI Chat Completions API — streaming, tool use |
| `src/ai/copilot_http_provider.py` | GitHub Copilot Chat API — OAuth, session tokens, streaming, tool use |
| `src/ai/tool_definitions.py` | Provider-agnostic tool schemas with Anthropic/OpenAI converters |
| `src/ai/tool_executor.py` | Executes tool calls (file I/O, grep, shell commands) |
| `src/ai/chat_canvas.py` | DrawingArea renderer for ANSI-styled text (GtkSnapshot) |
| `src/ai/ansi_buffer.py` | Parses ANSI escape codes into styled line spans |
| `src/ai/terminal_markdown_renderer.py` | Streaming markdown → ANSI converter (code highlighting, tables) |
| `src/ai/system_tag_stripper.py` | Strips XML tags from stream data (used during resize re-rendering) |
| `src/ai/tab_title_inferrer.py` | Generates short chat tab titles from first user message |
| `src/ai/spinner.py` | Braille-character spinner for loading state |
| `src/ai/block_cursor_text_view.py` | Input text view with block cursor |
| `src/ai/dock_badge.py` | Notification badge for the AI chat dock button |
| `src/ai/markdown_formatter.py` | Markdown formatting utilities |
