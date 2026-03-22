# Code Navigation

Zen IDE supports **Go to Definition** via `Cmd+Click` for Python, TypeScript/JavaScript, and Terraform.

## How to Use

| Action | Shortcut |
|---|---|
| Go to definition | `Cmd+Click` on a symbol |
| Preview link | `Cmd+Hover` — underlines navigable symbols |

## How It Works

1. **Hold Cmd** and hover over a symbol — if it's navigable, it gets underlined
2. **Click** to jump to the definition
3. The target file opens in the editor and scrolls to the definition line
4. A **fade-out highlight animation** marks the target line

## Language Support

### Python

The Python navigator resolves:
- `import module` statements → finds the source file
- `from module import name` → finds the file and the specific definition
- Class names, function names, variable references

**Search locations:**
1. Current workspace
2. Project root
3. Python standard library paths
4. Installed packages (site-packages)

### TypeScript / JavaScript

The TypeScript/JS navigator resolves:
- `import { name } from './module'` → finds the source file
- `require('./module')` → finds the file
- Supports `.ts`, `.tsx`, `.js`, `.jsx` extension resolution
- Checks `index.ts` / `index.js` for directory imports

### Terraform

The Terraform navigator resolves:
- `resource "type" "name"` blocks
- `module "name"` references
- Variable and local value references

## Symbol Resolution

When you click on a symbol, the navigation system:
1. Parses the import statement or symbol reference
2. Searches for the source file across the workspace
3. Uses **Tree-sitter AST queries** to locate the exact definition (class, function, variable, interface, etc.)
4. Opens the file and scrolls to the definition

## Settings

| Setting | Default | Description |
|---|---|---|
| `navigation.provider` | `"custom"` | Navigation backend |
