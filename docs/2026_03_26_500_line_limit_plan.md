# 500-Line File Limit — Reorganisation Plan

**Created_at:** 2026-03-26
**Status:** Proposed
**Goal:** Bring every source file under a 500-line maximum
**Scope:** All files in `src/` and `tests/`

---

## Overview

40 Python files currently exceed 500 lines (12 exceed 1 000 lines).
This plan describes how to split each one while preserving public APIs via
`__init__.py` re-exports.

---

## Principles

1. **Extract by responsibility** — each module owns one concern (rendering, persistence, input, etc.)
2. **Preserve public API** — use `__init__.py` re-exports so existing imports don't break.
3. **Data near logic** — constants live alongside the code that uses them, not in a generic `constants.py`.
4. **Tests mirror source** — test splits follow the same boundaries as source splits.

---

## Tier 1 — Critical (1 000+ lines)

### `editor_view.py` (4 085 lines)

Convert to package `src/editor/editor_view/`:

| Module | Responsibility |
|---|---|
| `__init__.py` | Re-export `EditorView` |
| `core.py` | Core class, buffer setup, basic properties |
| `highlighting.py` | Syntax highlighting & style schemes |
| `cursor.py` | Cursor rendering, blink, caret styles |
| `input.py` | Key/mouse event handling, shortcuts |
| `gutters.py` | Line numbers, fold markers, breakpoint gutter |
| `scroll.py` | Scroll behaviour, minimap sync |
| `theme.py` | Theme/CSS integration |
| `config.py` | Editor settings (tab width, wrap mode, etc.) |

### `sketch_canvas.py` (2 602 lines)

Convert to package `src/sketch_pad/canvas/`:

| Module | Responsibility |
|---|---|
| `core.py` | SketchCanvas class shell, setup, properties |
| `rendering.py` | GtkSnapshot shape drawing |
| `interaction.py` | Mouse drag, resize, select, marquee |
| `alignment.py` | Alignment guides, snapping |
| `pan_zoom.py` | Pan/zoom transforms |
| `text_editing.py` | Inline text editing on shapes |

### `markdown_canvas.py` (2 125 lines)

Convert to package `src/editor/preview/markdown_canvas/`:

| Module | Responsibility |
|---|---|
| `core.py` | MarkdownCanvas class, viewport, scroll |
| `block_layout.py` | Block positioning & culling |
| `text_renderer.py` | Heading/paragraph/list Pango rendering |
| `table_renderer.py` | Table layout & rendering |
| `media_renderer.py` | Image/emoji rendering |
| `scroll_sync.py` | Scroll-sync mapping |

### `sketch_model.py` (1 629 lines)

Split by shape type:

| Module | Responsibility |
|---|---|
| `base.py` | `Board`, `AbstractShape`, enums (`ToolMode`, `ArrowLineStyle`) |
| `rectangle.py` | `RectangleShape` |
| `arrow.py` | `ArrowShape`, arrow routing |
| `actors.py` | `ActorShape`, `TopicShape`, `DatabaseShape`, `CloudShape` |
| `connection.py` | `Connection`, serialisation helpers |

### `diff_view.py` (1 500 lines)

| Module | Responsibility |
|---|---|
| `diff_view.py` | Core DiffView widget, layout |
| `diff_parser.py` | Diff parsing & line alignment |
| `diff_gutter.py` | `RevertGutterRenderer`, revert button handling |
| `diff_navigation.py` | Commit history navigation |

### `nvim_popup.py` (1 486 lines)

| Module | Responsibility |
|---|---|
| `nvim_popup.py` | `NvimPopup` base class, focus/keyboard |
| `border_overlay.py` | `_BorderOverlay`, custom border drawing |
| `popup_anchor.py` | Anchored positioning, alignment calculations |

### `openapi_preview.py` (1 432 lines)

| Module | Responsibility |
|---|---|
| `openapi_preview.py` | `OpenAPIPreview` widget, spec parsing |
| `openapi_renderer.py` | Endpoint/schema/parameter rendering |
| `openapi_scroll_sync.py` | `OpenAPIScrollSync` |

### `test_sketch_pad.py` (1 214 lines)

Split into `test_shapes.py`, `test_board.py`, `test_canvas_integration.py`.

### `test_terminal_view.py` (1 126 lines)

Split into `test_path_patterns.py`, `test_vte_integration.py`, `test_scrolling.py`.

### `dev_pad.py` (1 055 lines)

Extract `activity_store.py` (storage/persistence) and `activity_renderer.py` (UI).

### `markdown_preview.py` (1 016 lines)

