"""Tests for inline completion provider — prompt building and response cleaning."""

from editor.inline_completion.inline_completion_provider import (
    InlineCompletionProvider,
    _dedupe_suggestions,
)
from tests.editor.inline_completion.test_helpers import make_completion_context as _make_context

# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def setup_method(self):
        self.provider = InlineCompletionProvider()

    def test_prompt_contains_language(self):
        ctx = _make_context(language="python")
        prompt = self.provider._build_prompt(ctx)
        assert "python" in prompt

    def test_prompt_contains_prefix_and_suffix(self):
        ctx = _make_context(prefix="import os\ndef foo(", suffix="):\n    pass")
        prompt = self.provider._build_prompt(ctx)
        assert "import os" in prompt
        assert "def foo(" in prompt
        assert "):\n    pass" in prompt

    def test_prompt_contains_cursor_marker(self):
        ctx = _make_context()
        prompt = self.provider._build_prompt(ctx)
        assert "█" in prompt

    def test_prompt_contains_filename(self):
        """Prompt uses language context and filename."""
        ctx = _make_context(file_path="/home/user/project/main.py")
        prompt = self.provider._build_prompt(ctx)
        assert "█" in prompt
        assert "python" in prompt
        assert "main.py" in prompt

    def test_prompt_no_file_info_when_empty_path(self):
        ctx = _make_context(file_path="")
        prompt = self.provider._build_prompt(ctx)
        assert "File:" not in prompt

    def test_prompt_instructions_no_markdown(self):
        """FIM prompts don't include instructions — the system message handles that."""
        ctx = _make_context()
        prompt = self.provider._build_prompt(ctx)
        # FIM prompt is code-only, instructions are in the system message
        assert "```python" in prompt
        assert "█" in prompt


# ---------------------------------------------------------------------------
# _clean_response
# ---------------------------------------------------------------------------


class TestCleanResponse:
    def setup_method(self):
        self.provider = InlineCompletionProvider()

    def test_strips_markdown_fences(self):
        response = "```python\nname, age):\n    pass\n```"
        result = self.provider._clean_response(response)
        assert result == "name, age):\n    pass"

    def test_strips_backticks(self):
        result = self.provider._clean_response("`hello`")
        assert result == "hello"

    def test_empty_response(self):
        result = self.provider._clean_response("")
        assert result == ""

    def test_whitespace_only(self):
        result = self.provider._clean_response("   \n  ")
        assert result == ""

    def test_multiline_completion(self):
        response = "name, age):\n    self.name = name\n    self.age = age"
        result = self.provider._clean_response(response)
        assert "self.name = name" in result
        assert "self.age = age" in result

    def test_preserves_leading_newline(self):
        """Leading newline signals completion starts on a new line (e.g. function body)."""
        response = "\n    authorizer = event['requestContext']"
        result = self.provider._clean_response(response)
        assert result.startswith("\n")
        assert "authorizer" in result

    def test_preserves_leading_newline_multiline(self):
        """Multi-line body after def should keep leading newline."""
        response = "\n    x = 1\n    return x"
        result = self.provider._clean_response(response)
        assert result == "\n    x = 1\n    return x"

    def test_no_leading_newline_for_inline(self):
        """Inline continuation should NOT get a leading newline."""
        response = "nse = requests.get(url)"
        result = self.provider._clean_response(response)
        assert not result.startswith("\n")
        assert result == "nse = requests.get(url)"


# ---------------------------------------------------------------------------
# _deduplicate
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def setup_method(self):
        self.provider = InlineCompletionProvider()

    def test_strips_prefix_overlap(self):
        ctx = _make_context(prefix="import os\ndef hello(")
        completion = "import os\nname):"
        result = self.provider._deduplicate(completion, ctx)
        assert result == "name):"

    def test_strips_suffix_overlap(self):
        ctx = _make_context(suffix=")\n    pass\n    return True")
        completion = "name):\n    pass\n    return True"
        result = self.provider._deduplicate(completion, ctx)
        assert "name):" in result

    def test_no_overlap(self):
        ctx = _make_context()
        completion = "name, age):"
        result = self.provider._deduplicate(completion, ctx)
        assert result == "name, age):"

    def test_strips_typed_prefix_overlap(self):
        """User typed 'respo', AI returns 'response = ...' — strip 'respo' prefix."""
        ctx = _make_context(prefix="    respo", suffix="\n")
        completion = "response = requests.get(url)"
        result = self.provider._deduplicate(completion, ctx)
        assert result == "nse = requests.get(url)"

    def test_strips_typed_prefix_overlap_with_indent(self):
        """User typed '    respo', AI returns '    response = ...' — strip overlap."""
        ctx = _make_context(prefix="    respo", suffix="\n")
        completion = "    response = requests.get(url)"
        result = self.provider._deduplicate(completion, ctx)
        assert result == "nse = requests.get(url)"

    def test_strips_full_word_typed(self):
        """User typed full word, AI returns same word + more."""
        ctx = _make_context(prefix="response", suffix="\n")
        completion = "response = True"
        result = self.provider._deduplicate(completion, ctx)
        assert result == " = True"

    def test_no_false_positive_on_unrelated(self):
        """No overlap when completion doesn't start with typed text."""
        ctx = _make_context(prefix="    respo", suffix="\n")
        completion = "nse = True"
        result = self.provider._deduplicate(completion, ctx)
        assert result == "nse = True"

    def test_strips_prefix_overlap_multiline(self):
        """Prefix overlap with multiline completion."""
        ctx = _make_context(prefix="    respo", suffix="\n")
        completion = "response = {\n    'key': 'val'\n}"
        result = self.provider._deduplicate(completion, ctx)
        assert result == "nse = {\n    'key': 'val'\n}"

    def test_entire_completion_is_overlap(self):
        """User already typed everything the AI suggests."""
        ctx = _make_context(prefix="response", suffix="\n")
        completion = "response"
        result = self.provider._deduplicate(completion, ctx)
        assert result == ""

    def test_preserves_leading_newline_for_new_block(self):
        """Completion starting with newline after 'def handler():' keeps newline."""
        ctx = _make_context(prefix="def handler(event, context):", suffix="\n\n")
        completion = "\n    authorizer = event['ctx']\n    return authorizer"
        result = self.provider._deduplicate(completion, ctx)
        assert result.startswith("\n")
        assert "authorizer" in result

    def test_preserves_leading_newline_no_false_strip(self):
        """Leading empty line should not be stripped when content is not a duplicate."""
        ctx = _make_context(prefix="class Foo:\n    def bar(self):", suffix="\n")
        completion = "\n        return 42"
        result = self.provider._deduplicate(completion, ctx)
        assert result == "\n        return 42"

    def test_strips_leading_empty_plus_dup(self):
        """Leading empty line + duplicate line should both be stripped."""
        ctx = _make_context(
            prefix="import os\ndef hello(",
            suffix=")\n    pass",
        )
        completion = "\nimport os\nname):"
        result = self.provider._deduplicate(completion, ctx)
        assert result == "name):"


