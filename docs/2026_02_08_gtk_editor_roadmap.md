# GTK Editor Roadmap

**Created_at:** 2026-02-08  
**Updated_at:** 2026-03-08  
**Status:** In Progress  
**Goal:** Plan implementation of autocomplete, go-to-definition, hover docs, and cross-file navigation  
**Scope:** GtkSourceView 5, LSP integration  

---

## Current State

The GTK4 editor uses **GtkSourceView 5**, which provides:

- ✅ Syntax highlighting (lexical/token-based)
- ✅ Line numbers
- ✅ Indent guides
- ✅ Undo/redo
- ✅ Search/replace
- ✅ Bracket matching
- ✅ Basic auto-indent

## Missing Features (Need Implementation)

GtkSourceView is purely an editor widget—it does **not** provide intellisense or cross-file navigation out of the box.

### 1. Autocomplete

**What:** Show completion suggestions as user types (variables, functions, imports, etc.)

**Options:**
- Implement `GtkSourceCompletionProvider` interface for custom completions
- Integrate LSP client for language-aware completions

---

### 2. Go-to-Definition

**What:** Cmd+Click on symbol to jump to its definition (same file or different file)

**Options:**
- Integrate LSP client (`textDocument/definition` request)
- Custom symbol indexing per language

---

### 3. Hover Documentation

**What:** Show type info and docstrings when hovering over symbols

**Options:**
- LSP client (`textDocument/hover` request)
- Custom tooltip with `Gtk.Popover`

---

### 4. Cross-File Navigation

**What:** Navigate between files based on imports, references, symbol definitions

**Options:**
- LSP client for full project awareness
- Custom import parsing and file resolution

---

### 5. Symbol Search (Cmd+Shift+O)

**What:** Quick jump to symbols (functions, classes) in current file or workspace

**Options:**
- LSP client (`textDocument/documentSymbol`, `workspace/symbol`)
- Custom parsing with regex

---

### 6. Color Preview (Inline Color Swatches)

**What:** Show inline color previews for hex codes (`#FF5733`), RGB (`rgb(255, 87, 51)`), and named colors in CSS/code

**Options:**
- Custom `GtkSourceGutterRenderer` to draw color swatches in gutter
- Inline widget overlay next to color values
- Underline/background decoration with the actual color
- Color picker popup on click to modify the color

**Implementation Ideas:**
- Regex to detect color patterns: `#[0-9A-Fa-f]{3,8}`, `rgb\(`, `rgba\(`, `hsl\(`
- Draw small colored rectangle inline or in margin
- Click to open `Gtk.ColorChooserDialog` for editing

**Reference:** Standard color decorator behavior in modern editors

---

## Recommended Approach: LSP Integration

The standard solution is to integrate a **Language Server Protocol (LSP)** client. This provides all features above with one integration.

### Popular LSP Servers

| Language | Server |
|----------|--------|
| Python | `pyright`, `pylsp` |
| TypeScript/JS | `typescript-language-server` |
| Rust | `rust-analyzer` |
| Go | `gopls` |
| C/C++ | `clangd` |

### LSP Client Libraries for Python

- **pygls** - Python LSP server/client library
- **pylspclient** - Minimal LSP client
- Custom implementation using JSON-RPC over stdio

### Implementation Steps

1. Create `src/lsp_client.py` - JSON-RPC communication with LSP servers
2. Create `src/intellisense.py` - Connect LSP responses to GtkSourceView
3. Wire completion provider to `GtkSourceCompletionProvider`
4. Add hover tooltips via `Gtk.Popover`
5. Implement go-to-definition with file opening

---

## Priority Order

1. **Autocomplete** - Most impactful for productivity
2. **Go-to-definition** - Essential for code navigation
3. **Color preview** - Visual enhancement, standalone feature
4. **Hover docs** - Nice to have
5. **Symbol search** - Nice to have
6. **Cross-file navigation** - Advanced feature
