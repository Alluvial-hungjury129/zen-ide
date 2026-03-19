"""Tests for SettingsManager logic."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from shared.settings.settings_manager import (
    DEFAULT_SETTINGS,
    _deep_merge,
    get_setting,
    load_settings,
    set_setting,
)


class TestDeepMerge:
    """Test _deep_merge function."""

    def test_simple_override(self):
        """Override takes precedence for simple values."""
        result = _deep_merge({"a": 1, "b": 2}, {"b": 3})
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        """Nested dicts are merged recursively."""
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3, "c": 4}}
        result = _deep_merge(base, override)
        assert result == {"x": {"a": 1, "b": 3, "c": 4}}

    def test_deeply_nested(self):
        """Three-level deep merge works."""
        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"d": 3, "e": 4}}}
        result = _deep_merge(base, override)
        assert result == {"a": {"b": {"c": 1, "d": 3, "e": 4}}}

    def test_override_adds_new_keys(self):
        """Override can add entirely new keys."""
        result = _deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_override_replaces_dict_with_scalar(self):
        """Override scalar replaces base dict."""
        result = _deep_merge({"a": {"b": 1}}, {"a": "flat"})
        assert result == {"a": "flat"}

    def test_base_not_mutated(self):
        """Original base dict is not mutated."""
        base = {"a": 1}
        _deep_merge(base, {"a": 2})
        assert base == {"a": 1}

    def test_empty_override(self):
        """Empty override returns copy of base."""
        result = _deep_merge({"a": 1}, {})
        assert result == {"a": 1}

    def test_empty_base(self):
        """Empty base returns override."""
        result = _deep_merge({}, {"a": 1})
        assert result == {"a": 1}


class TestGetSetting:
    """Test dot-notation path resolution."""

    def test_simple_key(self):
        """Simple top-level key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
            ):
                settings_file.write_text(json.dumps({"theme": "dracula"}))
                load_settings()
                assert get_setting("theme") == "dracula"

    def test_nested_key(self):
        """Dot-separated nested key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
            ):
                settings_file.write_text(json.dumps({"editor": {"tab_size": 8}}))
                load_settings()
                assert get_setting("editor.tab_size") == 8

    def test_missing_key_returns_default(self):
        """Missing key returns the provided default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
            ):
                settings_file.write_text(json.dumps({}))
                load_settings()
                assert get_setting("nonexistent", "fallback") == "fallback"


