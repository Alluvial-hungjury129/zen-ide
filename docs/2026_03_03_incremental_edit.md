# Incremental Text Editing

**Created_at:** 2026-03-03  
**Updated_at:** 2026-03-08  
**Status:** Active  
**Goal:** Explain incremental text editing for format-on-save that preserves scroll position and cursor  
**Scope:** `src/editor/editor_view.py`, `_apply_incremental_edit()`  

---

## Overview

Zen IDE uses **incremental text editing** for format-on-save operations. Instead of replacing the entire buffer content (which causes scroll and cursor jumps), the editor computes minimal diffs and applies surgical edits to only the changed regions.

This is a standard approach used by modern editors to preserve user context during automatic formatting.

## The Problem

When saving a file with format-on-save enabled, the naive approach is:

```python
# BAD: Replaces entire buffer, loses scroll/cursor position
formatted_content = formatter.format(content)
buffer.set_text(formatted_content)
```

This causes several issues:
1. **Scroll position resets** - User loses their place in the file
2. **Cursor position resets** - Cursor jumps to start of file
3. **Selection is lost** - Any text selection disappears
4. **Undo history fragmented** - Single "replace all" in undo stack

## The Solution

The `_apply_incremental_edit()` method in `editor_view.py` uses Python's `difflib` to:

1. Split old and new content into lines
2. Compute minimal opcodes (equal, replace, insert, delete)
3. Apply changes **in reverse order** to preserve line numbers
4. Wrap all edits in a single `begin_user_action()`/`end_user_action()` pair

```python
def _apply_incremental_edit(self, new_content: str):
    import difflib
    
    old_lines = buffer.get_text(...).splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    opcodes = matcher.get_opcodes()
    
    # Apply in reverse to preserve line numbers
    for tag, i1, i2, j1, j2 in reversed(opcodes):
        if tag == "equal":
            continue
        # Apply change at [i1:i2] -> new_lines[j1:j2]
```

## Why Reverse Order?

Consider this example with two changes:

```
Line 0: unchanged
Line 1: change A (old) -> A' (new)
Line 2: unchanged  
Line 3: change B (old) -> B' (new)
Line 4: unchanged
```

**Forward order (wrong):**
1. Apply change A at line 1 - this might change the buffer length
2. Apply change B at "line 3" - but line 3 has shifted!

**Reverse order (correct):**
1. Apply change B at line 3 first
2. Apply change A at line 1 - line 1 position is unchanged because B was below it

## Algorithm Details

### Step 1: Normalize Lines

```python
old_lines = old_content.splitlines(keepends=True)
new_lines = new_content.splitlines(keepends=True)

# Ensure final newline for consistent comparison
if old_lines and not old_lines[-1].endswith("\n"):
    old_lines[-1] += "\n"
```

### Step 2: Compute Diff

```python
matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
opcodes = matcher.get_opcodes()
# Returns: [('equal', 0, 10, 0, 10), ('replace', 10, 11, 10, 11), ...]
```

### Step 3: Early Exit

```python
if all(op[0] == "equal" for op in opcodes):
    return  # No changes, nothing to do
```

### Step 4: Apply Changes

```python
buffer.begin_user_action()  # Group for undo
try:
    for tag, i1, i2, j1, j2 in reversed(opcodes):
        if tag == "equal":
            continue
        
        # Get start iter at line i1
        start_iter = buffer.get_start_iter()
        for _ in range(i1):
            start_iter.forward_line()
        
        # Get end iter at line i2
        end_iter = buffer.get_start_iter()
        for _ in range(i2):
            if not end_iter.forward_line():
                end_iter = buffer.get_end_iter()
                break
        
        # Replace the range
        new_text = "".join(new_lines[j1:j2])
        buffer.delete(start_iter, end_iter)
        buffer.insert(start_iter, new_text)
finally:
    buffer.end_user_action()
```

## Performance

The `difflib.SequenceMatcher` algorithm is O(n²) in worst case but typically O(n) for similar sequences. For a 10,000 line file with one changed line, the diff completes in milliseconds.

Tests verify performance with large files - see `tests/editor/test_incremental_edit.py`.

## Benefits

| Aspect | `buffer.set_text()` | Incremental Edit |
|--------|---------------------|------------------|
| Scroll position | ❌ Lost | ✅ Preserved |
| Cursor position | ❌ Lost | ✅ Preserved (if in unchanged region) |
| Selection | ❌ Lost | ✅ Preserved (if in unchanged region) |
| Undo | ❌ Coarse | ✅ Fine-grained |
| Performance | ✅ O(1) | ✅ O(n) typical |

## Usage

The incremental edit is automatically used by `save_file()` when formatting is applied:

```python
# In save_file():
formatted = self._format_on_save(path, content)
if formatted is not None and formatted != content:
    content = formatted
    self._apply_incremental_edit(content)  # Preserves scroll/cursor
```

## Testing

Run the incremental edit tests:

```bash
make tests -- tests/editor/test_incremental_edit.py
```

Tests cover:
- Diff opcode generation (no change, single change, multiple changes)
- Reverse order application
- Newline normalization
- Large file performance
- Scroll/cursor preservation scenarios

## Related

- `src/editor/editor_view.py` - `_apply_incremental_edit()` implementation
- `src/editor/format_manager.py` - Format-on-save logic
- `tests/editor/test_incremental_edit.py` - Test coverage