# ---------------------------------------------------------------------------
# _ensure_newline_boundary
# ---------------------------------------------------------------------------


class TestEnsureNewlineBoundary:
    def setup_method(self):
        self.provider = InlineCompletionProvider()

    def test_adds_newline_for_indented_block_after_def(self):
        """FIM returns body without leading newline after 'def handler():'."""
        ctx = _make_context(prefix="def handler(event, context):", suffix="\n\n")
        result = self.provider._ensure_newline_boundary("    return {}", ctx)
        assert result == "\n    return {}"

    def test_adds_newline_for_indented_block_after_if(self):
        """Indented body after 'if condition:'."""
        ctx = _make_context(prefix="    if x > 0:", suffix="\n")
        result = self.provider._ensure_newline_boundary("        return x", ctx)
        assert result == "\n        return x"

    def test_no_newline_when_already_present(self):
        """Completion already starts with newline — don't double it."""
        ctx = _make_context(prefix="def handler(event, context):", suffix="\n")
        result = self.provider._ensure_newline_boundary("\n    return {}", ctx)
        assert result == "\n    return {}"

    def test_no_newline_for_inline_continuation(self):
        """Inline continuation like 'nse = ...' should stay on same line."""
        ctx = _make_context(prefix="    respo", suffix="\n")
        result = self.provider._ensure_newline_boundary("nse = requests.get(url)", ctx)
        assert result == "nse = requests.get(url)"

    def test_no_newline_on_empty_prefix_line(self):
        """Cursor on empty line — completion goes on current line."""
        ctx = _make_context(prefix="def foo():\n    ", suffix="\n")
        result = self.provider._ensure_newline_boundary("    return 42", ctx)
        assert result == "    return 42"

    def test_no_newline_for_value_completion(self):
        """Value completion after 'x = ' stays on same line."""
        ctx = _make_context(prefix="x = ", suffix="\n")
        result = self.provider._ensure_newline_boundary("42", ctx)
        assert result == "42"

    def test_adds_newline_for_tab_indent(self):
        """Tab-indented completion gets newline prepended."""
        ctx = _make_context(prefix="def foo():", suffix="\n")
        result = self.provider._ensure_newline_boundary("\treturn 42", ctx)
        assert result == "\n\treturn 42"

    def test_empty_completion(self):
        ctx = _make_context(prefix="def foo():", suffix="\n")
        result = self.provider._ensure_newline_boundary("", ctx)
        assert result == ""

    def test_adds_newline_multiline_completion(self):
        """Multi-line body without leading newline gets one prepended."""
        ctx = _make_context(prefix="def handler(event, context):", suffix="\n")
        completion = "    return {\n        'statusCode': 200\n    }"
        result = self.provider._ensure_newline_boundary(completion, ctx)
        assert result.startswith("\n    return {")


# ---------------------------------------------------------------------------
# _is_prose_response
# ---------------------------------------------------------------------------


class TestIsProseResponse:
    def setup_method(self):
        self.provider = InlineCompletionProvider()

    def test_detects_code_review(self):
        text = "The code is well-structured and no changes are necessary."
        assert self.provider._is_prose_response(text) is True

    def test_accepts_code(self):
        text = "name, age):\n    self.name = name"
        assert self.provider._is_prose_response(text) is False

    def test_short_text_not_prose(self):
        text = "x = 1"
        assert self.provider._is_prose_response(text) is False


# ---------------------------------------------------------------------------
# _dedupe_suggestions
# ---------------------------------------------------------------------------


class TestDedupeSuggestions:
    def test_removes_exact_duplicates(self):
        result = _dedupe_suggestions(["return True", "return True", "return False"])
        assert result == ["return True", "return False"]

    def test_removes_whitespace_duplicates(self):
        result = _dedupe_suggestions(["return True", "return True  ", "return False"])
        assert result == ["return True", "return False"]

    def test_preserves_order(self):
        result = _dedupe_suggestions(["aaa", "bbb", "ccc"])
        assert result == ["aaa", "bbb", "ccc"]

    def test_empty_list(self):
        assert _dedupe_suggestions([]) == []

    def test_filters_empty_strings(self):
        result = _dedupe_suggestions(["return True", "", "   ", "return False"])
        assert result == ["return True", "return False"]
