# 500-Line File Limit — Reorganisation Plan

**Created_at:** 2026-03-26
**Completed_at:** 2026-03-27
**Status:** Completed
**Goal:** Bring every source file under a 500-line maximum
**Scope:** All files in `src/` and `tests/`

---

## Overview

40 Python files originally exceeded 500 lines (12 exceeded 1 000 lines).
All have been split while preserving public APIs via `__init__.py` re-exports
and mixin inheritance patterns.

**Result:** 0 files over 500 lines. All existing tests pass (failures are
pre-existing missing dependencies: `tree_sitter`, `cmarkgfm`, `gh` CLI).

---

## Principles

1. **Extract by responsibility** — each module owns one concern (rendering, persistence, input, etc.)
2. **Preserve public API** — use `__init__.py` re-exports so existing imports don't break.
3. **Data near logic** — constants live alongside the code that uses them, not in a generic `constants.py`.
4. **Tests mirror source** — test splits follow the same boundaries as source splits.
5. **Mixin pattern** — large classes split via mixin inheritance to keep methods on `self`.

---

## Tier 1 — Critical (1 000+ lines) — DONE

### `editor_view.py` (4 143 lines) -> package `src/editor/editor_view/`

| Module | Lines | Responsibility |
|---|---|---|
| `__init__.py` | 37 | Re-export `EditorView`, `EditorTab`, `ZenSourceView` |
| `core.py` | 53 | Helper functions (`_iter_at_line`, etc.) |
| `highlighting.py` | 157 | Syntax highlighting & style schemes |
| `cursor.py` | 75 | `ZenSourceViewCursorMixin` — block cursor blink/draw |
| `gutters.py` | 251 | `ZenSourceViewGuttersMixin` — indent guides, diagnostic waves |
| `source_view.py` | 247 | `ZenSourceView` class composing cursor+gutter mixins |
| `input.py` | 478 | `EditorTabInputMixin` — key press, click, smart indent |
| `hover.py` | 420 | `EditorTabHoverMixin` — Cmd+hover underline, word nav |
| `theme.py` | 196 | `EditorTabThemeMixin` — theme application |
| `config.py` | 245 | `EditorTabConfigMixin` — view config, font, language detection |
| `editor_tab.py` | 476 | `EditorTab` class composing all tab mixins |
| `find.py` | 276 | `EditorViewFindMixin` — find & replace bar |
| `scroll.py` | 95 | `EditorViewScrollMixin` — smooth scroll, go-to-line |
| `tabs.py` | 487 | `EditorViewTabsMixin` — tab open/close/save |
| `file_openers.py` | 149 | `EditorViewFileOpenersMixin` — image, sketch, binary |
| `editor_view.py` | 490 | `EditorView` class composing all view mixins |

### `sketch_canvas.py` (2 596 lines) -> package `src/sketch_pad/canvas/`

| Module | Lines | Responsibility |
|---|---|---|
| `__init__.py` | 11 | Re-export `SketchCanvas` |
| `core.py` | 478 | Class shell, setup, properties, undo/redo |
| `rendering.py` | 500 | Shape drawing, grid, connections |
| `text_rendering.py` | 194 | Text cursor, text selection drawing |
| `interaction.py` | 431 | Click, drag, motion |
| `selection.py` | 130 | Select, resize handle hit-test |
| `keyboard.py` | 257 | Key handling, clipboard |
| `alignment.py` | 83 | Alignment guides, snapping |
| `pan_zoom.py` | 176 | Scroll, zoom, export |
| `text_editing.py` | 482 | Inline text editing |
| `helpers.py` | 10 | `_hex()` helper |

### `markdown_canvas.py` (2 120 lines) -> package `src/editor/preview/markdown_canvas/`

