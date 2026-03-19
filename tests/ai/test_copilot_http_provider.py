"""Tests for CopilotHTTPProvider SSE parsing and configuration logic."""

import json

from ai.copilot_http_provider import CopilotHTTPProvider

_THINKING_MARKER = "\u200b"
_CONTENT_MARKER = "\u200c"


class TestParseSSELine:
    """Test _parse_sse_line for OpenAI-compatible SSE events."""

    def _make_provider(self):
        p = CopilotHTTPProvider.__new__(CopilotHTTPProvider)
        p._stop_requested = False
        p._current_response = None
        return p

    def test_content_delta(self):
        """Standard content delta returns content-marked text."""
        p = self._make_provider()
        data = {"choices": [{"delta": {"content": "hello world"}}]}
        line = f"data: {json.dumps(data)}"
        result = p._parse_sse_line(line)
        assert result == f"{_CONTENT_MARKER}hello world"

    def test_empty_content_returns_none(self):
        """Empty content in delta returns None."""
        p = self._make_provider()
        data = {"choices": [{"delta": {"content": ""}}]}
        line = f"data: {json.dumps(data)}"
        assert p._parse_sse_line(line) is None

    def test_done_marker(self):
        """[DONE] marker returns None."""
        p = self._make_provider()
        assert p._parse_sse_line("data: [DONE]") is None

    def test_empty_choices_returns_none(self):
        """Empty choices list returns None."""
        p = self._make_provider()
        data = {"choices": []}
        line = f"data: {json.dumps(data)}"
        assert p._parse_sse_line(line) is None

    def test_no_delta_returns_finish_signal(self):
        """Choice with finish_reason returns finish signal dict."""
        p = self._make_provider()
        data = {"choices": [{"finish_reason": "stop"}]}
        line = f"data: {json.dumps(data)}"
        result = p._parse_sse_line(line)
        assert result == {"_finish_reason": "stop"}

    def test_non_data_line_ignored(self):
        """Lines not starting with 'data: ' are ignored."""
        p = self._make_provider()
        assert p._parse_sse_line("event: message") is None
        assert p._parse_sse_line("") is None
        assert p._parse_sse_line(": comment") is None

    def test_invalid_json_ignored(self):
        """Malformed JSON after 'data: ' is ignored."""
        p = self._make_provider()
        assert p._parse_sse_line("data: {broken json") is None

    def test_role_only_delta_returns_none(self):
        """Delta with only role (no content) returns None."""
        p = self._make_provider()
        data = {"choices": [{"delta": {"role": "assistant"}}]}
        line = f"data: {json.dumps(data)}"
        assert p._parse_sse_line(line) is None


class TestAvailability:
    """Test is_available with different token sources.

    Note: is_available only returns True for Copilot OAuth tokens, not regular
    GitHub PATs (ghp_), since those often lack Copilot scope and would fail.
    """

    def test_not_available_without_any_token(self, monkeypatch):
        """Provider is not available when no token source exists."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        import ai.copilot_http_provider as mod

        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", mod.Path("/tmp/nonexistent_copilot_apps.json"))
        p = CopilotHTTPProvider()
        assert p.is_available is False

    def test_not_available_with_regular_pat(self, monkeypatch, tmp_path):
        """Provider is NOT available with a regular GitHub PAT (ghp_).

        Regular PATs often lack Copilot scope, so we don't count them as available.
        Users must authenticate via OAuth or use a Copilot-specific token.
        """
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123456")
        import ai.copilot_http_provider as mod

        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", mod.Path("/tmp/nonexistent_copilot_apps.json"))
        p = CopilotHTTPProvider()
        assert p.is_available is False

    def test_available_with_oauth_token_in_env(self, monkeypatch, tmp_path):
        """Provider is available when GITHUB_TOKEN is a Copilot OAuth token (gho_)."""
        monkeypatch.setenv("GITHUB_TOKEN", "gho_copilot_oauth_token_123456")
        import ai.copilot_http_provider as mod

        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", mod.Path("/tmp/nonexistent_copilot_apps.json"))
        p = CopilotHTTPProvider()
        assert p.is_available is True

    def test_available_with_oauth_token_in_api_keys(self, monkeypatch, tmp_path):
        """Provider is available when api_keys.json has a Copilot OAuth token (gho_)."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        import ai.copilot_http_provider as mod

        keys_file = tmp_path / "api_keys.json"
        keys_file.write_text(json.dumps({"github": "gho_copilot_oauth_token_123456"}))
        monkeypatch.setattr(mod, "_API_KEYS_PATH", keys_file)
        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", mod.Path("/tmp/nonexistent_copilot_apps.json"))
        p = CopilotHTTPProvider()
        assert p.is_available is True

    def test_available_with_copilot_apps_file(self, monkeypatch, tmp_path):
        """Provider is available when Copilot apps.json exists."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        import ai.copilot_http_provider as mod

        apps_file = tmp_path / "apps.json"
        apps_data = {"github-copilot-app": {"oauth_token": "gho_copilot_token_123456"}}
        apps_file.write_text(json.dumps(apps_data))
        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", apps_file)
        p = CopilotHTTPProvider()
        assert p.is_available is True

    def test_empty_models_without_token(self, monkeypatch):
        """get_available_models returns empty list when no token (no fallback)."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        import ai.copilot_http_provider as mod

        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", mod.Path("/tmp/nonexistent_copilot_apps.json"))
        # Reset class-level cache
        CopilotHTTPProvider._cached_models = None
        CopilotHTTPProvider._models_fetched = False
        p = CopilotHTTPProvider()
        models = p.get_available_models()
        assert models == []


