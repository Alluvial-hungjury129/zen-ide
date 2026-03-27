# Editor

The editor is the heart of Zen IDE — a GtkSourceView 5-based code editor with syntax highlighting for 100+ languages, AI inline completions, and a rich set of editing features.

## Opening Files

| Method | How |
|---|---|
| Quick Open | `Cmd+P` — fuzzy finder across all workspace files |
| Tree View | Click a file in the left sidebar |
| Terminal | `Cmd+Click` on a file path in terminal output |
| CLI | `code myfile.py` from any terminal |
| Drag & Drop | Drag files onto the editor window |

Files open in tabs. Switch between tabs by clicking or with standard `Cmd+1`–`Cmd+9` shortcuts.

## Syntax Highlighting

Zen supports **100+ languages** via GtkSourceView language specs. Language is auto-detected by file extension and content type.

**Enhanced semantic highlighting** is available for:
- Python
- JavaScript / TypeScript
- Terraform

Semantic highlighting overlays extra colours for variables, parameters, decorators, and type annotations beyond standard syntax colouring.

## Find & Replace

Open with `Cmd+F`. Features:
- **Regex mode** — toggle with the `.*` button
- **Case sensitivity** — toggle with the `Aa` button
- **Find next / previous** — `Cmd+G` / `Cmd+Shift+G`
- **Replace** / **Replace All**

## Code Editing Features

### Comments
- `Cmd+/` — Toggle line comment (supports all languages with comment syntax)

### Indentation
- `Cmd+]` — Indent selected lines
- `Cmd+[` — Unindent selected lines
- **Smart indent** — Auto-indentation based on language context (after `{`, `:`, etc.)
- **Indent guides** — Vertical lines showing nesting depth (toggle in settings)

### Bracket Matching
- Matching brackets are automatically highlighted when the cursor is on one
- **Auto-close brackets** — Typing `(`, `[`, `{`, `"`, `'`, or `` ` `` auto-inserts the closing character

### Selections
- `Cmd+A` — Select all
- `Cmd+X` — Cut line (or selection)
- `Cmd+C` — Copy line (or selection)
- `Cmd+D` — Select next occurrence of current word

## Minimap

A code overview on the right side of the editor showing a miniature rendering of your file. Click to jump to a position.

Toggle via settings: `editor.show_minimap`

## Code Folding

Collapse multi-line blocks (functions, classes, loops, objects, etc.) to a single header line. Fold regions are detected automatically using tree-sitter for Python, JavaScript, TypeScript, and TSX, and brace/bracket matching for JSON and other languages.

**Fold chevrons** appear in the line number gutter on hover:
- Click a **down chevron** (▾) to collapse a block
- Click a **right chevron** (▸) to expand it — collapsed chevrons are always visible
- Chevrons fade in/out on gutter hover (~200ms animation)

**Behaviour:**
- Folded content is completely hidden — the header line remains visible
- If the cursor is inside a collapsed region (e.g. via find or go-to-line), the fold auto-expands
- Collapsed state is preserved across edits (matched by proximity within ±2 lines)
- Fold regions recompute on buffer change (500ms debounce)

**Supported languages:**

| Detection | Languages |
|---|---|
| Tree-sitter AST | Python, JavaScript, TypeScript, TSX |
| Brace/bracket matching | JSON and all other languages |

Fold chevron visibility is controlled by `editor.show_line_numbers` — when line numbers are hidden, fold chevrons are also hidden.

## Line Numbers

Shown by default in the left gutter. Also controls fold chevron visibility. Toggle via settings: `editor.show_line_numbers`

## Gutter Diff Indicators

The line number gutter shows coloured markers for git changes:

| Colour | Meaning |
|---|---|
| 🟢 Green | Added lines |
| 🟡 Yellow | Modified lines |
| 🔴 Red | Deleted lines |

## Colour Preview

Hex colour codes (e.g., `#ff5733`) and `rgb()` values display an inline colour swatch. Click the swatch to open the colour picker popup and edit the colour visually.

## Format on Save

When enabled (default: `true`), files are auto-formatted on save using external formatters:

| Extension | Default Formatter |
|---|---|
| `.py` | `ruff format` |
| `.js`, `.ts`, `.jsx`, `.tsx` | `prettier` |
| `.json` | Built-in (2-space indent) |

Configure custom formatters in settings — see [Formatters & Linters](Formatters-and-Linters).

## File Previews

Certain file types open in split view with a live preview alongside the editor:

| File Type | Preview |
|---|---|
| `.md`, `.markdown` | **Markdown Preview** — rendered HTML with syntax-highlighted code blocks |
| `.json`, `.yaml` (OpenAPI) | **OpenAPI/Swagger Viewer** — endpoints with coloured HTTP method badges |
| `.html` | **HTML Preview** — rendered via WebKit |
| `.png`, `.jpg`, `.gif`, `.svg`, `.webp` | **Image Viewer** |
| Binary files | **Hex Viewer** — offset + hex dump + ASCII |
| `.zen_sketch` | **Sketch Pad** — ASCII diagram editor |

### Markdown Preview

Markdown files open in a split view: editor on the left, rendered preview on the right. The preview:
- Uses GitHub Flavoured Markdown (GFM)
- Syntax-highlights code blocks
- Respects the current theme colours
- Scrolls in sync with the editor

### OpenAPI Preview

JSON/YAML files containing OpenAPI specs display a formatted endpoint list:
- **GET** endpoints in blue
- **POST** in green
- **PUT** in yellow
- **DELETE** in red
- **PATCH** in cyan
- Request/response schemas shown inline

## Word Wrap

Toggle via settings: `editor.word_wrap` (default: `false`)

## Scroll Past End

Allows scrolling past the last line of the file so it can appear in the centre of the screen. Toggle via settings: `editor.scroll_past_end` (default: `true`)

## Editor Settings Summary

| Setting | Default | Description |
|---|---|---|
| `editor.tab_size` | `4` | Spaces per tab stop |
| `editor.insert_spaces` | `true` | Use spaces instead of tabs |
| `editor.show_line_numbers` | `true` | Show line number gutter |
| `editor.highlight_current_line` | `true` | Highlight cursor line |
| `editor.word_wrap` | `false` | Wrap long lines |
| `editor.show_indent_guides` | `true` | Vertical indent lines |
| `editor.show_minimap` | `true` | Code minimap |
| `editor.scroll_past_end` | `true` | Scroll past end of file |
| `editor.auto_close_brackets` | `true` | Auto-insert closing brackets/quotes |
| `editor.auto_complete_on_type` | `false` | Trigger autocomplete after 3+ chars |
| `editor.format_on_save` | `true` | Auto-format on save |
| `editor.font_ligatures` | `false` | Enable OpenType ligatures |
| `editor.letter_spacing` | `0.3` | Extra letter spacing (pixels) |