| Module | Lines | Responsibility |
|---|---|---|
| `__init__.py` | 11 | Re-export `MarkdownCanvas`, `_estimate_block_lines` |
| `core.py` | 377 | Class shell, `do_snapshot`, sizing |
| `block_layout.py` | 255 | Block positioning & culling |
| `text_renderer.py` | 473 | Heading/paragraph/list/code Pango rendering |
| `table_renderer.py` | 140 | Table layout & rendering |
| `media_renderer.py` | 421 | Image/emoji rendering |
| `scroll_sync.py` | 153 | Scroll-sync mapping |
| `selection.py` | 385 | Text selection, clipboard |

### `sketch_model.py` (1 629 lines) -> split by shape type

| Module | Lines | Responsibility |
|---|---|---|
| `sketch_model.py` | 67 | Thin re-export shim |
| `sketch_model_base.py` | 225 | `AbstractShape`, enums, constants |
| `sketch_model_rectangle.py` | 135 | `RectangleShape` |
| `sketch_model_arrow.py` | 356 | `ArrowShape` |
| `_arrow_routing.py` | 312 | Arrow routing functions |
| `sketch_model_actors.py` | 470 | `ActorShape`, `TopicShape`, `DatabaseShape`, `CloudShape` |
| `sketch_model_connection.py` | 216 | `Connection`, `Board` |

### `diff_view.py` (1 500 lines) -> mixin split

| Module | Lines | Responsibility |
|---|---|---|
| `diff_view.py` | 433 | Core `DiffView` widget |
| `diff_parser.py` | 312 | `DiffParserMixin` — parsing, tags, theme |
| `diff_gutter.py` | 412 | `RevertGutterRenderer`, `DiffMinimap`, `DiffGutterMixin` |
| `diff_navigation.py` | 398 | `DiffNavigationMixin` — commit history, find bar |

### `nvim_popup.py` (1 492 lines) -> mixin split

| Module | Lines | Responsibility |
|---|---|---|
| `nvim_popup.py` | 497 | `NvimPopup` base class |
| `border_overlay.py` | 129 | `_BorderOverlay` widget |
| `popup_anchor.py` | 407 | `PopupAnchorMixin` — positioning |
| `popup_styles.py` | 492 | `PopupStylesMixin` — CSS theme |

### `openapi_preview.py` (1 432 lines) -> split

| Module | Lines | Responsibility |
|---|---|---|
| `openapi_preview.py` | 444 | `OpenAPIPreview` widget |
| `openapi_renderer.py` | 318 | HTML rendering functions |
| `openapi_css.py` | 317 | CSS builder, HTML template |
| `openapi_schema_helpers.py` | 343 | Schema resolution helpers |
| `openapi_scroll_sync.py` | 108 | macOS WebKit helper |

### `test_sketch_pad.py` (1 214 lines) -> split into 3 files

- `test_shapes.py` (462), `test_board.py` (475), `test_canvas_integration.py` (298)

### `test_terminal_view.py` (1 126 lines) -> split into 3 files

- `test_path_patterns.py` (307), `test_vte_integration.py` (257), `test_scrolling.py` (500)

### `dev_pad.py` (1 055 lines) -> mixin split

- `dev_pad.py` (359), `activity_store.py` (246), `activity_renderer.py` (500)

### `python_provider.py` (1 043 lines) -> mixin split

- `python_provider.py` (197), `python_builtins.py` (124), `python_imports.py` (297), `python_members.py` (483)

### `markdown_preview.py` (1 016 lines) -> mixin split

- `markdown_preview.py` (414), `markdown_css.py` (381), `markdown_scroll_sync.py` (260)

### `ai_terminal_stack.py` (988 lines) -> mixin split

- `ai_terminal_stack.py` (454), `ai_tab_bar.py` (270), `ai_session_persistence.py` (294)

---

## Tier 2 — Large (700–999 lines) — DONE

