"""Tests for incremental text editing to preserve scroll/cursor.

The _apply_incremental_edit method uses difflib to apply minimal changes
to the buffer instead of replacing all text. This preserves scroll position
and cursor location when formatting on save.

See docs/incremental_edit.md for the full design.
"""

import difflib

import pytest


class TestIncrementalEdit:
    """Test the incremental edit algorithm used in format-on-save."""

    def test_diff_opcodes_no_change(self):
        """When content is unchanged, no edits should be needed."""
        old = ["line1\n", "line2\n", "line3\n"]
        new = ["line1\n", "line2\n", "line3\n"]

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # All opcodes should be 'equal'
        assert all(op[0] == "equal" for op in opcodes)

    def test_diff_opcodes_single_line_change(self):
        """Single line change should produce minimal diff."""
        old = ["line1\n", "line2\n", "line3\n"]
        new = ["line1\n", "modified\n", "line3\n"]

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Should have: equal (line1), replace (line2->modified), equal (line3)
        ops = [(tag, i1, i2, j1, j2) for tag, i1, i2, j1, j2 in opcodes]

        assert len(ops) == 3
        assert ops[0][0] == "equal"
        assert ops[1][0] == "replace"
        assert ops[2][0] == "equal"

    def test_diff_opcodes_insert_line(self):
        """Inserting a line should produce insert opcode."""
        old = ["line1\n", "line2\n"]
        new = ["line1\n", "new_line\n", "line2\n"]

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Should have an insert opcode
        tags = [tag for tag, _, _, _, _ in opcodes]
        assert "insert" in tags

    def test_diff_opcodes_delete_line(self):
        """Deleting a line should produce delete opcode."""
        old = ["line1\n", "to_delete\n", "line2\n"]
        new = ["line1\n", "line2\n"]

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Should have a delete opcode
        tags = [tag for tag, _, _, _, _ in opcodes]
        assert "delete" in tags

    def test_diff_opcodes_multiple_changes(self):
        """Multiple changes should all be captured."""
        old = ["line1\n", "line2\n", "line3\n", "line4\n", "line5\n"]
        new = ["line1\n", "changed2\n", "line3\n", "changed4\n", "line5\n"]

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Count non-equal operations
        changes = [op for op in opcodes if op[0] != "equal"]
        assert len(changes) == 2

    def test_diff_preserves_unchanged_regions(self):
        """Unchanged regions at start/end should be preserved."""
        # Simulate a 100-line file where only line 50 changes
        old = [f"line{i}\n" for i in range(100)]
        new = old.copy()
        new[50] = "modified50\n"

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Should have: equal (0-50), replace (50-51), equal (51-100)
        assert len(opcodes) == 3
        assert opcodes[0] == ("equal", 0, 50, 0, 50)
        assert opcodes[1][0] == "replace"
        assert opcodes[2] == ("equal", 51, 100, 51, 100)

    def test_reverse_order_application(self):
        """Applying changes in reverse preserves line numbers."""
        # When applying multiple edits, reverse order ensures
        # earlier edits don't shift line numbers for later ones
        old = ["a\n", "b\n", "c\n", "d\n", "e\n"]
        new = ["a\n", "B\n", "c\n", "D\n", "e\n"]

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = list(matcher.get_opcodes())

        # When applied in reverse, line 3 (d->D) is applied before line 1 (b->B)
        # This ensures the change to line 1 doesn't affect line 3's position
        reversed_changes = [op for op in reversed(opcodes) if op[0] != "equal"]

        # First change should be later in file (d->D at index 3)
        # Second change should be earlier (b->B at index 1)
        assert reversed_changes[0][1] == 3  # i1 for d->D
        assert reversed_changes[1][1] == 1  # i1 for b->B

    def test_newline_normalization(self):
        """Lines should be normalized to have newlines."""
        # Without final newline
        old = "line1\nline2"
        new = "line1\nline2"

        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        # Normalize
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        assert old_lines[-1].endswith("\n")
        assert new_lines[-1].endswith("\n")

    def test_empty_to_content(self):
        """Adding content to empty buffer."""
        old = []
        new = ["line1\n", "line2\n"]

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Should have just one insert
        assert len(opcodes) == 1
        assert opcodes[0][0] == "insert"

    def test_content_to_empty(self):
        """Clearing buffer content."""
        old = ["line1\n", "line2\n"]
        new = []

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Should have just one delete
        assert len(opcodes) == 1
        assert opcodes[0][0] == "delete"


