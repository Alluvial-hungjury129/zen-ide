# Intellisense System

**Created_at:** 2026-02-08  
**Updated_at:** 2026-03-16  
**Status:** Active  
**Goal:** Document autocomplete, signature hints, go-to-definition, and hover highlighting  
**Scope:** `src/editor/autocomplete/`, `src/navigation/`, Python/JavaScript completions  

---

Zen IDE provides code intelligence features through the `src/editor/autocomplete/` and `src/navigation/` modules. This includes autocomplete, signature hints, go-to-definition, and hover highlighting.

## Architecture Overview

```
editor/autocomplete/
├── autocomplete.py          # Ctrl+Space triggered completions
├── python_provider.py       # Python completion provider
├── js_provider.py           # JavaScript/TypeScript completion provider
└── terraform_provider.py    # Terraform completion provider

navigation/
├── code_navigation.py       # Cmd+Click navigation coordinator
├── code_navigation_py.py    # Python navigation (import resolution, type inference)
├── code_navigation_ts.py    # TypeScript/JS navigation
├── code_navigation_tf.py    # Terraform navigation
├── navigation_provider.py   # Base provider interface
├── tree_sitter_core.py      # Lazy parser manager (language registry, caching)
├── tree_sitter_queries.py   # S-expression query definitions per language
├── tree_sitter_py_provider.py  # Python provider using Tree-sitter
├── tree_sitter_ts_provider.py  # TS/JS provider using Tree-sitter
└── tree_sitter_tf_provider.py  # Terraform provider using Tree-sitter
```

## Components

### 1. Autocomplete (`editor/autocomplete/autocomplete.py`)

**Trigger:** `Ctrl+Space`

Provides context-aware code completion in a dropdown popup.

#### Features:
- **Language detection:** Python, JavaScript/TypeScript completions based on file extension
- **Completion kinds:** Functions, properties, keywords, builtins, snippets, variables, parameters
- **Dot notation:** `ClassName.` or `self.` triggers member completions
- **Import completions:** `from module.` shows submodules, `from module import ` shows exports
- **Parameter completions:** Inside function calls (`func(arg, |)`) suggests remaining keyword arguments with defaults
- **Type inference:** `var = SomeClass()` → `var.` shows `SomeClass` members
- **Venv introspection:** Completions from packages in `.venv/venv`

#### Completion Icons

Each completion item shows an icon indicating its kind:

| Icon | Kind | Description |
|------|------|-------------|
| `ƒ` | Function | Functions and methods |
| `●` | Property | Classes, attributes, enum values |
| `κ` | Keyword | Language keywords (`if`, `class`, `return`, etc.) |
| `β` | Builtin | Built-in functions (`len`, `print`, `range`, etc.) |
| `⌘` | Snippet | Code snippets (e.g., `if __name__` block) |
| `ν` | Variable | Variables and imports |
| `π` | Parameter | Function call parameters (keyword args) |

#### Completion Priority:
1. Properties (class attributes, enum values)
2. Functions/methods
3. Variables
4. Builtins
5. Keywords
6. Snippets

#### Key Bindings:
| Key | Action |
|-----|--------|
| `Ctrl+Space` | Trigger completions |
| `↑/↓` | Navigate list |
| `Enter/Tab` | Accept completion |
| `Escape` | Close popup |

### 2. Code Navigation (`navigation/code_navigation.py`)

**Trigger:** `Cmd+Click` (macOS) or `Ctrl+Click` (Linux)

Coordinates go-to-definition and hover highlighting. Delegates to language-specific implementations.

#### Features:
- **Hover highlighting:** Shows clickable link styling when hovering over navigable symbols
- **Go-to-definition:** Opens file and navigates to symbol definition
- **Import resolution:** Follows `from X import Y` to find where `Y` is defined
- **Re-export handling:** Follows re-exports in `__init__.py` to actual source files
- **Cross-file navigation:** Searches project directories and workspace folders

#### Motion Throttling:
Hover detection is throttled (32ms) to avoid performance issues during scrolling.

### 3. Language-Specific Navigation (`navigation/code_navigation_py.py`, etc.)

Provides a registry of language-specific navigation implementations.

#### Supported Languages:

| Language | Class | Features |
|----------|-------|----------|
| Python | `PythonIntellisense` | Full import resolution, type inference, re-export following |
| Terraform | `TerraformIntellisense` | `local.`, `var.`, `module.`, `data.`, resource refs |
| TypeScript/JS | `TypeScriptIntellisense` | Import navigation, interface property lookup, CSS modules |
| YAML | `YamlIntellisense` | `$ref` navigation (OpenAPI/Swagger) |
| Generic | `GenericIntellisense` | Basic definition finding |

#### Extension Mapping:

```python
".py"  → python      ".tf"   → terraform
".ts"  → typescript  ".tsx"  → typescript  
".js"  → javascript  ".jsx"  → javascript
".yaml"→ yaml        ".yml"  → yaml
```

