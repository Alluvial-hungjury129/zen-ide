"""Tests for ApiKeySetupPopup (src/popups/api_key_setup_popup.py)."""

import tempfile

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    parse_popup_source,
    read_popup_source,
)


class TestApiKeySetupPopupStructure:
    """Verify ApiKeySetupPopup structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("api_key_setup_popup.py")
        assert class_inherits(tree, "ApiKeySetupPopup", "NvimPopup")

    def test_has_create_content(self):
        tree = parse_popup_source("api_key_setup_popup.py")
        cls = find_class(tree, "ApiKeySetupPopup")
        assert find_method(cls, "_create_content") is not None

    def test_has_on_key_pressed(self):
        tree = parse_popup_source("api_key_setup_popup.py")
        cls = find_class(tree, "ApiKeySetupPopup")
        assert find_method(cls, "_on_key_pressed") is not None

    def test_has_save_key(self):
        tree = parse_popup_source("api_key_setup_popup.py")
        cls = find_class(tree, "ApiKeySetupPopup")
        assert find_method(cls, "_save_key") is not None

    def test_has_validate_key(self):
        tree = parse_popup_source("api_key_setup_popup.py")
        cls = find_class(tree, "ApiKeySetupPopup")
        assert find_method(cls, "_validate_key") is not None

    def test_has_present(self):
        tree = parse_popup_source("api_key_setup_popup.py")
        cls = find_class(tree, "ApiKeySetupPopup")
        assert find_method(cls, "present") is not None


class TestApiKeySetupKeyHandling:
    """Verify key handling patterns."""

    def test_escape_closes(self):
        source = read_popup_source("api_key_setup_popup.py")
        assert "KEY_Escape" in source

    def test_enter_saves(self):
        source = read_popup_source("api_key_setup_popup.py")
        assert "activate" in source


class TestApiKeySetupValidation:
    """Verify validation logic."""

    def test_has_key_validation(self):
        source = read_popup_source("api_key_setup_popup.py")
        assert "_validate_key" in source
        assert "too short" in source.lower() or "required" in source.lower()


class TestApiKeySetupProviderSupport:
    """Verify all providers are supported."""

    def test_anthropic_provider(self):
        source = read_popup_source("api_key_setup_popup.py")
        assert "anthropic_api" in source
        assert "ANTHROPIC_API_KEY" in source

    def test_copilot_provider(self):
        source = read_popup_source("api_key_setup_popup.py")
        assert "copilot_api" in source
        assert "GITHUB_TOKEN" in source

    def test_password_masking(self):
        source = read_popup_source("api_key_setup_popup.py")
        assert "set_visibility" in source

    def test_copilot_stores_as_github_key(self):
        source = read_popup_source("api_key_setup_popup.py")
        # copilot_api should store under "github" key field
        assert '"github"' in source


class TestApiKeysFileIO:
    """Test save/load of api_keys.json."""

    def test_load_nonexistent_returns_empty(self, monkeypatch):
        import popups.api_key_setup_popup as mod

        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        assert mod._load_api_keys() == {}

    def test_save_and_load_roundtrip(self, monkeypatch):
        import popups.api_key_setup_popup as mod

        with tempfile.TemporaryDirectory() as tmpdir:
            keys_path = mod.Path(tmpdir) / "api_keys.json"
            monkeypatch.setattr(mod, "_API_KEYS_PATH", keys_path)

            data = {"anthropic": "sk-ant-test-key-123", "github": "ghp-test-key-456"}
            mod._save_api_keys(data)

            loaded = mod._load_api_keys()
            assert loaded == data

    def test_save_creates_parent_directory(self, monkeypatch):
        import popups.api_key_setup_popup as mod

        with tempfile.TemporaryDirectory() as tmpdir:
            nested = mod.Path(tmpdir) / "nested" / "dir" / "api_keys.json"
            monkeypatch.setattr(mod, "_API_KEYS_PATH", nested)

            mod._save_api_keys({"anthropic": "test"})
            assert nested.exists()

    def test_save_preserves_existing_keys(self, monkeypatch):
        import popups.api_key_setup_popup as mod

        with tempfile.TemporaryDirectory() as tmpdir:
            keys_path = mod.Path(tmpdir) / "api_keys.json"
            monkeypatch.setattr(mod, "_API_KEYS_PATH", keys_path)

            # Save initial key
            mod._save_api_keys({"anthropic": "sk-ant-first"})

            # Load and add another key
            data = mod._load_api_keys()
            data["github"] = "ghp-second"
            mod._save_api_keys(data)

            # Both keys should be present
            loaded = mod._load_api_keys()
            assert loaded["anthropic"] == "sk-ant-first"
            assert loaded["github"] == "ghp-second"

    def test_load_corrupted_file_returns_empty(self, monkeypatch):
        import popups.api_key_setup_popup as mod

        with tempfile.TemporaryDirectory() as tmpdir:
            keys_path = mod.Path(tmpdir) / "api_keys.json"
            keys_path.write_text("not valid json {{{")
            monkeypatch.setattr(mod, "_API_KEYS_PATH", keys_path)

            assert mod._load_api_keys() == {}


class TestShowApiKeySetupHelper:
    """Verify the module-level helper function exists."""

    def test_show_api_key_setup_exists(self):
        source = read_popup_source("api_key_setup_popup.py")
        assert "def show_api_key_setup" in source
