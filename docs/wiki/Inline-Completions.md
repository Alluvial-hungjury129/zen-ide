# Inline Code Completions

Zen IDE provides AI-powered inline code suggestions that appear as ghost text in your editor.

## How It Works

1. **You type code** — After a brief pause (500ms by default), Zen requests a completion from the AI
2. **Ghost text appears** — The suggestion is rendered in dimmed text at your cursor position
3. **Accept or dismiss** — Press `Tab` to accept, `Escape` to dismiss, or just keep typing to ignore it

```
def calculate_total(items):
    total = 0
    for item in items:░ total += item.price    ← ghost text (dimmed)
```

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Tab` | Accept the full suggestion |
| `Cmd+Right` | Accept one word at a time |
| `Escape` | Dismiss the suggestion |
| `Alt+]` | Cycle to next suggestion |
| `Alt+[` | Cycle to previous suggestion |

## Context Gathering

The completion system sends the AI relevant context:
- **Current file content** — surrounding lines around the cursor
- **Cursor position** — line and column
- **File language** — detected from extension
- **Imports and definitions** — from the current file

This context helps the AI make accurate, relevant suggestions.

## Adaptive Trigger Delay

The system adapts to your typing speed:
- While you're typing quickly, suggestions are suppressed to avoid distraction
- After you pause, the system waits the configured delay before requesting a completion
- Default delay: **500ms** (configurable)

## Multi-Suggestion Cycling

The AI may return multiple suggestions for the same position. Use `Alt+]` and `Alt+[` to cycle through them.

## Settings

| Setting | Default | Description |
|---|---|---|
| `ai.show_inline_suggestions` | `true` | Enable/disable inline completions |
| `ai.inline_completion.trigger_delay_ms` | `500` | Milliseconds to wait before requesting |
| `ai.inline_completion.model` | `"gpt-4.1"` | AI model used for completions |
| `ai.is_enabled` | `true` | Master AI toggle (also disables completions) |

## Disabling Inline Completions

To keep AI chat but disable ghost text suggestions:

```json
{
  "ai.show_inline_suggestions": false
}
```

## Tips

- **Tab to accept** — The most common workflow is just pressing `Tab` when you see a good suggestion
- **Partial accept** — Use `Cmd+Right` to accept word-by-word for long suggestions
- **Keep typing** — If the suggestion isn't relevant, just keep typing — it will disappear
- **Trigger manually** — Pause briefly after typing to trigger a new suggestion
