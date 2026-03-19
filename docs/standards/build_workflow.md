# Build Workflow — Makefile & Validation

**Created_at:** 2026-01-03  
**Updated_at:** 2026-03-09  
**Status:** Active  
**Goal:** Enforce Makefile as the single source of truth for all commands and require validation of breaking changes  
**Scope:** `Makefile`, all build/run/test/lint workflows  

---

## Makefile is the Source of Truth

**All commands, paths, and configurations must be driven by the Makefile.** Never bypass the Makefile for:

- Installing dependencies → `make install`
- Running the app → `make run`
- Testing → `make tests`
- Linting → `make lint`

If a new command or workflow is needed, **add it to the Makefile first**, then document it.

## Validate Breaking Changes

**Before returning control to the user, run `make run` if your changes could break the application.** This includes:

- Changes to UI components, widgets, or layouts
- Modifications to event handlers or keybindings
- Updates to imports, module structure, or initialization code
- Any changes to core functionality (editor, terminal, treeview, etc.)
