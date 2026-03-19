# AI Setup & Providers

Zen IDE integrates with AI coding assistants for inline code completions and interactive chat. All providers use **direct HTTP API calls** — no CLI tools or Node.js required.

## Supported Providers

| Provider | Auth | Models |
|---|---|---|
| **Copilot API** | GitHub Copilot subscription (auto-detected) | claude-sonnet-4 (default), gpt-4.1, and more |
| **Anthropic API** | API key from [console.anthropic.com](https://console.anthropic.com) | claude-sonnet-4, claude-opus-4, claude-haiku-4 |
| **OpenAI API** | API key from [platform.openai.com](https://platform.openai.com) | gpt-4.1, o3, o4-mini |

## Setup

### Copilot API (Zero Setup)

If you use GitHub Copilot in another editor (JetBrains, Neovim, etc.) — **you're already set up**. Zen auto-detects the OAuth token stored at `~/.config/github-copilot/apps.json` by your editor's Copilot extension.

If auto-detection doesn't work, provide a GitHub token manually:

**Option A — In-IDE:** Open AI chat → click provider selector → choose "Copilot API ⚙ setup" → enter your GitHub token.

**Option B — Manual:** Create `~/.zen_ide/api_keys.json`:
```json
{
  "github": "ghp_your-github-token"
}
```

**Option C — Environment variable:**
```bash
export GITHUB_TOKEN="ghp_your-github-token"
```

> The token must have Copilot access. GitHub Personal Access Tokens (PATs) created at [github.com/settings/tokens](https://github.com/settings/tokens) work if your account has a Copilot subscription.

### Anthropic API

**In-IDE:** Open AI chat → click provider selector → choose "Anthropic API ⚙ setup" → enter your API key.

**Manual:** Add to `~/.zen_ide/api_keys.json`:
```json
{
  "anthropic": "sk-ant-your-key-here"
}
```

Or: `export ANTHROPIC_API_KEY="sk-ant-your-key-here"`

Get a key at: [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)

### OpenAI API

**In-IDE:** Open AI chat → click provider selector → choose "OpenAI API ⚙ setup" → enter your API key.

**Manual:** Add to `~/.zen_ide/api_keys.json`:
```json
{
  "openai": "sk-your-key-here"
}
```

Or: `export OPENAI_API_KEY="sk-your-key-here"`

Get a key at: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

## Provider Auto-Detection

On startup, Zen IDE checks providers in this order:
1. **Copilot API** — looks for `~/.config/github-copilot/apps.json`, `GITHUB_TOKEN` env, or `~/.zen_ide/api_keys.json`
2. **Anthropic API** — looks for `ANTHROPIC_API_KEY` env or `~/.zen_ide/api_keys.json`
3. **OpenAI API** — looks for `OPENAI_API_KEY` env or `~/.zen_ide/api_keys.json`

The first available provider is activated automatically.

## Switching Providers

Use the provider dropdown in the AI chat header, or set `ai.provider` in `~/.zen_ide/settings.json`:

```json
{
  "ai.provider": "copilot_api"
}
```

Valid values: `"copilot_api"`, `"anthropic_api"`, `"openai_api"`, `""` (auto-detect)

You can also set models per provider:

```json
{
  "ai.model.copilot_api": "claude-sonnet-4",
  "ai.model.anthropic_api": "claude-sonnet-4-20250514",
  "ai.model.openai_api": "gpt-4.1"
}
```

## AI Settings

| Setting | Default | Description |
|---|---|---|
| `ai.is_enabled` | `true` | Master toggle for all AI features |
| `ai.provider` | `""` | Active provider (`"copilot_api"`, `"anthropic_api"`, `"openai_api"`, or `""` for auto-detect) |
| `ai.show_inline_suggestions` | `true` | Show ghost text inline completions |
| `ai.yolo_mode` | `true` | Skip tool-use confirmation prompts |
| `ai.model.copilot_api` | `"claude-sonnet-4"` | Selected Copilot API model |
| `ai.model.anthropic_api` | `"claude-sonnet-4-20250514"` | Selected Anthropic API model |
| `ai.model.openai_api` | `"gpt-4.1"` | Selected OpenAI API model |
| `ai.inline_completion.trigger_delay_ms` | `200` | Debounce delay before requesting completions |
| `ai.inline_completion.model` | `"gpt-4.1"` | Model used for inline completions |
| `ai.auto_scroll_on_output` | `true` | Auto-scroll chat while AI is responding |

## Disabling AI

To completely disable AI features:

```json
{
  "ai.is_enabled": false
}
```

To disable only inline suggestions (keep chat):

```json
{
  "ai.show_inline_suggestions": false
}
```

## Troubleshooting

**"Copilot API — failed to get session token"**
- Your GitHub token may not have Copilot access
- Check you have an active GitHub Copilot subscription
- If using `~/.config/github-copilot/apps.json`, try re-authenticating Copilot in your editor

**"Anthropic/OpenAI API key not configured"**
- Check `~/.zen_ide/api_keys.json` exists with the correct key
- Or set the appropriate environment variable

**"Invalid API key" / 401 error**
- Verify your key is valid and not expired

**"Rate limited" / 429 error**
- Wait a few seconds and retry
- Check your API plan usage limits