| File | Split result |
|---|---|
| `window_state.py` (947) | `window_state.py` (326), `window_persistence.py` (160), `startup_optimizer.py` (483) |
| `test_python_provider.py` (945) | `test_imports.py` (184), `test_symbols.py` (304), `test_dot_access.py` (461) |
| `zen_ide.py` (886) | `zen_ide.py` (450), `app_preload.py` (197), `app_modules.py` (280) |
| `autocomplete.py` (880) | `autocomplete.py` (488), `completion_popup.py` (313), `completion_ranking.py` (166) |
| `markdown_block_renderer.py` (818) | `markdown_block_renderer.py` (373), `table_block.py` (373), `code_block.py` (106) |
| `window_layout.py` (816) | `window_layout.py` (364), `layout_css.py` (421), `layout_dnd.py` (48) |
| `tree_sitter_provider.py` (770) | `tree_sitter_provider.py` (87), `ts_python.py` (264), `ts_python_members.py` (390), `ts_javascript.py` (126) |
| `status_bar.py` (767) | `status_bar.py` (475), `status_indicators.py` (313) |
| `system_dialogs.py` (763) | `system_dialogs.py` (460), `recent_items.py` (164), `path_breadcrumb.py` (162) |
| `tree_panel.py` (733) | `tree_panel.py` (486), `tree_panel_data.py` (165), `tree_panel_selection.py` (110) |
| `global_search_dialog.py` (725) | `global_search_dialog.py` (453), `search_engine.py` (295) |
| `test_preview_scroll_mixin.py` (750) | `test_scroll_sync.py` (390), `test_heading_detection.py` (421) |

---

## Tier 3 — Medium (500–699 lines) — DONE

| File | Split result |
|---|---|
| `ai_terminal_view.py` (671) | `ai_terminal_view.py` (312), `cli_provider.py` (394) |
| `diagnostics_manager.py` (666) | `diagnostics_manager.py` (466), `linter_parsers.py` (225) |
| `test_autocomplete.py` (650) | `test_popup_nav.py` (419), `test_filtering.py` (284) |
| `test_navigation_edge_cases.py` (639) | `test_py_nav.py` (338), `test_js_nav.py` (175), `test_tf_nav.py` (179) |
| `inline_completion_provider.py` (629) | `inline_completion_provider.py` (323), `completion_cache.py` (325) |
| `test_openapi_scroll_sync.py` (628) | `test_endpoint_detection.py` (276), `test_scroll_mapping.py` (366) |
| `fold_manager.py` (613) | `fold_manager.py` (406), `fold_gutter.py` (219) |
| `utils.py` (610) | `utils.py` (397), `unicode_width.py` (61), `color_utils.py` (181) |
| `tab_title_inferrer.py` (598) | `tab_title_inferrer.py` (107), `title_patterns.py` (378) |
| `window_actions.py` (587) | `window_actions.py` (181), `file_actions.py` (235), `view_actions.py` (192) |
| `terminal_stack.py` (585) | `terminal_stack.py` (433), `terminal_tab_bar.py` (163) |
| `tree_view_actions.py` (561) | `tree_view_actions.py` (474), `tree_clipboard.py` (100) |
| `test_tree_view.py` (555) | `test_tree_selection.py` (397), `test_drag_drop.py` (182) |
| `code_navigation_py.py` (540) | `code_navigation_py.py` (306), `py_symbol_lookup.py` (244) |
| `font_picker_dialog.py` (532) | `font_picker_dialog.py` (353), `font_preview.py` (203) |
| `test_ai_terminal_spinner.py` (521) | `test_spinner_lifecycle.py` (281), `test_status_messages.py` (300) |

---

## Near-Limit Watch List (400–500 lines)

These files don't need splitting but should be monitored:

`test_scrolling.py` (500), `rendering.py` (500), `activity_renderer.py` (500),
`nvim_popup.py` (497), `test_markdown_scroll_sync.py` (493),
`popup_styles.py` (492), `test_ai_chat_restoration.py` (491),
`editor_view.py` (490), `autocomplete.py` (488), `tabs.py` (487),
`tree_panel.py` (486), `sketch_pad.py` (484), `git_manager.py` (483),
`startup_optimizer.py` (483), `python_members.py` (483),
`text_editing.py` (482), `canvas/core.py` (478), `input.py` (478),
`font_manager.py` (476), `editor_tab.py` (476), `status_bar.py` (475),
`tree_view_actions.py` (474).
