"""Tests for DevPadStorage activity management."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from dev_pad.dev_pad_storage import DevPadActivity, DevPadStorage


class TestDevPadActivity:
    """Test DevPadActivity dataclass."""

    def test_to_dict(self):
        """to_dict returns all fields."""
        a = DevPadActivity(
            id="1",
            timestamp="2024-01-01T00:00:00",
            activity_type="file_edit",
            title="Edit main.py",
            description="Modified function",
            link_type="file",
            link_target="/src/main.py",
            metadata={"lines": 10},
        )
        d = a.to_dict()
        assert d["id"] == "1"
        assert d["activity_type"] == "file_edit"
        assert d["metadata"] == {"lines": 10}

    def test_from_dict_roundtrip(self):
        """from_dict reverses to_dict."""
        a = DevPadActivity(
            id="2",
            timestamp="2024-01-01",
            activity_type="ai_chat",
            title="Chat",
            description="Asked AI",
            metadata={},
        )
        restored = DevPadActivity.from_dict(a.to_dict())
        assert restored.id == a.id
        assert restored.title == a.title
        assert restored.activity_type == a.activity_type

    def test_default_metadata(self):
        """metadata defaults to empty dict."""
        a = DevPadActivity(
            id="3",
            timestamp="t",
            activity_type="test",
            title="Test",
            description="Desc",
        )
        assert a.metadata == {}


class TestDevPadStorage:
    """Test DevPadStorage with temporary file storage."""

    def _make_storage(self, tmpdir):
        """Create a DevPadStorage with custom file paths."""
        s = DevPadStorage()
        s._loaded = False
        s._activities = []
        s._listeners = []
        return s

    def test_add_activity(self):
        """add_activity creates and returns activity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dev_pad_file = Path(tmpdir) / "dev_pad.json"
            with (
                patch("dev_pad.dev_pad_storage.DEV_PAD_DIR", Path(tmpdir)),
                patch("dev_pad.dev_pad_storage.DEV_PAD_FILE", dev_pad_file),
            ):
                s = DevPadStorage()
                s._loaded = True
                s._activities = []
                s._listeners = []
                a = s.add_activity("file_edit", "Edit", "Edited file")
                assert a.activity_type == "file_edit"
                assert a.title == "Edit"
                assert len(s._activities) == 1

    def test_add_activity_most_recent_first(self):
        """New activities are inserted at the beginning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dev_pad_file = Path(tmpdir) / "dev_pad.json"
            with (
                patch("dev_pad.dev_pad_storage.DEV_PAD_DIR", Path(tmpdir)),
                patch("dev_pad.dev_pad_storage.DEV_PAD_FILE", dev_pad_file),
            ):
                s = DevPadStorage()
                s._loaded = True
                s._activities = []
                s._listeners = []
                s.add_activity("test", "First", "First activity")
                s.add_activity("test", "Second", "Second activity")
                assert s._activities[0].title == "Second"

    def test_max_activities_trimmed(self):
        """Activities beyond max are trimmed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dev_pad_file = Path(tmpdir) / "dev_pad.json"
            with (
                patch("dev_pad.dev_pad_storage.DEV_PAD_DIR", Path(tmpdir)),
                patch("dev_pad.dev_pad_storage.DEV_PAD_FILE", dev_pad_file),
            ):
                s = DevPadStorage()
                s._loaded = True
                s._activities = []
                s._listeners = []
                s._max_activities = 3
                for i in range(5):
                    s.add_activity("test", f"Activity {i}", f"Desc {i}")
                assert len(s._activities) == 3

    def test_update_or_add_updates_existing(self):
        """update_or_add moves existing activity to top."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dev_pad_file = Path(tmpdir) / "dev_pad.json"
            with (
                patch("dev_pad.dev_pad_storage.DEV_PAD_DIR", Path(tmpdir)),
                patch("dev_pad.dev_pad_storage.DEV_PAD_FILE", dev_pad_file),
            ):
                s = DevPadStorage()
                s._loaded = True
                s._activities = []
                s._listeners = []
                s.add_activity("edit", "File A", "Edited A", "file", "/a.py")
                s.add_activity("edit", "File B", "Edited B", "file", "/b.py")
                s.update_or_add_activity("edit", "File A Updated", "Re-edited A", "file", "/a.py")
                assert s._activities[0].title == "File A Updated"
                assert s._activities[0].link_target == "/a.py"

    def test_delete_activity(self):
        """delete_activity removes by ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dev_pad_file = Path(tmpdir) / "dev_pad.json"
            with (
                patch("dev_pad.dev_pad_storage.DEV_PAD_DIR", Path(tmpdir)),
                patch("dev_pad.dev_pad_storage.DEV_PAD_FILE", dev_pad_file),
            ):
                s = DevPadStorage()
                s._loaded = True
                s._activities = []
                s._listeners = []
                a = s.add_activity("test", "To Delete", "Desc")
                s.delete_activity(a.id)
                assert len(s._activities) == 0

    def test_save_and_load(self):
        """Activities persist to JSON and load back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dev_pad_file = Path(tmpdir) / "dev_pad.json"
            with (
                patch("dev_pad.dev_pad_storage.DEV_PAD_DIR", Path(tmpdir)),
                patch("dev_pad.dev_pad_storage.DEV_PAD_FILE", dev_pad_file),
            ):
                s = DevPadStorage()
                s._loaded = True
                s._activities = []
                s._listeners = []
                s.add_activity("test", "Saved Activity", "Should persist")

                # Create new storage and load
                s2 = DevPadStorage()
                s2._loaded = False
                s2._activities = []
                s2._listeners = []
                s2._load()
                assert len(s2._activities) == 1
                assert s2._activities[0].title == "Saved Activity"


class TestMatchesFilter:
    """Test _matches_filter logic."""

    def _make_storage(self):
        s = DevPadStorage()
        s._loaded = True
        s._activities = []
        s._listeners = []
        return s

    def test_matches_type_filter(self):
        """Matches when activity_type is in type_filter set."""
        s = self._make_storage()
        a = DevPadActivity(id="1", timestamp="t", activity_type="file_edit", title="X", description="Y")
        assert s._matches_filter(a, {"file_edit"}, "")

    def test_rejects_wrong_type(self):
        """Rejects when activity_type not in type_filter."""
        s = self._make_storage()
        a = DevPadActivity(id="1", timestamp="t", activity_type="ai_chat", title="X", description="Y")
        assert not s._matches_filter(a, {"file_edit"}, "")

    def test_matches_query_in_title(self):
        """Matches when query found in title."""
        s = self._make_storage()
        a = DevPadActivity(id="1", timestamp="t", activity_type="test", title="Fix Bug", description="")
        assert s._matches_filter(a, None, "fix")

    def test_matches_query_in_description(self):
        """Matches when query found in description."""
        s = self._make_storage()
        a = DevPadActivity(id="1", timestamp="t", activity_type="test", title="X", description="database error")
        assert s._matches_filter(a, None, "database")

    def test_rejects_unmatched_query(self):
        """Rejects when query not found."""
        s = self._make_storage()
        a = DevPadActivity(id="1", timestamp="t", activity_type="test", title="Hello", description="World")
        assert not s._matches_filter(a, None, "missing")

    def test_no_filter_matches_all(self):
        """No type_filter and empty query matches everything."""
        s = self._make_storage()
        a = DevPadActivity(id="1", timestamp="t", activity_type="any", title="Any", description="Anything")
        assert s._matches_filter(a, None, "")


class TestGetActivitiesGroupedByDate:
    """Test grouping and filtering logic."""

    def test_groups_by_date(self):
        """Activities are grouped by date string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dev_pad_file = Path(tmpdir) / "dev_pad.json"
            with (
                patch("dev_pad.dev_pad_storage.DEV_PAD_DIR", Path(tmpdir)),
                patch("dev_pad.dev_pad_storage.DEV_PAD_FILE", dev_pad_file),
            ):
                s = DevPadStorage()
                s._loaded = True
                s._listeners = []
                s._activities = [
                    DevPadActivity(id="1", timestamp="2024-01-15T10:00:00", activity_type="edit", title="A", description=""),
                    DevPadActivity(id="2", timestamp="2024-01-15T11:00:00", activity_type="edit", title="B", description=""),
                    DevPadActivity(id="3", timestamp="2024-01-16T10:00:00", activity_type="edit", title="C", description=""),
                ]
                grouped = s.get_activities_grouped_by_date()
                assert len(grouped) == 2  # Two different dates

    def test_type_filter(self):
        """type_filter restricts results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dev_pad_file = Path(tmpdir) / "dev_pad.json"
            with (
                patch("dev_pad.dev_pad_storage.DEV_PAD_DIR", Path(tmpdir)),
                patch("dev_pad.dev_pad_storage.DEV_PAD_FILE", dev_pad_file),
            ):
                s = DevPadStorage()
                s._loaded = True
                s._listeners = []
                s._activities = [
                    DevPadActivity(id="1", timestamp="2024-01-15T10:00:00", activity_type="edit", title="A", description=""),
                    DevPadActivity(id="2", timestamp="2024-01-15T11:00:00", activity_type="chat", title="B", description=""),
                ]
                grouped = s.get_activities_grouped_by_date(type_filter={"edit"})
                total = sum(len(v) for v in grouped.values())
                assert total == 1

    def test_limit_respected(self):
        """limit parameter caps total results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dev_pad_file = Path(tmpdir) / "dev_pad.json"
            with (
                patch("dev_pad.dev_pad_storage.DEV_PAD_DIR", Path(tmpdir)),
                patch("dev_pad.dev_pad_storage.DEV_PAD_FILE", dev_pad_file),
            ):
                s = DevPadStorage()
                s._loaded = True
                s._listeners = []
                s._activities = [
                    DevPadActivity(
                        id=str(i),
                        timestamp=f"2024-01-15T{10 + i}:00:00",
                        activity_type="edit",
                        title=f"Act {i}",
                        description="",
                    )
                    for i in range(10)
                ]
                grouped = s.get_activities_grouped_by_date(limit=3)
                total = sum(len(v) for v in grouped.values())
                assert total == 3
