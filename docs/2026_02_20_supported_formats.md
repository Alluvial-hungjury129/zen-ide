# Supported File Formats & Languages

**Created_at:** 2026-02-20  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** List all file types, languages, and viewer modes supported by Zen IDE  
**Scope:** 50+ languages, markdown/HTML/OpenAPI previews, image/hex viewers  

---

Reference of all file types and formats Zen IDE can open, with the level of support each receives.

---

## Viewer Modes

| Mode | Description |
|------|-------------|
| **Editor** | Full text editing with syntax highlighting |
| **Split Preview** | Side-by-side editor + live rendered preview |
| **Image Viewer** | Read-only image display (Gtk.Picture) |
| **Hex Viewer** | Read-only hex dump with ASCII column |

---

## Special File Viewers

### Markdown (Split Preview)
| Extension | Preview Engine |
|-----------|---------------|
| `.md`, `.markdown` | GitHub Flavored Markdown via cmarkgfm |

- Side-by-side editor + live preview (300ms debounce)
- Backends: WebKitGTK (Linux), WKWebView (macOS), GtkTextView fallback

### HTML (Split Preview)
| Extension | Preview Engine |
|-----------|---------------|
| `.html`, `.htm`, `.xhtml` | WebKit browser rendering |

- Side-by-side editor + live preview (300ms debounce)
- Backends: WebKitGTK (v6.0/v4.1/v4.0), WKWebView (macOS), plain editor fallback

### OpenAPI / Swagger (Split Preview)
| Extension | Detection |
|-----------|-----------|
| `.yaml`, `.yml`, `.json` | Content-based (looks for `openapi:` or `swagger:` keys) |

- Interactive preview with endpoints, schemas, and API info
- 500ms debounce for live preview

### Images (Image Viewer)
| Extensions |
|-----------|
| `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.ico`, `.webp`, `.tiff`, `.tif`, `.svg` |

- Content-fit with preserved aspect ratio
- Scrollable, read-only

### Binary Files (Hex Viewer)
| Detection | Max Size |
|-----------|----------|
| Null-byte scanning | 10 MB |

- 16 bytes per row, offset + hex + ASCII columns
- Read-only, scrollable

### Workspace Files (Editor)
| Extension | Compatibility |
|-----------|--------------|
| `.zen-workspace` | Zen IDE native format |
| `.code-workspace` | Legacy workspace format |

- JSON-based multi-root workspace definitions
- Supports relative and absolute folder paths
- Tolerates comments and trailing commas in workspace files
- Tab displays workspace name (without extension)
- Status bar shows "workspace" as file type

---

## Programming Languages

### Full Support (Syntax + Regex Navigation + Semantic Highlighting)

| Language | Extensions | Navigation | Notes |
|----------|-----------|------------|-------|
| **Python** | `.py` | ✅ Go-to-definition, import resolution | Smart indent, decorator support, semantic class/function call highlighting |

### Syntax Highlighting Only

These languages get GtkSourceView syntax highlighting but no code navigation:

| Language | Extensions |
|----------|-----------|
| **HTML** | `.html`, `.htm`, `.xhtml` |
| **CSS** | `.css` |
| **Markdown** | `.md`, `.markdown` |
| **YAML** | `.yaml`, `.yml` |
| **TOML** | `.toml` |
| **SQL** | `.sql` |
| **Kotlin** | `.kt` |
| **Swift** | `.swift` |
| **Lua** | `.lua` |
| **R** | `.r` |
| **Terraform / HCL** | `.tf` (2-space indent) |
| **Clojure** | `.clj`, `.cljs`, `.cljc`, `.edn` (2-space indent, custom lang spec) |
| **XML** | `.xml`, `.plist`, `.svg`, `.xsd`, `.xsl`, `.xslt`, `.wsdl`, `.glade`, `.rss` |
| **Dockerfile** | `Dockerfile` (filename) |
| **Makefile** | `Makefile` (filename) |
| **CMake** | `CMakeLists.txt` (filename) |

> GtkSourceView provides built-in highlighting for 100+ additional languages beyond this list. Any language supported by GtkSourceView will get basic syntax coloring automatically.

---

## Editor Features (All Text Files)

| Feature | Description |
|---------|-------------|
| Syntax highlighting | Dynamic theme-based via GtkSourceView |
| Minimap | Code overview sidebar |
| Git gutter | Add/delete/change indicators |
| Color preview | Inline hex color swatches |
| Search & replace | Case-insensitive, wrap-around |
| Go-to-line | `Ctrl+G` |
| Comment toggle | `Ctrl+/` |
| Bracket auto-close | `(`, `[`, `{`, `"`, `'` |
| Indent/unindent | `Tab` / `Shift+Tab` |
| Autocomplete | IntelliSense-style completions |
| Dev Pad logging | File activity tracking |

---

## Diff Viewing

| Feature | Description |
|---------|-------------|
| Side-by-side diff | Color-coded add/delete/change regions |
| Inline revert | Per-region revert buttons |
| Commit history | Navigate through git history |
| Gutter indicators | Green (add), red (delete), yellow (change) |

---

## File Type Detection Priority

1. Image extension check → Image Viewer
2. Binary detection (null-byte scan) → Hex Viewer
3. OpenAPI content detection → Split Preview
4. Markdown/HTML extension → Split Preview
5. GtkSourceView language detection → Editor with syntax highlighting
6. Filename-based mapping (`Makefile`, `Dockerfile`, etc.)
7. Extension-based fallback table
8. Plain text fallback

---

## Theme Support

26 built-in themes with dynamic syntax scheme generation:
Dracula, Gruvbox, Tokyo Night, Catppuccin, One Dark, Solarized, Nord, and more.

Each theme provides consistent coloring across all supported languages via core token mappings (`keyword`, `type`, `function`, `string`, `comment`, `number`, `operator`, etc.).
