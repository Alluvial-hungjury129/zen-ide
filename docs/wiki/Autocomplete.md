# Autocomplete / IntelliSense

Zen IDE provides context-aware code completion with signature hints for Python, JavaScript/TypeScript, and Terraform.

## Triggering Autocomplete

| Action | Shortcut |
|---|---|
| Manual trigger | `Cmd+Space` |
| Auto-trigger | Type `.`, `:`, `(`, or after 3+ characters (if `editor.auto_complete_on_type` is enabled) |

## Navigating the Completion List

| Key | Action |
|---|---|
| `↓` / `j` / `Ctrl+N` | Move down |
| `↑` / `k` / `Ctrl+P` | Move up |
| `Enter` | Insert selected completion |
| `Tab` | Insert and advance to next tabstop (for snippets) |
| `Escape` | Dismiss the completion list |

## Completion Kinds

Each suggestion has an icon indicating its type:

| Icon | Kind |
|---|---|
| `ƒ` | Function / Method |
| `C` | Class |
| `P` | Property / Field |
| `V` | Variable |
| `K` | Keyword |
| `M` | Module |
| `S` | Snippet |
| `T` | Type |
| `E` | Enum |
| `I` | Interface |
| `U` | Unit / Constant |

## Signature Display

When you type `(` after a function name, a signature hint appears showing:
- Parameter names and types
- Current parameter highlighted
- Brief description (when available)

## Language-Specific Providers

### Python
- **AST-based** completion using Python's `ast` module
- **Introspection** for installed packages
- Completes: imports, class members, function names, variables, keywords
- Understands decorators, type hints, and docstrings

### JavaScript / TypeScript
- **Babel-based** parsing for accurate JS/TS completion
- Completes: imports, object properties, function names, React components
- Supports JSX/TSX

### Terraform
- **Schema-based** HCL completion
- Completes: resource types, provider attributes, variable references
- Knows standard Terraform resource schemas

## Snippet Tabstops

Some completions insert snippets with multiple cursor positions (tabstops). After inserting:
- Press `Tab` to jump to the next tabstop
- Edit each tabstop value
- Press `Escape` when done

## Settings

| Setting | Default | Description |
|---|---|---|
| `editor.auto_complete_on_type` | `false` | Auto-trigger after 3+ characters |

## Tips

- Use `Cmd+Space` to trigger completions at any time
- After typing a dot (`.`), completions appear automatically
- The completion list updates as you type to filter results
