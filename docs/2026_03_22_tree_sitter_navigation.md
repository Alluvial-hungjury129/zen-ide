# Tree-sitter Navigation

**Created_at:** 2026-03-22  
**Updated_at:** 2026-03-22  
**Status:** Active  
**Goal:** Replace regex-based symbol finding and import parsing with Tree-sitter AST queries for accurate, scope-aware code navigation  
**Scope:** `src/navigation/tree_sitter_core.py`, `src/navigation/tree_sitter_queries.py`, `src/navigation/tree_sitter_py_provider.py`, `src/navigation/tree_sitter_ts_provider.py`  

---

## Overview

Zen IDE's go-to-definition (`Cmd+Click`) now uses **Tree-sitter** for parsing source code instead of regex patterns. Tree-sitter produces a full Abstract Syntax Tree (AST) that is queried with S-expression patterns, giving accurate results for constructs that regex can't handle (async functions, type-hinted variables, complex imports with comments, nested definitions).

## Architecture

```
src/navigation/
├── tree_sitter_core.py          # Lazy parser manager (language registry, caching)
├── tree_sitter_queries.py       # S-expression query definitions per language
├── tree_sitter_py_provider.py   # Python NavigationProvider using tree-sitter
├── tree_sitter_ts_provider.py   # TS/JS NavigationProvider using tree-sitter
├── code_navigation.py           # Dispatcher (unchanged interface)
├── code_navigation_py.py        # Python mixin — delegates to tree-sitter provider
├── code_navigation_ts.py        # TS/JS mixin — delegates to tree-sitter provider
├── code_navigation_tf.py        # Terraform mixin — delegates to tree-sitter provider
├── navigation_provider.py       # Abstract base class (unchanged)
├── custom_provider.py           # Standalone provider — uses tree-sitter
├── terraform_provider.py        # Terraform provider — uses tree-sitter
```

## Components

### TreeSitterCore (`tree_sitter_core.py`)

Lazy singleton that manages Tree-sitter parsers and languages:

- **Lazy loading**: `tree_sitter` module is imported on first use, not at module level
- **Caching**: `Language` and `Parser` instances are cached per language
- **Supported languages**: `python`, `javascript`, `typescript`, `tsx`, `hcl`
- **API**: `parse(source_bytes, lang)`, `query(lang, pattern)`, `run_query(tree, query)`

### Query Definitions (`tree_sitter_queries.py`)

S-expression patterns grouped by language:

| Query | Languages | Captures |
|-------|-----------|----------|
| `PY_DEFINITIONS` | Python | `@name`, `@node` — function, class, assignment |
| `PY_IMPORTS` | Python | `@module`, `@name`, `@alias` — import/from-import |
| `TS_DEFINITIONS` | TypeScript | `@name`, `@node` — function, class, interface, type, enum, const |
| `JS_DEFINITIONS` | JavaScript | `@name`, `@node` — function, class, const |
| `TS_IMPORTS` | TypeScript/JS | `@name`, `@module` — named, default, namespace imports |

### Providers

Both providers implement the `NavigationProvider` interface:

- **`TreeSitterPyProvider`**: Python symbol finding and import parsing
- **`TreeSitterTsProvider`**: TypeScript/JavaScript/TSX symbol finding and import parsing
- **`TreeSitterTfProvider`**: Terraform/HCL block resolution

## What Tree-sitter Handles vs. What Stays

| Concern | Implementation |
|---------|---------------|
| Symbol finding in file content | **Tree-sitter AST queries** |
| Import parsing | **Tree-sitter AST queries** |
| Module/file resolution (venv, workspace) | OS path walking (unchanged) |
| Re-export following (`__init__.py`) | File I/O + tree-sitter |
| tsconfig path aliases | JSON parsing (unchanged) |
| Terraform navigation | **Tree-sitter AST queries** |

## Improvements Over Regex

Tree-sitter correctly handles constructs that regex could not:

- `async def fetch_data()` — async functions
- `count: int = 0` — type-hinted variable assignments  
- Parenthesized imports with inline comments
- Decorated function definitions
- Nested class definitions
- Complex export patterns in TypeScript

## Dependencies

Added to `pyproject.toml`:

```toml
"tree-sitter>=0.23.0",
"tree-sitter-python>=0.23.0",
"tree-sitter-javascript>=0.23.0",
"tree-sitter-typescript>=0.23.0",
"tree-sitter-hcl>=1.2.0",
```

## Startup Performance

Tree-sitter is **lazy-loaded** — no imports occur at module level. The first `Cmd+Click` triggers loading (~5ms one-time cost), subsequent navigations use cached parsers. This preserves the <80ms startup requirement.

## Tests

Test file: `tests/navigation/test_tree_sitter_navigation.py`

- `TestTreeSitterCore`: Lazy loading, caching, language mapping, query compilation
- `TestTreeSitterPyProvider`: Class, function, async function, variable, decorated, nested, imports
- `TestTreeSitterTsProvider`: Function, class, interface, type, enum, const, arrow function, TSX, imports
