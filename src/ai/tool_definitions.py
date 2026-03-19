"""
Tool definitions for AI providers in Zen IDE.

Defines the tools available for AI agentic coding (read, write, edit,
list, search, run) in a provider-agnostic format with conversion
functions for Anthropic and Copilot API formats.
"""

# Provider-agnostic tool definitions.
# Each tool has: name, description, parameters (JSON Schema).

TOOLS = [
    {
        "name": "read_file",
        "description": (
            "Read the contents of a file at the given path. "
            "Use this to examine existing code, configuration, or documentation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to workspace root)",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Create a new file or completely overwrite an existing file. "
            "Use this for creating new files. For modifying existing files, "
            "prefer edit_file to make surgical changes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write (relative to workspace root)",
                },
                "content": {
                    "type": "string",
                    "description": "The complete file content to write",
                },
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Make a targeted edit to an existing file by replacing a specific "
            "text string with new text. The old_text must match exactly one "
            "location in the file. Include enough surrounding context to make "
            "the match unique."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit (relative to workspace root)",
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace (must match exactly one location)",
                },
                "new_text": {
                    "type": "string",
                    "description": "The replacement text",
                },
            },
            "required": ["file_path", "old_text", "new_text"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "List files matching a glob pattern in the workspace. Use this to discover project structure and find files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": 'Glob pattern (e.g. "**/*.py", "src/**/*.ts", "*.md")',
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (relative to workspace root, default: workspace root)",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "search_files",
        "description": (
            "Search file contents for a regex pattern (like grep). Returns matching lines with file paths and line numbers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (relative to workspace root, default: workspace root)",
                },
                "include": {
                    "type": "string",
                    "description": 'File glob to include (e.g. "*.py", "*.ts")',
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a shell command in the workspace directory. "
            "Use for build commands, tests, git operations, installing packages, etc. "
            "Commands run with a timeout of 30 seconds."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
            },
            "required": ["command"],
        },
    },
]


def tools_for_anthropic() -> list[dict]:
    """Convert tool definitions to Anthropic API format."""
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["parameters"],
        }
        for tool in TOOLS
    ]


def tools_for_copilot() -> list[dict]:
    """Convert tool definitions to Copilot API format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in TOOLS
    ]
