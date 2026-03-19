# Supported Languages & File Types

Zen IDE supports syntax highlighting for **100+ languages** via GtkSourceView, with enhanced features for a selection of popular languages.

## Feature Levels

| Level | Languages | Features |
|---|---|---|
| **Full** | Python, JavaScript, TypeScript | Syntax highlighting + semantic highlighting + autocomplete + code navigation |
| **Enhanced** | Terraform | Syntax highlighting + autocomplete + navigation |
| **Standard** | 100+ languages | Syntax highlighting |

## Language Detection

Languages are detected automatically by:
1. **File extension** (`.py` → Python, `.ts` → TypeScript)
2. **Filename** (`Makefile`, `Dockerfile`, `CMakeLists.txt`)
3. **Content type** (via Gio content_type_guess)
4. **GtkSourceView** language spec matching

## Fully Supported Languages

### Python (`.py`)
- ✅ Syntax highlighting
- ✅ Semantic highlighting (variables, parameters, decorators, type annotations)
- ✅ Autocomplete (AST-based + introspection)
- ✅ Code navigation (Cmd+Click go to definition)
- ✅ Format on save (ruff)
- ✅ Diagnostics (ruff check)

### JavaScript / TypeScript (`.js`, `.jsx`, `.ts`, `.tsx`)
- ✅ Syntax highlighting
- ✅ Semantic highlighting
- ✅ Autocomplete (Babel-based parsing)
- ✅ Code navigation (import resolution)
- ✅ Format on save (prettier)
- ✅ Diagnostics (eslint)

### Terraform (`.tf`)
- ✅ Syntax highlighting
- ✅ Autocomplete (schema-based HCL completion)
- ✅ Code navigation (resource block matching)

## Standard Syntax Highlighting

The following languages have syntax highlighting out of the box:

| Category | Languages |
|---|---|
| **Systems** | C, C++, Rust, Go, Assembly |
| **JVM** | Java, Kotlin, Scala, Clojure, Groovy |
| **Scripting** | Ruby, PHP, Perl, Lua, R, Julia |
| **Shell** | Bash, Zsh, Fish, PowerShell |
| **Web** | HTML, CSS, SCSS, Less, SVG |
| **Data** | JSON, YAML, TOML, XML, CSV, INI |
| **Markup** | Markdown, LaTeX, reStructuredText |
| **DevOps** | Dockerfile, Makefile, CMake, Meson |
| **Database** | SQL, GraphQL |
| **Config** | Nginx, Apache, systemd, gitconfig |
| **Other** | Swift, Dart, Elixir, Erlang, Haskell, OCaml, F#, Zig, Nim, V, GLSL, Vala |

## File Previews

Certain file types open with a visual preview alongside (or instead of) the text editor:

| Extension | Preview Type | Description |
|---|---|---|
| `.md`, `.markdown` | **Markdown** | Rendered HTML with code block highlighting |
| `.json`, `.yaml` (OpenAPI) | **OpenAPI/Swagger** | Formatted endpoint list with method badges |
| `.html` | **HTML** | Rendered via WebKit |
| `.png`, `.jpg`, `.gif`, `.bmp`, `.svg`, `.webp`, `.ico` | **Image Viewer** | Visual preview |
| Binary files | **Hex Viewer** | Offset + hex dump + ASCII |
| `.zen_sketch` | **Sketch Pad** | ASCII diagram editor |

## Custom Language Specs

Zen IDE bundles a custom GtkSourceView language spec for **Clojure** (not available in the standard GtkSourceView distribution). Additional `.lang` files can be added to `src/langs/`.
