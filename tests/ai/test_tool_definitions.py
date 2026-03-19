"""Tests for ai.tool_definitions module."""

from ai.tool_definitions import TOOLS, tools_for_anthropic, tools_for_copilot


class TestToolDefinitions:
    """Test the tool definition schemas."""

    def test_tools_not_empty(self):
        assert len(TOOLS) > 0

    def test_all_tools_have_required_fields(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert tool["parameters"]["type"] == "object"
            assert "properties" in tool["parameters"]
            assert "required" in tool["parameters"]

    def test_expected_tools_present(self):
        names = {t["name"] for t in TOOLS}
        assert "read_file" in names
        assert "write_file" in names
        assert "edit_file" in names
        assert "list_files" in names
        assert "search_files" in names
        assert "run_command" in names


class TestAnthropicFormat:
    """Test Anthropic API format conversion."""

    def test_format_has_input_schema(self):
        tools = tools_for_anthropic()
        assert len(tools) == len(TOOLS)
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert "parameters" not in tool

    def test_input_schema_matches_parameters(self):
        tools = tools_for_anthropic()
        for i, tool in enumerate(tools):
            assert tool["input_schema"] == TOOLS[i]["parameters"]


class TestCopilotFormat:
    """Test Copilot API format conversion."""

    def test_format_has_function_wrapper(self):
        tools = tools_for_copilot()
        assert len(tools) == len(TOOLS)
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn

    def test_parameters_match(self):
        tools = tools_for_copilot()
        for i, tool in enumerate(tools):
            assert tool["function"]["parameters"] == TOOLS[i]["parameters"]
