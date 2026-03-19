# Diff View

Zen IDE includes a split diff view for comparing file changes against git, showing additions, deletions, and modifications with syntax highlighting.

## Opening the Diff View

Right-click a modified file in the tree view and select **Discard Local Changes** to see the diff, or the diff view is shown automatically when comparing git changes.

## Layout

The diff view uses a side-by-side split layout:

```
┌──────────────────┬──────────────────┐
│   Original (HEAD) │   Modified       │
│                   │                  │
│   line 1          │   line 1         │
│ - deleted line    │                  │
│   line 3          │ + new line       │
│                   │   line 3         │
└──────────────────┴──────────────────┘
```

## Features

### Colour Coding

| Colour | Meaning |
|---|---|
| 🟢 Green background | Added lines |
| 🔴 Red background | Deleted lines |
| 🟡 Yellow background | Changed lines |

### Inline Revert

Each diff region has a revert button — click it to revert just that specific change back to the HEAD version without discarding the entire file.

### Syntax Highlighting

Both sides of the diff have full syntax highlighting, matching the editor's current theme.

### Navigation

- Scroll both sides in sync
- Click on a line to jump to it
- Browse commit history

### Blame Information

Git blame data is available, showing who last modified each line.
