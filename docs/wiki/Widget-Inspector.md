# Widget Inspector

The Widget Inspector is a DevTools-like inspection mode for exploring the Zen IDE interface itself — useful for theme development and debugging.

## Opening the Inspector

| Action | Shortcut |
|---|---|
| Toggle Widget Inspector | `Cmd+Shift+I` |

When active, the status bar shows an **Inspect** mode indicator.

## Features

### Inspect Mode

Click on any UI element to inspect it:
- Widget type and class name
- CSS classes applied
- Current colours (foreground, background, border)
- Font family and size
- Widget dimensions and position

### AI Chat Block Inspection

In the AI chat panel, inspect individual message blocks to see:
- Block type (user message, AI response, code block, etc.)
- Rendering details
- Colour values used

### Colour Inspection

Click on any coloured element to see:
- Exact hex colour value
- RGB components
- How the colour maps to the current theme

## Use Cases

- **Theme development** — See exactly which theme colours are applied where
- **Debugging layout issues** — Check widget dimensions and positioning
- **Learning the UI structure** — Understand how Zen IDE's interface is built
