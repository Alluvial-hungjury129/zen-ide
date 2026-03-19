# Indent System

**Created_at:** 2026-02-19  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Document indentation editing, smart auto-indent, and visual indent guides  
**Scope:** `src/editor/editor_view.py`, `src/constants.py`, indent configuration  

---

The Zen IDE indent system handles three concerns: **indentation editing** (inserting/removing whitespace), **smart indentation** (language-aware auto-indent on Enter), and **indent guides** (visual vertical lines showing nesting depth).

---

## Configuration

All indent constants live in `src/constants.py`:

| Constant | Default | Purpose |
|----------|---------|---------|
| `DEFAULT_INDENT_WIDTH` | `4` | Spaces per indent level (all languages) |
| `LANG_INDENT_WIDTH` | `{"hcl": 2, ".tf": 2}` | Per-language/extension overrides |
| `INDENT_GUIDE_ALPHA` | `1.00` | Opacity of indent guide lines |
| `NO_INDENT_GUIDE_LANGS` | markdown, txt, plain, … | Languages that skip indent guides |

The `show_indent_guides` boolean in `settings_manager.py` controls whether guides are drawn at all.

Each theme defines an `indent_guide` color in its `ThemeModel` (see `src/themes/theme_model.py`).

---

## Per-Language Indent Width

When a file is opened, `EditorTab._set_language_from_file()` resolves the indent width:

```
indent = LANG_INDENT_WIDTH[lang_id] or LANG_INDENT_WIDTH[extension] or DEFAULT_INDENT_WIDTH
```

Both `tab_width` and `indent_width` on the `GtkSourceView` are set to this value, ensuring Tab key, auto-indent, and visual tab stops all agree.

### Tab-Only Languages

Some languages require **real tab characters** instead of spaces (e.g., Makefiles, where indentation with spaces is a syntax error). These are listed in `TAB_ONLY_LANGS` in `constants.py`.

When a file's language ID is in `TAB_ONLY_LANGS`, the editor sets `insert_spaces_instead_of_tabs` to `False`, so pressing Tab inserts a real `\t` character. For all other languages, spaces are used as usual.

---

## Indentation Editing (Tab / Shift-Tab)

**Keybindings** (defined in `src/keybindings.py`):

| Action | Shortcut |
|--------|----------|
| Indent | `Cmd+]` / `Ctrl+]` |
| Unindent | `Cmd+[` / `Ctrl+[` |

The `EditorView.indent()` / `unindent()` methods delegate to `_indent_lines(indent: bool)`:

1. Determines the affected lines (selection or current line).
2. Wraps all changes in `begin_user_action()` / `end_user_action()` (single undo step).
3. **Indent**: prepends `" " * tab_width` to each line.
4. **Unindent**: removes up to `tab_width` leading spaces (or one tab character) from each line.

GtkSourceView's built-in `auto_indent` and `indent_on_tab` are also enabled, so pressing Tab at the start of a line inserts one indent level and Enter preserves the current indentation.

---

## Smart Indentation (Python)

`EditorTab._handle_smart_indent()` intercepts Enter key presses **only for Python files** (`python` / `python3` language IDs). It provides two behaviours:

### Auto-indent after openers
If the line (before cursor) ends with `:`, `(`, `[`, or `{`, the new line gets **one extra indent level**:

```python
def foo():      # cursor here, press Enter
    |           # cursor lands here (indented)
```

### Auto-dedent after keywords
If the first word on the line is `return`, `break`, `continue`, `pass`, or `raise`, the new line gets **one fewer indent level**:

```python
    return 42   # cursor here, press Enter
|               # cursor lands here (dedented)
```

For all other cases, GtkSourceView's default auto-indent (copy previous line's whitespace) takes over.

---

## Indent Guides (Visual Lines)

Indent guides are thin vertical lines drawn at each indent level to visualise code nesting. They are rendered by `ZenSourceView`, a custom subclass of `GtkSource.View`.

### Architecture

```
ZenSourceView (src/editor/editor_view.py)
  ├── _draw_indent_guides_snapshot()   # rendering
  ├── _compute_indent_step()           # detect indent step from file content
  └── set_guide_color_hex()            # theme integration

indent_guide_levels.py (src/editor/indent_guide_levels.py)
  ├── compute_indent_step()            # GCD-based indent detection
  └── compute_guide_levels()           # per-line guide level calculation
      ├── _raw_indents()               # measure leading whitespace per line
      └── _interpolate_blanks()        # fill blank lines from neighbours
```

### Indent Step Detection

The indent step (how many columns = one indent level) is **auto-detected from file content**, not assumed from `tab_width`:

1. Scan all non-blank lines and collect their leading whitespace widths.
2. Compute the GCD of all those widths.
3. **Heuristic**: if the GCD is smaller than `tab_width` but fewer than 20% of lines are misaligned, prefer `tab_width` (avoids a single odd line forcing 1-space guides).
4. Floor the result to a minimum of 2.

The result is **cached** in `_cached_indent_step` and invalidated on every buffer change (`_on_buf_content_changed`).

### Per-Line Guide Levels

`compute_guide_levels()` returns a list of integers (one per line), where level _n_ means _n_ vertical guide lines should be drawn:

1. Measure the raw indent (in columns) for each line; blank lines get `-1`.
2. Divide each indent by `indent_step` to get the level.
3. **Blank-line interpolation**: blank lines inherit `min(above, below)` from their nearest non-blank neighbours, so guides flow smoothly through empty lines.

### Rendering Pipeline

On every `snapshot()` call (GTK4 draw cycle):

1. Skip if guides are disabled or the language is in `NO_INDENT_GUIDE_LANGS`.
2. Determine the **visible line range** from the scroll position.
3. Extract text for those lines (plus 1 line of context each side).
4. Call `compute_guide_levels()` to get per-line levels.
5. For each visible line with level > 0, draw 1px-wide coloured rectangles at each guide column using `snapshot.append_color()`.

Guide colour and alpha come from the active theme via `set_guide_color_hex()`, called during theme application in `EditorTab._apply_theme()`.

### Excluded Languages

Non-coding file types (markdown, plain text, LaTeX, etc.) skip indent guides entirely — defined in `NO_INDENT_GUIDE_LANGS` in `constants.py`.

---

## File Map

| File | Responsibility |
|------|----------------|
| `src/constants.py` | `DEFAULT_INDENT_WIDTH`, `LANG_INDENT_WIDTH`, `TAB_ONLY_LANGS`, `INDENT_GUIDE_ALPHA`, `NO_INDENT_GUIDE_LANGS` |
| `src/keybindings.py` | `INDENT` / `UNINDENT` key bindings |
| `src/editor/editor_view.py` | `ZenSourceView` (guide rendering), `EditorTab` (indent/unindent, smart indent, per-language width) |
| `src/editor/indent_guide_levels.py` | Pure-logic indent step detection and per-line guide level computation |
| `src/themes/theme_model.py` | `indent_guide` colour field in `ThemeModel` |
| `src/shared/settings_manager.py` | `show_indent_guides` user setting |
