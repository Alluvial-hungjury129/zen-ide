# Slack Integration Idea

**Created_at:** 2026-01-25  
**Updated_at:** 2026-03-12  
**Status:** Planned  
**Goal:** Capture a possible Slack integration for sharing code, terminal output, and summaries directly from Zen IDE.  
**Scope:** prospective `src/slack/` modules, IDE sharing workflows, external messaging integrations  

---

## Summary

This document captures a potential Slack integration that would let Zen IDE users share code and workflow information without leaving the editor.

## Integration Options

| Approach | Direction | Use Case |
|----------|-----------|----------|
| **Web API** (`slack_sdk`) | Bi-directional | Full chat, channels, messages |
| **Incoming Webhooks** | IDE -> Slack only | Notifications, snippet sharing |
| **Socket Mode** | Real-time bi-directional | Live chat panel |

## Potential Features

### Easy

- Share a code snippet to a Slack channel
- Post terminal output to Slack
- Send AI chat summaries

### Medium

- View Slack channels in a panel
- Reply to messages from the IDE

### Hard

- Full embedded Slack chat panel

## Proposed Structure

```text
src/slack/
├── slack_client.py
├── slack_panel.py
└── slack_config.py
```
