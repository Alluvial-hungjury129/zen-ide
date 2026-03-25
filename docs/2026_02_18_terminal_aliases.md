# Terminal Aliases

**Created_at:** 2026-02-18  
**Updated_at:** 2026-03-25  
**Status:** Active  
**Goal:** Document built-in shell aliases and custom alias support via `~/.zen_ide/aliases`  
**Scope:** `src/terminal/`, bash/zsh aliases  

---

Zen IDE's integrated terminal comes with built-in shell aliases for common operations.

## Built-in Aliases

| Alias | Command | Description |
|-------|---------|-------------|
| `gst` | `git status` | Show git status |
| `groh` | `git reset --hard @{u}` | Hard reset to upstream |
| `git_prune_branches` | `git branch \| grep -v "^\*" \| grep -v "^  main$" \| xargs git branch -D` | Delete all local branches except `main` and the current branch |
| `ls` | `ls --color=auto` / `ls -G` | Colorized file listing (platform-aware) |
| `ll` | `ls -l --color=auto` / `ls -lG` | Long colorized file listing (platform-aware) |
| `open_pr` | `tools/open_pr` | Create a GitHub PR with AI-generated description (requires `gh` + `claude`/`copilot` CLI) |

## Custom Aliases

You can add your own aliases by creating the file `~/.zen_ide/aliases`. This file is sourced automatically when a new terminal session starts.

### Example `~/.zen_ide/aliases`

```bash
alias gco='git checkout'
alias gcb='git checkout -b'
alias gp='git push'
alias gl='git pull'
alias glog='git log --oneline --graph --decorate'
```

Any valid bash alias or function can be placed in this file. Changes take effect in new terminal sessions.

## `open_pr` — Create PR from Terminal

The `open_pr` command creates a GitHub pull request with an AI-generated description based on the current branch's changes.

### Requirements

- **`gh`** (GitHub CLI) — authenticated via `gh auth login`
- **`claude`** or **`copilot`** CLI — required for AI-generated descriptions

### Usage

```bash
open_pr              # Create PR for current branch → main
open_pr -b develop   # Create PR against a custom base branch
open_pr -h           # Show help
```

### What It Does

1. Gathers the commit log and diff between your branch and `main`
2. Uses the branch name as the PR title
3. Sends the changes to an AI CLI (claude or copilot) to generate a `## Description` body (3-line synthesis)
4. Pushes the branch if not already pushed
5. Creates the PR via `gh pr create`
