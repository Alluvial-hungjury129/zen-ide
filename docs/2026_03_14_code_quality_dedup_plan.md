# Code Quality Deduplication and Reuse Plan

**Created_at:** 2026-03-14  
**Updated_at:** 2026-03-14  
**Status:** In Progress  
**Goal:** Reduce duplication and dead code by centralizing repeated logic and removing unused variables in high-churn modules  
**Scope:** `src/ai/`, `src/editor/`, `src/terminal/`, `src/treeview/`, `src/shared/`, selected `tests/` modules  

---

## Context

This plan is based on targeted static scans for:

- Unused locals / dead assignments (`ruff` `F841`)
- Repeated helper implementations with identical bodies
- Repeated broad exception patterns that hide intent (`except Exception as e:`)

Current signal:

- `ruff` reports **87** issues for selected rules, mostly `F841` unused locals
- `except Exception as e:` appears broadly across runtime modules
- Duplicate helper bodies exist in click-hit-testing and focus/panel event handlers

---

## Outcomes

1. Remove low-value unused locals and stale variables that increase maintenance cost.
2. Consolidate repeated helper logic into shared utilities where behavior is truly identical.
3. Keep behavior unchanged while reducing copy-paste risk across AI/chat/editor/terminal surfaces.
4. Leave a clean follow-up backlog for deeper architectural deduplication.

---

## Prioritized Work Plan

### Phase 1 — Safe cleanup (fast, low risk)

Focus: deterministic `F841` cleanups with no behavior change.

- Replace unused exception variable bindings:
  - Convert `except Exception as e:` to `except Exception:` where `e` is not used
  - Keep explicit logging/reporting where variables are used
- Remove or inline clearly unused temporary locals (examples from scan):
  - `src/ai/ai_chat_terminal.py` (`cols`, `raw_len`, `ansi_fg`)
  - `src/editor/editor_view.py` (`w`, `h`, `vadj`)
  - `src/main/window_layout.py` (`term_font_size`)
  - `src/terminal/terminal_stack.py` (`cwd`, `terminal_number`)

Acceptance check:

- `uv run ruff check src tests --select F841` passes or has only intentional/test-scaffold exceptions.

---

### Phase 2 — Shared UI event helper extraction (medium impact)

Focus: move repeated GTK event detection helpers into one shared utility.

Known duplicates:

- `_is_button_click` in:
  - `src/ai/ai_chat_terminal.py`
  - `src/ai/ai_chat_tabs.py`
  - `src/terminal/terminal_stack.py`
- `_is_click_inside_widget` in:
  - `src/ai/ai_chat_tabs.py`
  - `src/terminal/terminal_stack.py`
- Panel focus/click handlers duplicated across:
  - `src/treeview/tree_view.py`
  - `src/editor/editor_view.py`

Plan:

- Introduce a shared module under `src/shared/` for GTK pointer/click hit-test helpers.
- Replace local nested helper clones with shared calls.
- Preserve existing call sites and signal wiring to avoid behavior drift.

Acceptance check:

- No change in click behavior for chat tabs, terminal tabs, or panel focus tracking.
- Existing tests touching panel focus and tab interactions continue to pass.

---

### Phase 3 — Exception policy normalization (medium risk, staged)

Focus: tighten broad exception usage without introducing regressions.

- Audit each `except Exception as e:` occurrence:
  - Keep broad catches only for explicit boundary layers (UI event callbacks, external CLI/process edges)
  - Narrow to concrete exceptions where feasible
  - Ensure every kept broad catch has a clear error path (log/notify/fallback by design)

Acceptance check:

- No silent failure paths added.
- Runtime error reporting remains visible in AI/chat/editor pathways.

---

### Phase 4 — Test fixture/helper dedup (low-medium)

Focus: deduplicate repeated test helper bodies found by AST scan.

Examples:

- Repeated scroll adjustment stubs (`get_value/get_upper/get_page_size`) across terminal/editor preview tests.
- Repeated setup scaffolding in inline completion provider tests.
- Repeated ANSI stripping helpers in terminal markdown renderer tests.

Plan:

- Extract shared test helpers into local test utility modules per domain (editor/terminal/ai).
- Keep test readability by avoiding over-abstraction.

Acceptance check:

- Test files shrink in repeated boilerplate.
- `make tests` remains green.

---

## Execution Order

1. Phase 1 (F841 cleanup)
2. Phase 2 (shared event helpers)
3. Phase 4 (test helper dedup)
4. Phase 3 (exception narrowing, performed last and incrementally)

This order maximizes safety: first remove noise, then deduplicate behavior-preserving helpers, then address higher-risk exception policy changes.

---

## Validation Commands

Use Makefile-first workflow where available:

```bash
make lint
make tests
```

For focused checks during implementation:

```bash
uv run ruff check src tests --select F841
uv run ruff check src tests --select F401,F841,F821
```

---

## Tracking Backlog (Initial)

- [x] P1.1 Remove unused exception bindings in `src/ai/` and `src/editor/`
- [x] P1.2 Remove stale temporary locals reported by `F841`
- [x] P2.1 Add shared click-hit-test helper in `src/shared/`
- [x] P2.2 Replace duplicated `_is_button_click` / `_is_click_inside_widget` call sites
- [x] P2.3 Deduplicate panel click/focus handlers between editor and tree view
- [x] P4.1 Extract repeated preview/terminal test adjustment stubs
- [x] P4.2 Extract repeated inline-completion test setup scaffolding
- [x] P3.1 Classify all broad catches by boundary vs internal logic
- [x] P3.2 Narrow eligible broad catches and keep explicit error surfacing

## Execution Notes (2026-03-14)

- Applied automated and manual `F841` cleanup; `ruff` focused checks now pass.
- Added `src/shared/gtk_event_utils.py` and migrated click-hit-test call sites in:
  - `src/ai/ai_chat_tabs.py`
  - `src/ai/ai_chat_terminal.py`
  - `src/terminal/terminal_stack.py`
- Validation run completed successfully via `make lint` and `make tests`.
- P2.3: deduplicated panel click/focus behavior through shared `FocusBorderMixin` handlers, and reused these in `editor_view.py` and `tree_view.py`.
- P4.1: extracted shared scroll test stubs/helpers into `tests/editor/preview_scroll_test_helpers.py` and reused them across markdown/openapi/preview mixin tests.
- P4.2: extracted shared inline-completion test setup into `tests/editor/inline_completion/test_helpers.py` and migrated provider/context/manager tests to use it.
- P3.1/P3.2: classified broad catches as boundary vs internal in updated codepaths, narrowed eligible broad catches (`binary_viewer`, `ai_chat_terminal`, `pty_cli_provider`, `sketch_pad`) and added explicit error surfacing/logging for callback boundaries (`focus_manager`) and dialog/file operations (`sketch_pad`).
