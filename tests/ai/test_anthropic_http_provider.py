"""Tests for AnthropicHTTPProvider SSE parsing logic."""

import json

from ai.anthropic_http_provider import AnthropicHTTPProvider

_THINKING_MARKER = "\u200b"
_CONTENT_MARKER = "\u200c"


class TestParseSSELine:
    """Test _parse_sse_line for various Anthropic SSE event types."""

    def _make_provider(self):
        p = AnthropicHTTPProvider.__new__(AnthropicHTTPProvider)
        p._stop_requested = False
        p._current_response = None
        return p

    def test_text_delta(self):
        """content_block_delta with text_delta returns content-marked text."""
        p = self._make_provider()
        data = {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hello"}}
        line = f"data: {json.dumps(data)}"
        result = p._parse_sse_line(line)
        assert result == f"{_CONTENT_MARKER}hello"

    def test_thinking_delta(self):
        """content_block_delta with thinking_delta returns thinking-marked text."""
        p = self._make_provider()
        data = {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "let me think"}}
        line = f"data: {json.dumps(data)}"
        result = p._parse_sse_line(line)
        assert result == f"{_THINKING_MARKER}let me think"

    def test_empty_text_delta_returns_none(self):
        """Empty text in text_delta returns None."""
        p = self._make_provider()
        data = {"type": "content_block_delta", "delta": {"type": "text_delta", "text": ""}}
        line = f"data: {json.dumps(data)}"
        assert p._parse_sse_line(line) is None

    def test_message_delta_end_turn(self):
        """message_delta with end_turn returns stop_reason signal."""
        p = self._make_provider()
        data = {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}
        line = f"data: {json.dumps(data)}"
        result = p._parse_sse_line(line)
        assert result == {"_stop_reason": "end_turn"}

    def test_error_event(self):
        """error event returns error message as content."""
        p = self._make_provider()
        data = {"type": "error", "error": {"message": "Rate limited"}}
        line = f"data: {json.dumps(data)}"
        result = p._parse_sse_line(line)
        assert _CONTENT_MARKER in result
        assert "Rate limited" in result

    def test_non_data_line_ignored(self):
        """Lines not starting with 'data: ' are ignored."""
        p = self._make_provider()
        assert p._parse_sse_line("event: content_block_delta") is None
        assert p._parse_sse_line("") is None
        assert p._parse_sse_line(": comment") is None

    def test_invalid_json_ignored(self):
        """Malformed JSON after 'data: ' is ignored."""
        p = self._make_provider()
        assert p._parse_sse_line("data: {not valid json}") is None

    def test_content_block_start_ignored(self):
        """content_block_start events produce no output."""
        p = self._make_provider()
        data = {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
        line = f"data: {json.dumps(data)}"
        assert p._parse_sse_line(line) is None

    def test_message_start_ignored(self):
        """message_start events produce no output."""
        p = self._make_provider()
        data = {"type": "message_start", "message": {"id": "msg_123"}}
        line = f"data: {json.dumps(data)}"
        assert p._parse_sse_line(line) is None

    def test_message_stop_ignored(self):
        """message_stop events produce no output."""
        p = self._make_provider()
        data = {"type": "message_stop"}
        line = f"data: {json.dumps(data)}"
        assert p._parse_sse_line(line) is None


class TestAvailability:
    """Test is_available and model listing."""

    def test_not_available_without_key(self, monkeypatch):
        """Provider is not available when no API key is set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # Ensure config file path points to non-existent file
        import ai.anthropic_http_provider as mod

        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        p = AnthropicHTTPProvider()
        assert p.is_available is False

    def test_available_with_env_key(self, monkeypatch):
        """Provider is available when ANTHROPIC_API_KEY env var is set."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        p = AnthropicHTTPProvider()
        assert p.is_available is True

    def test_empty_models_without_key(self, monkeypatch):
        """get_available_models returns empty list when no API key (no fallback)."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        import ai.anthropic_http_provider as mod

        monkeypatch.setattr(mod, "_API_KEYS_PATH", mod.Path("/tmp/nonexistent_zen_test_keys.json"))
        # Reset class-level cache
        AnthropicHTTPProvider._cached_models = None
        AnthropicHTTPProvider._models_fetched = False
        p = AnthropicHTTPProvider()
        models = p.get_available_models()
        assert models == []


class TestStop:
    """Test stop cancellation."""

    def test_stop_sets_flag(self):
        """stop() sets the _stop_requested flag."""
        p = AnthropicHTTPProvider()
        assert p._stop_requested is False
        p.stop()
        assert p._stop_requested is True
