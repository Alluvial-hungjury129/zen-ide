# Fonts

Zen IDE provides centralised font management with per-component configuration. Each part of the UI can have its own font family, size, and weight.

## Bundled Fonts

Zen IDE ships with these fonts (no installation required):

| Font | Purpose |
|---|---|
| **Source Code Pro** | Default editor and terminal font (variable weight) |
| **ZenIcons** | Nerd Font subset for file icons and UI symbols |
| **Symbols Nerd Font** | Fallback icon font |

## Font Components

Each UI component has independent font settings:

| Component | Default Family | Default Size | Setting Key |
|---|---|---|---|
| **Editor** | Source Code Pro | 16pt | `fonts.editor.*` |
| **Terminal** | System default | 16pt | `fonts.terminal.*` |
| **File Explorer** | System default | 16pt | `fonts.explorer.*` |
| **AI Chat** | System default | 16pt | `fonts.ai_chat.*` |
| **Markdown Preview** | Editor font | 14pt | `fonts.markdown_preview.*` |

## Changing Fonts

### Font Picker Dialog

Open the font picker from the **View** menu. It lets you:
1. **Choose a component** (editor, terminal, explorer, etc.)
2. **Search fonts** — Filter from all installed system fonts
3. **Set size** — 6pt to 72pt
4. **Preview** — See the font applied in real-time

### Manual Configuration

Edit `~/.zen_ide/settings.json`:

```json
{
  "fonts.editor.family": "JetBrains Mono",
  "fonts.editor.size": 14,
  "fonts.editor.weight": "normal",
  "fonts.terminal.family": "Fira Code",
  "fonts.terminal.size": 13
}
```

### Zoom (Quick Size Adjustment)

| Shortcut | Action |
|---|---|
| `Cmd++` | Increase font size (all components) |
| `Cmd+-` | Decrease font size (all components) |
| `Cmd+0` | Reset to default size |

## Font Weights

Available weight values:
- `"thin"`, `"light"`, `"normal"`, `"medium"`, `"semibold"`, `"bold"`, `"heavy"`

## Font Rendering Settings

Fine-tune text rendering in `~/.zen_ide/settings.json`:

| Setting | Default | Description |
|---|---|---|
| `font_rendering.pango_backend` | `"auto"` | Text backend: `"auto"`, `"coretext"` (macOS), `"freetype"` |
| `font_rendering.antialias` | `true` | Enable anti-aliasing |
| `font_rendering.hinting` | `true` | Enable font hinting |
| `font_rendering.hintstyle` | `"hintfull"` | Hint intensity: `"hintnone"`, `"hintslight"`, `"hintmedium"`, `"hintfull"` |
| `font_rendering.subpixel_order` | `"rgb"` | Subpixel layout: `"none"`, `"rgb"`, `"bgr"`, `"vrgb"`, `"vbgr"` |
| `font_rendering.hint_font_metrics` | `true` | Snap glyph metrics to pixel grid |

> **Note:** Changes to `font_rendering.pango_backend` require an IDE restart.

## Nerd Font Detection

On first launch, Zen IDE scans your system for installed Nerd Fonts (fonts with icon glyphs). The result is cached in `~/.zen_ide/font_cache.txt`.

If a Nerd Font is found, it's used for file icons in the tree view. Otherwise, emoji fallbacks are used.

## Font Ligatures

Enable programming ligatures (e.g., `=>` → `⇒`, `!=` → `≠`):

```json
{
  "editor.font_ligatures": true
}
```

Requires a font that supports ligatures (e.g., Fira Code, JetBrains Mono).

## Letter Spacing

Adjust spacing between characters:

```json
{
  "editor.letter_spacing": 0.5
}
```

Default: `0.3` on macOS, `0` on Linux.
