# Formatters & Linters

Zen IDE supports automatic code formatting on save and inline diagnostics from external linters.

## Format on Save

When `editor.format_on_save` is `true` (default), files are automatically formatted when you press `Cmd+S`.

### How It Works

1. The formatter reads your file content via **stdin**
2. It writes the formatted result to **stdout**
3. Zen applies the result as an incremental edit (preserving cursor position and scroll)

### Default Formatters

| Extension | Formatter | Install |
|---|---|---|
| `.py` | `ruff format` | `pip install ruff` |
| `.js`, `.ts`, `.jsx`, `.tsx` | `prettier` | `npm install -g prettier` |
| `.json` | Built-in | (no install needed) |
| `.css`, `.html` | `prettier` | `npm install -g prettier` |

### Configuring Formatters

Add or change formatters in `~/.zen_ide/settings.json`:

```json
{
  "formatters": {
    ".py": "ruff format --stdin-filename {file} -",
    ".js": "prettier --stdin-filepath {file}",
    ".ts": "prettier --stdin-filepath {file}",
    ".json": "builtin",
    ".go": "gofmt",
    ".rs": "rustfmt --edition 2021"
  }
}
```

- **`{file}`** is replaced with the file path (for language detection by the formatter)
- The formatter must read from **stdin** and write to **stdout**
- Use `"builtin"` for the built-in JSON formatter (2-space indent)

### Disabling Format on Save

```json
{
  "editor.format_on_save": false
}
```

Or remove a specific extension from the `formatters` map.

## Diagnostics (Linters)

Linters run automatically after saving a file and display inline diagnostics (errors, warnings) in the editor and status bar.

### How It Works

1. After save, Zen runs the configured linter command
2. The output is parsed into diagnostics (file, line, column, severity, message)
3. Diagnostics appear as:
   - **Gutter icons** next to affected lines
   - **Error/warning counts** in the status bar (clickable)
   - **Full list** in the Diagnostics Popup

### Configuring Linters

Add linter configs per extension in `~/.zen_ide/settings.json`:

```json
{
  "diagnostics": {
    ".py": {
      "command": "ruff check --output-format json {file}",
      "format": "ruff"
    },
    ".js": {
      "command": "eslint --format unix {file}",
      "format": "line"
    },
    ".ts": {
      "command": "eslint --format unix {file}",
      "format": "line"
    }
  }
}
```

### Output Formats

| Format | Description | Example Tool |
|---|---|---|
| `"ruff"` | Ruff JSON output | `ruff check --output-format json` |
| `"line"` | Generic `file:line:col: message` | `eslint --format unix`, `gcc` |

### Viewing Diagnostics

| Action | How |
|---|---|
| Status bar counts | Error (🔴) and warning (🟡) counts appear in the status bar |
| Click status bar | Opens the Diagnostics Popup with full list |
| Gutter indicators | Coloured marks appear next to affected lines |
| Navigate to error | Click a diagnostic in the popup to jump to that line |

### Keyboard Navigation in Diagnostics Popup

| Key | Action |
|---|---|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `Enter` | Jump to selected diagnostic |
| `q` / `Escape` | Close popup |