class TestSetSetting:
    """Test dot-notation setter."""

    def test_set_simple(self):
        """Set a top-level key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
            ):
                load_settings()
                set_setting("theme", "dracula")
                assert get_setting("theme") == "dracula"

    def test_set_nested(self):
        """Set a nested key creates intermediate dicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
            ):
                load_settings()
                set_setting("ai.provider", "copilot_api")
                assert get_setting("ai.provider") == "copilot_api"

    def test_persists_to_file(self):
        """set_setting auto-saves to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
            ):
                load_settings()
                set_setting("theme", "matrix")
                # Read file directly
                data = json.loads(settings_file.read_text())
                assert data["theme"] == "matrix"


class TestLoadSettings:
    """Test settings loading with fallbacks."""

    def test_missing_file_uses_defaults(self):
        """Missing settings file uses DEFAULT_SETTINGS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_backup = Path(tmpdir) / "settings.json.bak"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager.SETTINGS_BACKUP", settings_backup),
                patch("shared.settings.settings_manager._settings", None),
            ):
                result = load_settings()
                assert result["theme"] == DEFAULT_SETTINGS["theme"]

    def test_merges_with_defaults(self):
        """Partial settings file is merged with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
            ):
                # Only set theme, rest should come from defaults
                settings_file.write_text(json.dumps({"theme": "dracula"}))
                result = load_settings()
                assert result["theme"] == "dracula"
                # Default editor settings should still be present
                assert "editor" in result
                assert "tab_size" in result["editor"]

    def test_invalid_json_backed_up(self):
        """Invalid JSON file is backed up, last good backup restored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_backup = Path(tmpdir) / "settings.json.bak"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager.SETTINGS_BACKUP", settings_backup),
                patch("shared.settings.settings_manager._settings", None),
            ):
                settings_file.write_text("{invalid json")
                result = load_settings()
                assert result["theme"] == DEFAULT_SETTINGS["theme"]
                # Original file should be renamed to backup
                backups = list(Path(tmpdir).glob("settings.json.invalid-*"))
                assert len(backups) == 1

    def test_invalid_json_restores_from_backup(self):
        """Invalid JSON file restores from .bak if available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_backup = Path(tmpdir) / "settings.json.bak"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager.SETTINGS_BACKUP", settings_backup),
                patch("shared.settings.settings_manager._settings", None),
            ):
                # Create a valid backup with custom theme
                settings_backup.write_text(json.dumps({"theme": "my_custom_theme"}))
                # Write invalid JSON to main file
                settings_file.write_text("{invalid json")
                result = load_settings()
                # Should restore from backup, not defaults
                assert result["theme"] == "my_custom_theme"


class TestAtomicWrite:
    """Test atomic write protection."""

    def test_backup_created_on_save(self):
        """Backup file is created when saving settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_backup = Path(tmpdir) / "settings.json.bak"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_BACKUP", settings_backup),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
                patch("shared.settings.settings_manager._file_settings", None),
            ):
                # Create initial file
                settings_file.write_text(json.dumps({"theme": "original"}))
                load_settings()
                set_setting("theme", "updated")
                # Backup should exist with original content
                assert settings_backup.exists()
                backup_data = json.loads(settings_backup.read_text())
                assert backup_data["theme"] == "original"

    def test_batch_mode_single_write(self):
        """Batch mode only writes once at the end."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_backup = Path(tmpdir) / "settings.json.bak"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_BACKUP", settings_backup),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
                patch("shared.settings.settings_manager._file_settings", None),
            ):
                from shared.settings.settings_manager import has_pending_changes, save_settings

                load_settings()
                # Multiple changes without persist
                set_setting("editor.font_size", 14, persist=False)
                set_setting("editor.tab_size", 2, persist=False)
                set_setting("theme", "dracula", persist=False)
                # Should have pending changes
                assert has_pending_changes()
                # Not yet written to file (file has defaults from load_settings)
                data_before = json.loads(settings_file.read_text())
                assert data_before.get("theme") != "dracula"
                # Now save
                save_settings()
                # File should have all changes
                data_after = json.loads(settings_file.read_text())
                assert data_after["theme"] == "dracula"
                assert data_after["editor"]["font_size"] == 14
                assert data_after["editor"]["tab_size"] == 2

    def test_restore_from_backup(self):
        """Can restore settings from backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_backup = Path(tmpdir) / "settings.json.bak"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_BACKUP", settings_backup),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
                patch("shared.settings.settings_manager._file_settings", None),
            ):
                from shared.settings.settings_manager import restore_from_backup

                # Create a backup file
                settings_backup.write_text(json.dumps({"theme": "backup_theme"}))
                # Current file is different
                settings_file.write_text(json.dumps({"theme": "current_theme"}))
                load_settings()
                # Restore from backup
                result = restore_from_backup()
                assert result is True
                # Settings should match backup
                data = json.loads(settings_file.read_text())
                assert data["theme"] == "backup_theme"


class TestMigrateEditorFonts:
    """Test migration of editor.font_* → fonts.editor."""

    def test_migrates_old_format(self):
        """Old editor.font_* keys are moved to fonts.editor on load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
                patch("shared.settings.settings_manager._file_settings", None),
            ):
                settings_file.write_text(
                    json.dumps(
                        {
                            "editor": {
                                "font_family": "Monaco",
                                "font_size": 18,
                                "font_weight": "bold",
                                "tab_size": 4,
                            }
                        }
                    )
                )
                result = load_settings()
                # fonts.editor should have migrated values
                assert result["fonts"]["editor"]["family"] == "Monaco"
                assert result["fonts"]["editor"]["size"] == 18
                assert result["fonts"]["editor"]["weight"] == "bold"
                # Old keys should be removed from editor section
                persisted = json.loads(settings_file.read_text())
                assert "font_family" not in persisted["editor"]
                assert "font_size" not in persisted["editor"]
                assert "font_weight" not in persisted["editor"]
                # Non-font editor keys preserved
                assert persisted["editor"]["tab_size"] == 4

    def test_no_migration_when_already_new_format(self):
        """No migration when fonts.editor already exists and no old keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_dir = Path(tmpdir)
            with (
                patch("shared.settings.settings_manager.SETTINGS_FILE", settings_file),
                patch("shared.settings.settings_manager.SETTINGS_DIR", settings_dir),
                patch("shared.settings.settings_manager._settings", None),
                patch("shared.settings.settings_manager._file_settings", None),
            ):
                settings_file.write_text(
                    json.dumps(
                        {
                            "editor": {"tab_size": 4},
                            "fonts": {"editor": {"family": "Fira Code", "size": 15, "weight": "normal"}},
                        }
                    )
                )
                result = load_settings()
                assert result["fonts"]["editor"]["family"] == "Fira Code"
                assert result["fonts"]["editor"]["size"] == 15
