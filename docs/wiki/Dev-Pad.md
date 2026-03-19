# Dev Pad — Activity Tracker

The Dev Pad is an activity tracking panel that logs your recent work: file edits, AI chats, git commits, terminal commands, and more. It also lets you add manual notes, ideas, and reminders.

## Opening Dev Pad

| Action | Shortcut |
|---|---|
| Toggle Dev Pad | `Cmd+.` |

The Dev Pad appears as a split panel alongside the editor on the right side.

## Activity Types

The Dev Pad automatically tracks these activities:

| Icon | Type | What It Tracks |
|---|---|---|
| 📝 | File edit | File modifications |
| 📄 | File open | Files opened in editor |
| 💾 | File save | Files saved |
| 📋 | New file | New unsaved files |
| 🤖 | AI chat | AI chat interactions |
| 🔀 | Git checkout | Branch switches |
| ✅ | Git commit | Commits made |
| 🔍 | Search | Global searches |
| 💻 | Terminal | Terminal commands |

## Manual Entries

You can also add your own entries:

| Icon | Type | Purpose |
|---|---|---|
| 📌 | Note | Jot down observations or context |
| 💡 | Idea | Capture ideas while coding |
| ⏰ | Reminder | Things to come back to |
| 👀 | PR review | Mark PRs for review |

## Features

### Search & Filter
Filter activities by type: **All**, **PRs**, **Notes**, **Ideas**.

### Quick Links
Click any logged activity to jump back to it:
- Click a file edit → opens the file
- Click a git commit → shows the commit
- Click a PR → opens the pull request

### GitHub PR Integration
The Dev Pad fetches open pull requests via the `gh` CLI when available, showing them in a dedicated view.

### Activity Management
- Delete individual activities
- Clear all activities

## Persistence

Activities are stored in `~/.zen_ide/dev_pad.json`:
- Maximum **500 activities** stored (oldest trimmed automatically)
- Data persists across IDE restarts

## Settings

| Setting | Default | Description |
|---|---|---|
| `behavior.auto_show_dev_pad_when_empty` | `true` | Show Dev Pad when no files are open |

## Tips

- Use **Notes** to leave breadcrumbs while debugging — "tried approach X, didn't work because Y"
- Use **Ideas** as a lightweight backlog while coding
- The activity log gives you a timeline of your coding session — useful for standups and time tracking