class TestTokenResolutionOrder:
    """Test that token resolution follows the correct priority order.

    Note: _load_github_tokens() only includes env tokens with gho_ prefix,
    since regular PATs (ghp_) often lack Copilot scope.
    """

    def test_copilot_apps_takes_priority(self, monkeypatch, tmp_path):
        """Copilot apps.json is tried first (most reliable for Copilot)."""
        monkeypatch.setenv("GITHUB_TOKEN", "gho_env_token")
        import ai.copilot_http_provider as mod

        keys_file = tmp_path / "api_keys.json"
        keys_file.write_text(json.dumps({"github": "file_token"}))
        monkeypatch.setattr(mod, "_API_KEYS_PATH", keys_file)

        apps_file = tmp_path / "apps.json"
        apps_file.write_text(json.dumps({"app": {"oauth_token": "oauth_token"}}))
        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", apps_file)

        tokens = mod._load_github_tokens()
        assert tokens[0] == "oauth_token"
        assert "file_token" in tokens
        assert "gho_env_token" in tokens

    def test_file_before_env(self, monkeypatch, tmp_path):
        """api_keys.json comes before GITHUB_TOKEN env var."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        import ai.copilot_http_provider as mod

        keys_file = tmp_path / "api_keys.json"
        keys_file.write_text(json.dumps({"github": "file_token"}))
        monkeypatch.setattr(mod, "_API_KEYS_PATH", keys_file)

        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", mod.Path("/tmp/nonexistent_zen_test_apps.json"))

        tokens = mod._load_github_tokens()
        assert tokens[0] == "file_token"

    def test_falls_back_to_oauth_env_token(self, monkeypatch, tmp_path):
        """Falls back to GITHUB_TOKEN env when no other sources (if gho_ prefix)."""
        monkeypatch.setenv("GITHUB_TOKEN", "gho_oauth_env_token")
        import ai.copilot_http_provider as mod

        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", mod.Path("/tmp/nonexistent_zen_test_apps.json"))

        tokens = mod._load_github_tokens()
        assert tokens == ["gho_oauth_env_token"]

    def test_ignores_regular_pat_in_env(self, monkeypatch, tmp_path):
        """Regular PATs (ghp_) in env are ignored — they often lack Copilot scope."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_regular_pat")
        import ai.copilot_http_provider as mod

        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", mod.Path("/tmp/nonexistent_zen_test_apps.json"))

        tokens = mod._load_github_tokens()
        assert tokens == []

    def test_no_duplicates(self, monkeypatch, tmp_path):
        """Same token from multiple sources is not duplicated."""
        monkeypatch.setenv("GITHUB_TOKEN", "gho_same_token")
        import ai.copilot_http_provider as mod

        keys_file = tmp_path / "api_keys.json"
        keys_file.write_text(json.dumps({"github": "gho_same_token"}))
        monkeypatch.setattr(mod, "_API_KEYS_PATH", keys_file)

        monkeypatch.setattr(mod, "_COPILOT_APPS_PATH", mod.Path("/tmp/nonexistent_zen_test_apps.json"))

        tokens = mod._load_github_tokens()
        assert tokens == ["gho_same_token"]


class TestStop:
    """Test stop cancellation."""

    def test_stop_sets_flag(self):
        """stop() sets the _stop_requested flag."""
        p = CopilotHTTPProvider()
        assert p._stop_requested is False
        p.stop()
        assert p._stop_requested is True


class TestDefaultModel:
    """Test default model constant."""

    def test_default_model_is_set(self):
        """DEFAULT_MODEL is defined and non-empty."""
        assert CopilotHTTPProvider.DEFAULT_MODEL
        assert isinstance(CopilotHTTPProvider.DEFAULT_MODEL, str)
