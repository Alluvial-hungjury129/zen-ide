# Integrated Terminal

Zen IDE includes a full VTE (Virtual Terminal Emulator) with 256-colour support, file path linking, custom shell aliases, and a workspace folder picker.

## Opening the Terminal

| Action | Shortcut |
|---|---|
| Focus terminal | `` Cmd+` `` |
| Clear terminal | `Cmd+K` |

## Terminal Layout

```
┌──────────────────────────────────────────┐
│  TERMINAL (clickable)  [+] [clear] [⛶]  │  ← header
├──────────────────────────────────────────┤
│                                          │
│  $ your commands here...                 │
│                                          │
└──────────────────────────────────────────┘
```

### Header Controls

| Control | Action |
|---|---|
| **TERMINAL** label | Click to open workspace folder picker (cd to project) |
| **+ button** | Split terminal — adds a new pane |
| **Clear button** | Clear scrollback buffer |
| **⛶ Maximise** | Toggle full-window terminal mode |
| **× Close** | Close this pane (visible with 2+ panes) |

## Terminal Shortcuts

| Shortcut | Action |
|---|---|
| `Cmd+C` or `Ctrl+Shift+C` | Copy selection |
| `Cmd+V` or `Ctrl+Shift+V` | Paste |
| `Opt+Left` | Move cursor back one word |
| `Opt+Right` | Move cursor forward one word |
| `Opt+Backspace` | Delete back one word |
| `Cmd+Click` on a file path | Open that file in the editor |
| `Ctrl+C` | Interrupt running command |

## Layout Modes

### Vertical Stack (default)

Multiple terminal panes stacked vertically, each with its own header:

```
┌──────────────────────┐
│ TERMINAL [+][⛶]     │
│ $ make test          │
├──────────────────────┤
│ TERMINAL [×]         │
│ $ npm run dev        │
└──────────────────────┘
```

### Tab Bar Mode

Switch with `behavior.terminals_on_vertical_stack = false`:

```
┌──────────────────────┐
│ [Pane 1] [Pane 2]    │
├──────────────────────┤
│ TERMINAL [⛶]         │
│ $ active pane here   │
└──────────────────────┘
```

## Shell Configuration

Zen IDE spawns a bash shell with its own configuration:

### Custom bashrc

The file `~/.zen_ide/bashrc` is sourced on terminal start. It provides:
- **Git-aware prompt** showing the current branch
- **Coloured output** with ANSI escape codes
- **Built-in aliases** (see below)

### Built-in Aliases

| Alias | Command |
|---|---|
| `gst` | `git status` |
| `groh` | `git reset --hard @{u}` |
| `git_prune_branches` | Delete all branches except main |
| `ls` | Colorised listing |
| `ll` | Long colorised listing |

### Custom Aliases

Add your own aliases to `~/.zen_ide/aliases`:

```bash
alias gco='git checkout'
alias gcb='git checkout -b'
alias gp='git push'
alias gl='git log --oneline -20'
```

This file is automatically sourced when a new terminal opens.

## File Path Linking

`Cmd+Click` on any file path in terminal output opens it in the editor. The terminal uses regex-based path detection to recognise:
- Absolute and relative paths
- `file:line:col` patterns (e.g., `src/main.py:42:5`)
- Compiler/linter output patterns

## Workspace Folder Picker

Click the **TERMINAL** label in the header to see a list of workspace folders. Select one to `cd` into it. The terminal also optionally follows the active editor file — when you switch tabs, the terminal `cd`s into that file's directory.

Toggle this behaviour: `behavior.terminal_follow_file` (default: `true`)

## Scrollback

Default scrollback buffer: **10,000 lines**. Configure with `terminal.scrollback_lines`.

## Built-in Tools

### `open_pr` — Create a PR from Terminal

The `open_pr` command creates a GitHub pull request with an AI-generated title and description based on the current branch's changes.

**Requirements:**
- [GitHub CLI (`gh`)](https://cli.github.com) — must be installed and authenticated (`gh auth login`)
- Optionally, `claude` or `copilot` CLI for AI-generated descriptions (falls back to commit log)

**Usage:**

```bash
open_pr              # Create PR for current branch → main
open_pr -b develop   # Create PR against a custom base branch
open_pr -h           # Show help
```

The script checks that you're not on the base branch, collects the diff, and uses an available AI CLI to generate a meaningful PR description. If no AI CLI is found, it uses the commit log as the body.

## Settings

| Setting | Default | Description |
|---|---|---|
| `terminal.scrollback_lines` | `10000` | Lines kept in scrollback buffer |
| `terminal.shell` | `""` | Shell path (empty = auto-detect) |
| `behavior.terminal_follow_file` | `true` | Auto-cd when switching editor tabs |
| `behavior.terminals_on_vertical_stack` | `true` | Vertical stack vs tab bar mode |
| `behavior.auto_expand_terminals` | `true` | Reset terminal size when opening files |
