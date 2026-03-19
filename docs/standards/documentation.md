# Documentation Alignment

**Created_at:** 2026-02-08  
**Updated_at:** 2026-03-12  
**Status:** Active  
**Goal:** Ensure documentation stays continuously aligned with code changes  
**Scope:** `README.md`, `AGENTS.md`, all files in `docs/`  

---

## Rule

**Continuously align documentation whenever relevant changes are made.** If AI work affects behavior, workflows, architecture, commands, or UX, update the related documentation in the same task, including:

- `README.md`
- `AGENTS.md`
- relevant files in `docs/`

## Spec Format

**All docs must follow the standard format** defined in [docs/standards/spec_format.md](spec_format.md). Every doc requires **Created_at**, **Updated_at**, **Status**, **Goal**, and **Scope** frontmatter fields. When creating new docs, copy the template from the spec. When updating existing docs, update **Updated_at** and keep **Created_at** unchanged.

## Location and Naming

Create new project documentation only under `docs/`. Do not leave feature specs, architecture notes, investigations, or reference markdown files at the repository root or in other top-level folders.

For new non-standard docs, use the filename pattern `docs/YYYY_MM_DD_slug.md`. Standards docs remain in `docs/standards/` and are named by topic instead of date.
