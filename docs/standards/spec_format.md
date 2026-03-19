# Documentation Spec Format

**Created_at:** 2026-03-08  
**Updated_at:** 2026-03-09  
**Status:** Active  
**Goal:** Define the standard format all `docs/` files must follow for consistency and discoverability  
**Scope:** All markdown files in `docs/`  

---

## Why Standardize?

Every document in `docs/` serves as a specification, guide, or reference for a part of Zen IDE. Without a consistent format, it's hard to know at a glance:

- **When** a doc was written or last updated
- **Whether** the feature is implemented, planned, or in progress
- **What** the doc aims to achieve
- **Which** parts of the codebase it covers

Standardizing the frontmatter solves this. It makes docs scannable, sortable, and keeps the project's knowledge base organized as it grows.

---

## Required Frontmatter

Every markdown file in `docs/` **must** begin with these fields immediately after the title:

```markdown
# Document Title

**Created_at:** YYYY-MM-DD  
**Updated_at:** YYYY-MM-DD  
**Status:** Active  
**Goal:** One-line description of what this document achieves  
**Scope:** Files, modules, or areas covered  

---
```

### Field Definitions

| Field | Required | Format | Description |
|-------|----------|--------|-------------|
| **Created_at** | ✅ | `YYYY-MM-DD` | Date the doc was originally created |
| **Updated_at** | ✅ | `YYYY-MM-DD` | Date the doc was last amended |
| **Status** | ✅ | One of the values below | Current state of the feature/document |
| **Goal** | ✅ | Single sentence | What this document aims to achieve or describe |
| **Scope** | ✅ | Comma-separated paths or areas | Which files, modules, or system areas this covers |

### Status Values

| Status | Meaning | When to Use |
|--------|---------|-------------|
| **Draft** | Incomplete, not yet reviewed | Initial braindumps, rough notes |
| **Planned** | Feature is designed but not yet started | Future feature specs |
| **In Progress** | Feature is being actively developed | Work-in-progress specs |
| **Active** | Feature is implemented, doc is current and accurate | Completed features — the doc is the living reference |

---

## Document Types

Docs generally fall into one of these categories. The frontmatter format is the same for all types — the distinction helps readers understand the doc's purpose:

| Type | Purpose | Examples |
|------|---------|---------|
| **Spec** | Design/plan for a feature to be built | `2026_03_03_debugging.md`, `2026_03_03_custom_themes.md` |
| **Guide** | How-to or explanation of an implemented feature | `2026_02_20_terminal.md`, `2026_02_27_startup.md` |
| **Reference** | Lookup tables, lists, catalogs | `2026_02_12_settings_reference.md`, `2026_02_20_supported_formats.md` |
| **Analysis** | Investigation, audit, or comparison | `2026_03_05_codebase_audit.md`, `2026_03_05_visual_glitch_analysis.md` |
| **Roadmap** | Future plans and priorities | `2026_02_08_gtk_editor_roadmap.md` |

---

## Placement and Naming

New project documentation must live under `docs/`. Do not create feature, design, architecture, investigation, or reference markdown files at the repository root or elsewhere outside the documentation tree.

Use these naming rules for new docs:

- `docs/YYYY_MM_DD_slug.md` for dated feature, architecture, guide, analysis, and reference docs
- `docs/standards/topic_name.md` for long-lived standards documents keyed by topic rather than date

Examples:

- `docs/2026_03_12_plugin_architecture.md`
- `docs/2026_03_05_codebase_audit.md`
- `docs/standards/spec_format.md`

---

## Full Example

```markdown
# Terminal

**Created_at:** 2026-03-08  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Document the integrated VTE terminal architecture, shortcuts, and theming  
**Scope:** `src/terminal/terminal_view.py`, `src/terminal/terminal_stack.py`  

---

## Overview

Zen IDE includes a fully integrated terminal powered by **VTE**...
```

---

## Rules for AI Agents

When creating or modifying documentation:

1. **Always include the frontmatter** — no doc should exist without Created_at, Updated_at, Status, Goal, and Scope
2. **Create new project docs only under `docs/`** — never add repo-root markdown specs or design notes
3. **Use a `YYYY_MM_DD_` prefix for new non-standard docs** so the knowledge base stays sortable by date
4. **Update Updated_at** when making any content changes (never change Created_at)
5. **Update the Status** when a feature's state changes (e.g., Planned → In Progress → Active)
6. **Keep Goal to one sentence** — if you need more, the doc itself provides the detail
7. **Be specific in Scope** — list actual file paths, not vague descriptions like "the editor"
