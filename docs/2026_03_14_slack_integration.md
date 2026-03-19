# Slack Integration

**Created_at:** 2026-03-14  
**Updated_at:** 2026-03-14  
**Status:** Draft  
**Goal:** Add lightweight Slack messaging to Zen IDE using a Bot Token and the Slack Web API  
**Scope:** `src/slack/`, `src/keybindings.py`, `src/shared/settings_manager.py`, `src/popups/`  

---

## Overview

Integrate Slack into Zen IDE so users can send messages, share code snippets, and communicate with teammates without leaving the editor. The integration uses a **Slack Bot Token** (`xoxb-…`) stored in user settings — no OAuth browser flow required.

---

## UX Flow

### 1. Setup (one-time)

1. User creates a Slack App at [api.slack.com](https://api.slack.com/apps) and installs it to their workspace.
2. User copies the **Bot User OAuth Token** (`xoxb-…`).
3. In Zen IDE, user opens Settings and pastes the token under `slack.bot_token`.

### 2. Sending a Message

1. **Trigger:** `Cmd+Shift+S` (or command palette → "Send to Slack").
2. A `SelectionDialog` opens showing two sections:
   - **#channels** — fetched from `conversations.list` API
   - **@people** — fetched from `users.list` API
3. User fuzzy-searches and picks a target.
4. A compose popup (`NvimPopup`) opens with:
   - Pre-filled selected text from the editor (if any), wrapped in a code block
   - File path and line numbers as context
   - Editable message area
   - Send button
5. On send → `chat.postMessage` → toast notification: *"✓ Sent to #general"*

---

## Capabilities

| Action | Description |
|--------|-------------|
| **Send to channel** | Pick a `#channel` from the list → compose message → send |
| **Send to person (DM)** | Pick a `@user` → open DM via `conversations.open` → send |
| **Share code snippet** | Selected editor text sent as a Slack code block (` ```code``` `) with language annotation |
| **Share file reference** | Current file path + line range formatted as context in the message |
| **Default channel** | Optional `slack.default_channel` setting to skip the picker for quick sends |

---

## Architecture

```
src/slack/
├── slack_service.py      # API calls (stateless, async-friendly)
├── slack_picker.py       # SelectionDialog subclass for channel/user picking
└── slack_compose.py      # NvimPopup subclass for message composition
```

### `SlackService` (`slack_service.py`)

Handles all Slack Web API communication using Python's built-in `urllib.request` (no external dependencies).

**Methods:**

| Method | Slack API | Purpose |
|--------|-----------|---------|
| `list_channels()` | `conversations.list` | Fetch public/private channels the bot is in |
| `list_users()` | `users.list` | Fetch workspace members |
| `open_dm(user_id)` | `conversations.open` | Open/get a DM channel with a user |
| `send_message(channel_id, text)` | `chat.postMessage` | Post a message to a channel or DM |

**Design:**

- All methods return simple dicts/lists — no Slack SDK objects.
- Errors surface as exceptions caught by the UI layer → displayed as toasts.
- Channel and user lists are cached in memory with a short TTL (5 min) to avoid repeated API calls.
- Runs HTTP requests off the main thread using `GLib.Thread` to keep the UI responsive.

### `SlackPicker` (`slack_picker.py`)

Subclass of `SelectionDialog`. Shows a unified list of channels and users, prefixed with `#` and `@` respectively, for fuzzy search.

### `SlackCompose` (`slack_compose.py`)

Subclass of `NvimPopup`. Contains:

- A read-only header showing the target (e.g., `→ #general`)
- A `GtkSourceView` text area for composing the message
- Pre-populated context (selected code, file path) that the user can edit or remove
- `Cmd+Enter` to send, `Escape` to cancel

---

## Settings

New entries in `~/.zen_ide/settings.json`:

```json
{
  "slack.bot_token": "xoxb-...",
  "slack.default_channel": "#general",
  "slack.include_file_context": true
}
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `slack.bot_token` | `string` | `""` | Slack Bot User OAuth Token |
| `slack.default_channel` | `string` | `""` | Skip picker and send directly to this channel |
| `slack.include_file_context` | `bool` | `true` | Auto-include file path and line numbers in messages |

---

## Slack App Setup

Required **Bot Token Scopes**:

| Scope | Reason |
|-------|--------|
| `channels:read` | List public channels |
| `groups:read` | List private channels the bot is in |
| `users:read` | List workspace members |
| `chat:write` | Send messages |
| `im:write` | Open and send DMs |

The bot must be **invited to channels** it needs to post in (Slack requirement).

---

## Keybinding

| Shortcut | Action |
|----------|--------|
| `Cmd+Shift+S` | Open Slack send dialog |

Registered in `src/keybindings.py` alongside existing shortcuts.

---

## Implementation Phases

### Phase 1 — Send to Channel (MVP)

- [x] `SlackService` with `list_channels()` and `send_message()`
- [x] `SlackPicker` showing channels only
- [x] `SlackCompose` popup with basic text input
- [x] Settings: `slack.bot_token`
- [x] Keybinding: `Cmd+Shift+S`
- [x] Toast on success/failure
- [x] Error handling for missing/invalid token

### Phase 2 — DMs and Code Sharing

- [x] `list_users()` and `open_dm()` in `SlackService`
- [x] Unified channel + user list in `SlackPicker`
- [x] Auto-populate selected code as a code block in `SlackCompose`
- [x] File context (path + lines) appended to messages
- [x] Settings: `slack.default_channel`, `slack.include_file_context`

### Phase 3 — Polish

- [x] Channel/user caching with TTL
- [ ] Loading indicator while fetching channels/users
- [x] Keyboard-only flow (no mouse needed)
- [ ] Remember last-used channel for quick re-send
- [ ] Command palette entry: "Send to Slack"

---

## Non-Goals

- **Reading messages** — Zen is an editor, not a Slack client
- **Threads / reactions** — keep the scope minimal
- **OAuth browser flow** — bot token paste is simpler and sufficient
- **Slack SDK dependency** — use `urllib` to stay dependency-free
- **File uploads** — text messages only for now

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Bot token leaked in settings file | Document that `settings.json` should not be committed; consider env var support later |
| API rate limits | Cache channel/user lists; sends are infrequent and well within limits |
| Bot not in channel | Clear error toast: *"Bot is not a member of #channel — invite it first"* |
| Network errors | Timeout after 10s; show toast with retry option |