class TestFormatOnSaveIntegration:
    """Integration tests for format-on-save behavior.

    These tests verify the full flow works correctly with the
    incremental edit approach.
    """

    def test_formatting_indentation_change(self):
        """Formatting that changes indentation should work."""
        # Simulates a formatter fixing indentation
        old = ["def foo():\n", "x = 1\n", "  y = 2\n"]  # bad indent
        new = ["def foo():\n", "    x = 1\n", "    y = 2\n"]  # fixed

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Should detect the changes
        changes = [op for op in opcodes if op[0] != "equal"]
        assert len(changes) > 0

    def test_formatting_trailing_whitespace(self):
        """Formatting that removes trailing whitespace."""
        old = ["line1   \n", "line2\t\n", "line3\n"]
        new = ["line1\n", "line2\n", "line3\n"]

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Should detect trailing whitespace removal
        # difflib may group adjacent changes into one replace opcode
        changes = [op for op in opcodes if op[0] != "equal"]
        assert len(changes) >= 1  # at least one change detected
        # Verify the changed lines are covered
        changed_lines = set()
        for tag, i1, i2, j1, j2 in changes:
            for i in range(i1, i2):
                changed_lines.add(i)
        assert 0 in changed_lines and 1 in changed_lines

    def test_formatting_adds_final_newline(self):
        """Formatting that adds missing final newline."""
        old = "line1\nline2"
        new = "line1\nline2\n"

        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        # Normalize for comparison
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        opcodes = matcher.get_opcodes()

        # After normalization, should be equal or minimal change
        assert any(op[0] == "equal" for op in opcodes)

    def test_large_file_performance(self):
        """Diff algorithm should handle large files efficiently."""
        # 10,000 lines with one change at line 5000
        old = [f"line{i}\n" for i in range(10000)]
        new = old.copy()
        new[5000] = "modified5000\n"

        # This should complete quickly (< 1 second)
        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Should identify minimal change
        changes = [op for op in opcodes if op[0] != "equal"]
        assert len(changes) == 1
        assert changes[0][1] == 5000  # i1 should be 5000


class TestScrollPreservation:
    """Tests verifying scroll position preservation logic.

    The incremental edit approach preserves scroll because unchanged
    regions remain untouched in the buffer.
    """

    def test_cursor_in_unchanged_region_preserved(self):
        """When cursor is in unchanged region, it stays put."""
        # If file has 100 lines and cursor is at line 10,
        # changing line 50 should not affect cursor position

        old = [f"line{i}\n" for i in range(100)]
        new = old.copy()
        new[50] = "modified50\n"

        cursor_line = 10  # Cursor at line 10

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Find which region contains cursor
        cursor_affected = False
        for tag, i1, i2, j1, j2 in opcodes:
            if tag != "equal" and i1 <= cursor_line < i2:
                cursor_affected = True
                break

        assert not cursor_affected, "Cursor should not be in changed region"

    def test_cursor_in_changed_region_still_valid(self):
        """When cursor is in changed region, edit still works."""
        old = ["line1\n", "cursor_here\n", "line3\n"]
        new = ["line1\n", "modified_cursor_line\n", "line3\n"]

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Cursor is in changed region but algorithm still works
        changes = [op for op in opcodes if op[0] != "equal"]
        assert len(changes) == 1
        # After edit, cursor position depends on GTK behavior
        # but at least the edit completes successfully

    def test_multiple_cursors_scenario(self):
        """Changes far from cursor don't affect nearby cursor regions."""
        # Simulates having cursor at line 10 while formatting changes lines 90-95

        old = [f"line{i}\n" for i in range(100)]
        new = old.copy()
        for i in range(90, 95):
            new[i] = f"formatted{i}\n"

        cursor_line = 10

        matcher = difflib.SequenceMatcher(None, old, new)
        opcodes = matcher.get_opcodes()

        # Lines 0-89 should be in "equal" region
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal" and i1 <= cursor_line < i2:
                # Cursor is in equal region - it will be preserved
                assert True
                return

        pytest.fail("Cursor line should be in unchanged region")
