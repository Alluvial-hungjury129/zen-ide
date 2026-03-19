# AI SETUP GUIDE

**Created_at:** 2026-01-25  
**Updated_at:** 2026-06-20  
**Status:** Active  
**Goal:** Document AI provider setup — HTTP API providers  
**Scope:** Copilot API, Anthropic API, OpenAI API  

---

Zen IDE supports three AI providers, all via **direct HTTP API calls** — no CLI tools or Node.js required.

## Copilot API (Recommended — Zero Setup)

If you use GitHub Copilot in another editor (JetBrains, Neovim, etc.), Zen auto-detects your existing credentials from `~/.config/github-copilot/apps.json`.

### How it works

When you authenticate GitHub Copilot in any editor, it stores an OAuth token (`ghu_...`) in `~/.config/github-copilot/apps.json`. Zen reads this token and exchanges it for a Copilot session token via `api.github.com/copilot_internal/v2/token`, then uses that to call `api.githubcopilot.com/chat/completions`.

### Token resolution order

1. `~/.config/github-copilot/apps.json` — Copilot OAuth auth from any editor (most reliable)
2. `~/.zen_ide/api_keys.json` — `{"github": "ghp_..."}` or `{"github": "ghu_..."}`
3. `GITHUB_TOKEN` environment variable

Each source is tried in order; the first token that successfully exchanges for a Copilot session token is used.

### Manual setup (if auto-detection fails)

**In-IDE:** Open AI chat → click provider selector → choose "Copilot API ⚙ setup" → enter your GitHub token.

**Manual:** Create `~/.zen_ide/api_keys.json`:
```json
{
  "github": "ghp_your-github-token"
}
```

Or set the environment variable:
```bash
export GITHUB_TOKEN="ghp_your-github-token"
```

> Your GitHub account must have an active Copilot subscription. Regular PATs from [github.com/settings/tokens](https://github.com/settings/tokens) work if your account has Copilot access.

## Anthropic API (Claude)

Direct access to Claude models. No CLI needed.

**In-IDE setup:** Open AI chat → click provider selector → choose "Anthropic API ⚙ setup" → enter your API key.

**Manual setup:** Create `~/.zen_ide/api_keys.json`:
```json
{
  "anthropic": "sk-ant-your-key-here"
}
```

Or set the environment variable:
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

Get an API key at: https://console.anthropic.com/settings/keys

## OpenAI API (GPT, o-series)

Works with OpenAI and any OpenAI-compatible endpoint (Azure, local proxies).

**In-IDE setup:** Open AI chat → click provider selector → choose "OpenAI API ⚙ setup" → enter your API key.

**Manual setup:** Create `~/.zen_ide/api_keys.json`:
```json
{
  "openai": "sk-your-key-here",
  "openai_base_url": "https://api.openai.com/v1"
}
```

Or set environment variables:
```bash
export OPENAI_API_KEY="sk-your-key-here"
export OPENAI_API_BASE="https://api.openai.com/v1"  # optional, defaults to OpenAI
```

Get an API key at: https://platform.openai.com/api-keys

---

## TROUBLESHOOTING

**"Failed to get Copilot session token"**
- Your GitHub token may not have Copilot access
- Check you have an active Copilot subscription at [github.com/settings/copilot](https://github.com/settings/copilot)
- If using `~/.config/github-copilot/apps.json`, try re-authenticating Copilot in your editor

**"Anthropic API key not configured"**
- Check `~/.zen_ide/api_keys.json` exists and has `"anthropic": "sk-ant-..."` entry
- Or set `ANTHROPIC_API_KEY` environment variable

**"OpenAI API key not configured"**
- Check `~/.zen_ide/api_keys.json` exists and has `"openai": "sk-..."` entry
- Or set `OPENAI_API_KEY` environment variable

**"Invalid API key" / 401 error**
- Verify your key is valid and not expired
- Anthropic: https://console.anthropic.com/settings/keys
- OpenAI: https://platform.openai.com/api-keys

**"Rate limited" / 429 error**
- Wait a few seconds and try again
- Check your API plan usage limits

**"AI suggestions not working"**
- Check `ai.is_enabled` is `true` and `ai.show_inline_suggestions` is `true` in settings
- Check terminal for detailed error messages
