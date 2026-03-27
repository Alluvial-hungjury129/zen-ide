# Documentation Alignment

**Created_at:** 2026-02-08  
**Updated_at:** 2026-03-27
**Status:** Active
**Goal:** Ensure documentation stays continuously aligned with code changes
**Scope:** `README.md`, `AGENTS.md`, `docs/`, `docs/wiki/`

---

## Rule

**Continuously align documentation whenever relevant changes are made.** If AI work affects behavior, workflows, architecture, commands, or UX, update the related documentation in the same task across all relevant surfaces:

- `README.md`
- `AGENTS.md`
- relevant files in `docs/`
- relevant files in `docs/wiki/`

## Scope of Each Surface

Each documentation surface has a different audience and level of detail:

| Surface | Audience | Tone | Detail Level | Links to |
|---------|----------|------|-------------|----------|
| **README.md** | Humans (new users, contributors) | Synthetic, concise — avoid bloating | Minimal: what it is, how to install, how to run | Wiki only (never `docs/`) |
| **AGENTS.md** | AI agents | Technical, direct | Enough for an agent to navigate the codebase; link to `docs/` for deep dives | `docs/` |
| **docs/** | Developers (technical reference) | Exhaustive, technical | Full detail: how features work from a technical POV, architecture, edge cases | Other `docs/` files |
| **docs/wiki/** | End users | User-friendly, detailed | What the IDE offers, how to use it, practical examples | Other wiki pages |

**Key constraint:** `README.md` must only link to `docs/wiki/`, never directly to `docs/`. The wiki is the user-facing documentation; `docs/` is the internal technical reference.

## Spec Format

**All docs must follow the standard format** defined in [docs/standards/spec_format.md](spec_format.md). Every doc requires **Created_at**, **Updated_at**, **Status**, **Goal**, and **Scope** frontmatter fields. When creating new docs, copy the template from the spec. When updating existing docs, update **Updated_at** and keep **Created_at** unchanged.

## Location and Naming

Create new project documentation only under `docs/`. Do not leave feature specs, architecture notes, investigations, or reference markdown files at the repository root or in other top-level folders.

For new non-standard docs, use the filename pattern `docs/YYYY_MM_DD_slug.md`. Standards docs remain in `docs/standards/` and are named by topic instead of date.