Extract `markdown_css.py` (CSS generation), `markdown_scroll_sync.py`.

### `ai_terminal_stack.py` (988 lines)

Extract `ai_tab_bar.py` (tab management), `ai_session_persistence.py`.

---

## Tier 2 — Large (700–999 lines)

| File (lines) | Split strategy |
|---|---|
| `python_provider.py` (951) | Extract `python_builtins.py`, `python_imports.py`, `python_members.py` |
| `window_state.py` (947) | Extract `window_persistence.py`, `startup_optimizer.py` |
| `test_python_provider.py` (945) | Split into `test_imports.py`, `test_symbols.py`, `test_dot_access.py` |
| `zen_ide.py` (886) | Extract `app_preload.py`, `app_modules.py` |
| `autocomplete.py` (875) | Extract `completion_popup.py`, `completion_ranking.py` |
| `markdown_block_renderer.py` (818) | Extract `table_block.py`, `code_block.py` |
| `window_layout.py` (816) | Extract `layout_css.py`, `layout_dnd.py` |
| `tree_sitter_provider.py` (770) | Per-language files: `ts_python.py`, `ts_javascript.py`, `ts_terraform.py` |
| `status_bar.py` (767) | Extract `status_indicators.py` |
| `system_dialogs.py` (763) | Extract `recent_items.py`, `path_breadcrumb.py` |
| `tree_panel.py` (733) | Extract `tree_renderer.py`, `tree_inline_edit.py` |
| `global_search_dialog.py` (715) | Extract `search_engine.py` (ripgrep integration/caching) |
| `test_preview_scroll_mixin.py` (750) | Split into `test_scroll_sync.py`, `test_heading_detection.py` |

---

## Tier 3 — Medium (500–699 lines)

| File (lines) | Split strategy |
|---|---|
| `ai_terminal_view.py` (671) | Extract `cli_provider.py` |
| `diagnostics_manager.py` (666) | Extract `linter_parsers.py` |
| `test_autocomplete.py` (650) | Split into `test_popup_nav.py`, `test_filtering.py` |
| `test_navigation_edge_cases.py` (639) | Split into `test_py_nav.py`, `test_js_nav.py`, `test_tf_nav.py` |
| `inline_completion_provider.py` (629) | Extract `completion_cache.py` |
| `test_openapi_scroll_sync.py` (628) | Split into `test_endpoint_detection.py`, `test_scroll_mapping.py` |
| `tab_title_inferrer.py` (598) | Extract `title_patterns.py` |
| `window_actions.py` (587) | Extract `file_actions.py`, `view_actions.py` |
| `terminal_stack.py` (585) | Extract `terminal_tab_bar.py` |
| `utils.py` (579) | Extract `unicode_width.py`, `color_utils.py` |
| `tree_view_actions.py` (561) | Extract `tree_clipboard.py` |
| `test_tree_view.py` (555) | Split into `test_tree_selection.py`, `test_drag_drop.py` |
| `code_navigation_py.py` (540) | Extract `py_symbol_lookup.py` |
| `font_picker_dialog.py` (532) | Extract `font_preview.py` |
| `test_ai_terminal_spinner.py` (521) | Split into `test_spinner_lifecycle.py`, `test_status_messages.py` |

---

## Near-Limit Watch List (400–500 lines)

These 12 files don't need splitting today but should be monitored:

`test_markdown_scroll_sync.py` (493), `test_ai_chat_restoration.py` (491),
`sketch_pad.py` (484), `git_manager.py` (483), `font_manager.py` (476),
`test_tree_sitter_navigation.py` (474), `system_monitor.py` (454),
`tree_sitter_semantic.py` (446), `copilot_api.py` (424),
`test_semantic_highlight.py` (408), `openapi_block_renderer.py` (408),
`tree_panel_drag.py` (403).

---

## Suggested Execution Order

1. `editor_view.py` — largest file, highest impact
2. `sketch_canvas.py` + `sketch_model.py` — tightly coupled, split together
3. Preview renderers (`markdown_canvas.py`, `markdown_preview.py`, `openapi_preview.py`)
4. Popup system (`nvim_popup.py`, `system_dialogs.py`, `global_search_dialog.py`)
5. AI subsystem (`ai_terminal_stack.py`, `ai_terminal_view.py`, `dev_pad.py`)
6. Autocomplete (`autocomplete.py`, `python_provider.py`, `tree_sitter_provider.py`)
7. Window mixins (`window_state.py`, `window_layout.py`, `window_actions.py`)
8. Remaining medium files and tests