### 4. Signature Hints (`signature_hint.py`)

**Trigger:** `(` key or `Ctrl+Space` inside parentheses

Shows function/method signature in a tooltip popup.

#### Features:
- **Auto-trigger:** Shows when typing `(` after a function name
- **Parameter display:** Shows parameters with defaults, excludes `self/cls`
- **Docstring preview:** Shows first line of docstring
- **Local/imported/venv:** Finds signatures from local code, imports, and venv packages

#### Lookup Strategies:
1. Local function/method definition in current file
2. Imported class method (follows imports)
3. Venv introspection for external packages

### 5. Venv Introspector (`venv_introspector.py`)

Provides dynamic completions from packages installed in virtual environments.

#### Features:
- **Auto-detection:** Finds `.venv`, `venv`, `env`, `.env` directories
- **Dynamic import:** Temporarily adds site-packages to `sys.path`
- **Member extraction:** Gets public methods/properties from modules/classes
- **Caching:** Caches results per project to avoid re-importing

#### Supported Venv Layouts:
```
project/
├── .venv/lib/python3.x/site-packages/
├── venv/lib/python3.x/site-packages/
└── env/lib/python3.x/site-packages/
```

## Python Intellisense Details

### Import Resolution Flow

When Cmd+clicking on a symbol like `MyClass.method()`:

```
1. Parse imports in current file
2. Find "from module import MyClass" → module = "module"
3. Check if module/__init__.py has "from .submodule import MyClass"
4. If re-export found → open submodule.py instead of __init__.py
5. Navigate to "method" definition in the opened file
```

### Type Inference

For `var.method()` completions:

```python
# Pattern 1: Direct instantiation
validator = SomeValidator()  # var_type = "SomeValidator"

# Pattern 2: Type hint
validator: SomeValidator = ...  # var_type = "SomeValidator"

# Pattern 3: Function parameter
def process(validator: SomeValidator):  # var_type = "SomeValidator"
```

### Unnavigable Builtins

Certain Python builtins (implemented in C) are marked as unnavigable:
- Types: `str`, `int`, `list`, `dict`, etc.
- Functions: `len`, `print`, `range`, `isinstance`, etc.
- Exceptions: `ValueError`, `TypeError`, etc.

## Terraform Intellisense Details

### Reference Types

| Pattern | Example | Navigation |
|---------|---------|------------|
| `local.name` | `local.tags` | Find `name = ...` in `locals {}` block |
| `var.name` | `var.env` | Find `variable "name" {}` |
| `module.name` | `module.vpc` | Find `module "name" {}` |
| `data.type.name` | `data.aws_vpc.main` | Find `data "type" "name" {}` |
| `resource.name` | `aws_lambda.handler` | Find `resource "type" "name" {}` |

### Cross-File Search

If not found in current file, searches all `.tf` files in the same directory.

## TypeScript Intellisense Details

### Import Parsing

Supports various import styles:
```typescript
import { X, Y } from "path"     // Named imports
import X from "path"             // Default import  
import * as X from "path"        // Namespace import
```

### Type-Aware Navigation

For property access like `item.row`:
1. Find variable type annotation (`item: RowType`)
2. Check if type is imported
3. Open import source file
4. Find property definition in interface

### CSS Module Support

For `styles.className`:
1. Detect CSS module import (`import styles from './x.module.css'`)
2. Navigate to CSS file
3. Find `.className` definition

## YAML Intellisense Details

### $ref Navigation

Supports OpenAPI/Swagger `$ref` patterns:

```yaml
$ref: "#/components/schemas/User"      # Local JSON pointer
$ref: "./models.yaml#/User"            # External file + pointer
$ref: "../common/types.yaml"           # External file only
```

## Configuration

Intellisense is automatically enabled. Settings that affect it:

```json
{
  "editor": {
    "tab_size": 4  // Affects indent detection for completions
  }
}
```

## Adding Language Support

To add intellisense for a new language:

1. Create a class extending `BaseIntellisense` in `navigation/`
2. Implement required methods:
   - `get_word_at_index()` - Get symbol under cursor
   - `on_cmd_click()` - Handle go-to-definition
   - `check_resolvability()` - Check if symbol is navigable (for hover)
3. Register in the navigation provider registry
4. Add extension mapping

Example:
```python
class RubyIntellisense(BaseIntellisense):
    def get_word_at_index(self, editor, index: str) -> Optional[str]:
        # Ruby identifier extraction logic
        ...
    
    def on_cmd_click(self, editor, file_path: str, index: str) -> bool:
        # Ruby navigation logic
        ...

# Register
navigation_registry.register("ruby", RubyIntellisense)
navigation_registry.add_extension(".rb", "ruby")
```

## Performance Considerations

- **Caching:** Module introspection results are cached per project
- **Throttling:** Hover detection throttled to 32ms intervals
- **Lazy loading:** Language-specific intellisense instantiated on first use
- **Cache limits:** Autocomplete caches limited to 500 entries
