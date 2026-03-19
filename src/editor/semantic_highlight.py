"""
Semantic-like syntax highlighting for GtkSourceView.

GtkSourceView's regex-based lexer only highlights class/function names at
definition sites (e.g. `class Foo:`, `def bar(`). This module adds
call-site highlighting via text tags applied on top of GtkSourceView's
syntax highlighting:

- PascalCase identifiers → class color (e.g. `ServicingProcessor()`)
- function/method calls → function color (e.g. `.process()`, `len()`)

Supported languages: Python, JavaScript, TypeScript, JSX, TSX.
"""

import re

# Skip param-usage highlighting for files larger than this (bytes).
_MAX_PARAM_USAGE_FILE_SIZE = 50_000
# Skip param-usage highlighting for individual function bodies larger than this.
_MAX_PARAM_USAGE_BODY_SIZE = 10_000

from gi.repository import Gdk, GLib

# Patterns for call-site highlighting
# PascalCase: starts with uppercase, has at least one lowercase (avoids ALL_CAPS constants)
_RE_CLASS_USAGE = re.compile(r"\b([A-Z][a-zA-Z0-9]*[a-z][a-zA-Z0-9]*)\b")
# Function/method call: identifier followed by (
_RE_FUNC_CALL = re.compile(r"(?<![A-Z])(?<!\w)([a-z_][a-zA-Z0-9_]*)\s*\(")
# Method call: .identifier(
_RE_METHOD_CALL = re.compile(r"\.([a-z_][a-zA-Z0-9_]*)\s*\(")

# Python keywords that should NOT be colored as function calls
_PYTHON_KEYWORDS = frozenset(
    {
        "if",
        "elif",
        "else",
        "for",
        "while",
        "with",
        "try",
        "except",
        "finally",
        "return",
        "yield",
        "raise",
        "pass",
        "break",
        "continue",
        "and",
        "or",
        "not",
        "in",
        "is",
        "lambda",
        "assert",
        "global",
        "nonlocal",
        "del",
        "async",
        "await",
        "class",
        "def",
        "import",
        "from",
        "as",
    }
)

# JS/TS keywords that should NOT be colored as function calls
_JS_KEYWORDS = frozenset(
    {
        "if",
        "else",
        "for",
        "while",
        "do",
        "switch",
        "case",
        "default",
        "break",
        "continue",
        "return",
        "throw",
        "try",
        "catch",
        "finally",
        "new",
        "delete",
        "typeof",
        "instanceof",
        "void",
        "in",
        "of",
        "with",
        "debugger",
        "class",
        "extends",
        "function",
        "var",
        "let",
        "const",
        "import",
        "export",
        "from",
        "as",
        "async",
        "await",
        "yield",
        "this",
        "super",
        "type",
        "interface",
        "enum",
        "implements",
        "namespace",
        "module",
        "declare",
        "abstract",
        "readonly",
        "keyof",
        "infer",
        "satisfies",
    }
)

# Languages that support semantic highlighting
_PYTHON_LANGS = frozenset({"python3", "python"})
_JS_TS_LANGS = frozenset({"javascript", "typescript", "jsx", "typescript-jsx", "js"})

TAG_CLASS_USAGE = "zen-class-usage"
TAG_FUNC_CALL = "zen-func-call"
TAG_PARAM = "zen-param"
TAG_SELF = "zen-self"
TAG_PROPERTY = "zen-property"

# self/cls keyword (Python)
_RE_SELF = re.compile(r"\b(self|cls)\b")
# this keyword (JS/TS)
_RE_THIS = re.compile(r"\b(this)\b")
# Property/attribute access: .identifier NOT followed by ( (excludes method calls)
_RE_PROPERTY_ACCESS = re.compile(r"\.([a-z_][a-zA-Z0-9_]*)\b(?!\s*\()")

# Pattern for function parameters: captures parameter names from def lines
# Matches: def func(param1, param2, param3=default, *args, **kwargs, param: type)
# DOTALL allows matching multi-line function signatures
_RE_DEF_LINE = re.compile(r"^\s*(?:async\s+)?def\s+\w+\s*\(([^)]*)\)", re.MULTILINE | re.DOTALL)
_RE_PARAM_NAME = re.compile(r"(?:^|,)\s*\*{0,2}([a-zA-Z_]\w*)")

# JS/TS function parameter patterns
# function foo(a, b, c) / function foo(a: string, b = 1)
_RE_JS_FUNC_DEF = re.compile(
    r"(?:function\s+\w+|(?:async\s+)?(?:\w+\s*)?=>|(?:async\s+)?function)\s*\(([^)]*)\)",
    re.MULTILINE | re.DOTALL,
)
# Arrow function params: (a, b) => or (a: Type) =>
_RE_ARROW_PARAMS = re.compile(
    r"\(([^)]*)\)\s*(?::\s*[^=>{]*?)?\s*=>",
    re.MULTILINE | re.DOTALL,
)
# Destructured params: { a, b }: Type or { a, b } =
_RE_JS_PARAM_NAME = re.compile(r"(?:^|,)\s*(?:\.{3})?([a-zA-Z_]\w*)\s*(?:[?:=,)]|$)")

# JSX component tag names (PascalCase): <Component or <Ns.Component
_RE_JSX_COMPONENT = re.compile(r"</?([A-Z][a-zA-Z0-9]*(?:\.[A-Z][a-zA-Z0-9]*)*)")


def _parse_hex(hex_color):
    """Parse '#RRGGBB' to Gdk.RGBA."""
    rgba = Gdk.RGBA()
    rgba.parse(hex_color)
    return rgba


def setup_semantic_highlight(tab, theme):
    """Set up semantic highlighting on an EditorTab.

    Creates text tags and connects signals for automatic re-highlighting.
    """
    buf = tab.buffer

    # Create or update tags
    tag_table = buf.get_tag_table()

    class_tag = tag_table.lookup(TAG_CLASS_USAGE)
    if class_tag:
        class_tag.set_property("foreground-rgba", _parse_hex(theme.syntax_class))
    else:
        class_tag = buf.create_tag(TAG_CLASS_USAGE, foreground_rgba=_parse_hex(theme.syntax_class))

    func_tag = tag_table.lookup(TAG_FUNC_CALL)
    if func_tag:
        func_tag.set_property("foreground-rgba", _parse_hex(theme.syntax_function))
    else:
        func_tag = buf.create_tag(TAG_FUNC_CALL, foreground_rgba=_parse_hex(theme.syntax_function))

    param_color = _parse_hex(theme.get_syntax_color("syntax_parameter"))
    param_tag = tag_table.lookup(TAG_PARAM)
    if param_tag:
        param_tag.set_property("foreground-rgba", param_color)
        param_tag.set_property("style", 2)  # Pango.Style.ITALIC
    else:
        param_tag = buf.create_tag(TAG_PARAM, foreground_rgba=param_color, style=2)

    self_color = _parse_hex(theme.syntax_keyword)
    self_tag = tag_table.lookup(TAG_SELF)
    if self_tag:
        self_tag.set_property("foreground-rgba", self_color)
        self_tag.set_property("style", 2)  # Pango.Style.ITALIC
    else:
        self_tag = buf.create_tag(TAG_SELF, foreground_rgba=self_color, style=2)

    prop_color = _parse_hex(theme.get_syntax_color("syntax_variable"))
    prop_tag = tag_table.lookup(TAG_PROPERTY)
    if prop_tag:
        prop_tag.set_property("foreground-rgba", prop_color)
    else:
        prop_tag = buf.create_tag(TAG_PROPERTY, foreground_rgba=prop_color)

    # Ensure semantic tags have higher priority than GtkSourceView's syntax
    # tags so that e.g. a parameter named `type` gets the parameter color
    # instead of the built-in highlight color.
    max_prio = tag_table.get_size() - 1
    for tag in (param_tag, self_tag, class_tag, func_tag, prop_tag):
        if tag:
            tag.set_priority(max_prio)

    # Debounced re-highlight on text changes.
    # Uses timeout_add (150ms) instead of idle_add to avoid blocking the
    # main loop during rapid typing/scrolling — gives GTK time to
    # process rendering frames between edits.
    state = {"pending_id": 0, "idle_id": 0}

    def _schedule_highlight(*_args):
        # Cancel any pending idle or timeout to avoid redundant runs
        if state["idle_id"]:
            GLib.source_remove(state["idle_id"])
            state["idle_id"] = 0
        if state["pending_id"]:
            GLib.source_remove(state["pending_id"])
        state["pending_id"] = GLib.timeout_add(150, _do_highlight)

    def _do_highlight():
        state["pending_id"] = 0
        state["idle_id"] = 0
        _apply_semantic_tags(buf)
        return GLib.SOURCE_REMOVE

    # Store handler id so we can avoid duplicate connections
    if not getattr(tab, "_semantic_handler_id", None):
        hid = buf.connect("changed", _schedule_highlight)
        tab._semantic_handler_id = hid

    # Initial highlight
    state["idle_id"] = GLib.idle_add(_do_highlight)


def update_semantic_colors(tab, theme):
    """Update semantic tag colors when theme changes."""
    buf = tab.buffer
    tag_table = buf.get_tag_table()

    class_tag = tag_table.lookup(TAG_CLASS_USAGE)
    if class_tag:
        class_tag.set_property("foreground-rgba", _parse_hex(theme.syntax_class))

    func_tag = tag_table.lookup(TAG_FUNC_CALL)
    if func_tag:
        func_tag.set_property("foreground-rgba", _parse_hex(theme.syntax_function))

    param_tag = tag_table.lookup(TAG_PARAM)
    if param_tag:
        param_tag.set_property("foreground-rgba", _parse_hex(theme.get_syntax_color("syntax_parameter")))

    self_tag = tag_table.lookup(TAG_SELF)
    if self_tag:
        self_tag.set_property("foreground-rgba", _parse_hex(theme.syntax_keyword))

    prop_tag = tag_table.lookup(TAG_PROPERTY)
    if prop_tag:
        prop_tag.set_property("foreground-rgba", _parse_hex(theme.get_syntax_color("syntax_variable")))


def _is_inside_string_or_comment(buf, offset):
    """Check if an offset is inside a string or comment context.

    Uses GtkSourceView's context classes to avoid coloring tokens inside
    strings/comments.  Only uses ``iter_has_context_class`` (not
    ``iter_forward_to_context_class_toggle``) because the toggle API can
    trigger lazy re-highlighting that invalidates the iterator mid-call,
    producing GTK warnings that cannot be avoided from Python.
    """
    it = buf.get_iter_at_offset(offset)
    try:
        it = it[1]
    except (TypeError, IndexError):
        pass

    if hasattr(buf, "iter_has_context_class"):
        if buf.iter_has_context_class(it, "string"):
            return True
        # Rebuild iterator — iter_has_context_class may trigger lazy
        # re-highlighting that changes the buffer stamp.
        it = buf.get_iter_at_offset(offset)
        try:
            it = it[1]
        except (TypeError, IndexError):
            pass
        if buf.iter_has_context_class(it, "comment"):
            return True
    return False


def _apply_semantic_tags(buf):
    """Apply semantic highlighting tags to the entire buffer."""
    lang = buf.get_language()
    if not lang:
        return

    lang_id = lang.get_id()
    is_python = lang_id in _PYTHON_LANGS
    is_js_ts = lang_id in _JS_TS_LANGS

    if not is_python and not is_js_ts:
        return

    # Force GtkSourceView's syntax highlighting to complete for the entire
    # buffer BEFORE we create any iterators.  Context-class queries
    # (iter_has_context_class) can trigger lazy re-highlighting which
    # changes the buffer's internal stamp and invalidates iterators.
    if hasattr(buf, "ensure_highlight"):
        buf.ensure_highlight(buf.get_start_iter(), buf.get_end_iter())

    keywords = _PYTHON_KEYWORDS if is_python else _JS_KEYWORDS

    start = buf.get_start_iter()
    end = buf.get_end_iter()
    text = buf.get_text(start, end, True)

    # Remove existing semantic tags.
    for tag_name in (TAG_CLASS_USAGE, TAG_FUNC_CALL, TAG_PARAM, TAG_SELF, TAG_PROPERTY):
        buf.remove_tag_by_name(tag_name, buf.get_start_iter(), buf.get_end_iter())

    tag_table = buf.get_tag_table()
    class_tag = tag_table.lookup(TAG_CLASS_USAGE)
    func_tag = tag_table.lookup(TAG_FUNC_CALL)
    param_tag = tag_table.lookup(TAG_PARAM)
    self_tag = tag_table.lookup(TAG_SELF)
    prop_tag = tag_table.lookup(TAG_PROPERTY)
    if not class_tag or not func_tag:
        return

    # Apply parameter tags
    if param_tag:
        if is_python:
            _apply_param_tags(buf, text, param_tag)
        else:
            _apply_js_param_tags(buf, text, param_tag)

    # Apply property/attribute access tags (.attr, not .method())
    if prop_tag:
        for m in _RE_PROPERTY_ACCESS.finditer(text):
            s = m.start(1)
            e = m.end(1)
            if _is_inside_string_or_comment(buf, s):
                continue
            _apply_tag_at_offsets(buf, prop_tag, s, e)

    # Apply class usage tags (PascalCase identifiers)
    for m in _RE_CLASS_USAGE.finditer(text):
        name = m.group(1)
        s = m.start(1)
        e = m.end(1)
        if _is_inside_string_or_comment(buf, s):
            continue
        _apply_tag_at_offsets(buf, class_tag, s, e)

    # Apply function/method call tags
    for m in _RE_METHOD_CALL.finditer(text):
        name = m.group(1)
        if name in keywords:
            continue
        s = m.start(1)
        e = m.end(1)
        if _is_inside_string_or_comment(buf, s):
            continue
        _apply_tag_at_offsets(buf, func_tag, s, e)

    for m in _RE_FUNC_CALL.finditer(text):
        name = m.group(1)
        if name in keywords:
            continue
        s = m.start(1)
        e = m.end(1)
        if _is_inside_string_or_comment(buf, s):
            continue
        _apply_tag_at_offsets(buf, func_tag, s, e)

    # Apply self/cls/this tags
    if self_tag:
        pattern = _RE_SELF if is_python else _RE_THIS
        for m in pattern.finditer(text):
            s = m.start(1)
            e = m.end(1)
            if _is_inside_string_or_comment(buf, s):
                continue
            _apply_tag_at_offsets(buf, self_tag, s, e)


def _apply_param_tags(buf, text, param_tag):
    """Highlight function parameter names in def statements and their usages."""
    scan_usages = len(text) <= _MAX_PARAM_USAGE_FILE_SIZE
    for m in _RE_DEF_LINE.finditer(text):
        params_str = m.group(1)
        params_offset = m.start(1)
        # Collect parameter names and highlight definitions
        param_names = set()
        for pm in _RE_PARAM_NAME.finditer(params_str):
            name = pm.group(1)
            if name in ("self", "cls"):
                continue
            s = params_offset + pm.start(1)
            e = params_offset + pm.end(1)
            _apply_tag_at_offsets(buf, param_tag, s, e)
            param_names.add(name)
        # Highlight parameter usages in the function body
        if scan_usages and param_names:
            body_start, body_end = _find_python_func_body(text, m)
            if body_start < body_end and (body_end - body_start) <= _MAX_PARAM_USAGE_BODY_SIZE:
                _highlight_param_usages(buf, text, param_names, body_start, body_end, param_tag)


def _apply_js_param_tags(buf, text, param_tag):
    """Highlight function parameter names in JS/TS function definitions and their usages."""
    scan_usages = len(text) <= _MAX_PARAM_USAGE_FILE_SIZE
    for pattern in (_RE_JS_FUNC_DEF, _RE_ARROW_PARAMS):
        for m in pattern.finditer(text):
            params_str = m.group(1)
            params_offset = m.start(1)
            if _is_inside_string_or_comment(buf, params_offset):
                continue
            # Collect parameter names and highlight definitions
            param_names = set()
            for pm in _RE_JS_PARAM_NAME.finditer(params_str):
                name = pm.group(1)
                if name in _JS_KEYWORDS:
                    continue
                s = params_offset + pm.start(1)
                e = params_offset + pm.end(1)
                _apply_tag_at_offsets(buf, param_tag, s, e)
                param_names.add(name)
            # Highlight parameter usages in the function body
            if scan_usages and param_names:
                body_start, body_end = _find_js_func_body(text, m.end())
                if body_start < body_end and (body_end - body_start) <= _MAX_PARAM_USAGE_BODY_SIZE:
                    _highlight_param_usages(buf, text, param_names, body_start, body_end, param_tag)


def _apply_tag_at_offsets(buf, tag, start_offset, end_offset):
    """Apply a text tag between two offsets."""
    result_s = buf.get_iter_at_offset(start_offset)
    result_e = buf.get_iter_at_offset(end_offset)
    try:
        si = result_s[1]
    except (TypeError, IndexError):
        si = result_s
    try:
        ei = result_e[1]
    except (TypeError, IndexError):
        ei = result_e
    buf.apply_tag(tag, si, ei)


def _find_python_func_body(text, def_match):
    """Return (body_start, body_end) for a Python function body."""
    line_start = text.rfind("\n", 0, def_match.start()) + 1
    def_line_prefix = text[line_start : def_match.start()]
    def_indent = len(def_line_prefix) - len(def_line_prefix.lstrip())

    nl = text.find("\n", def_match.end())
    if nl == -1:
        return (0, 0)

    pos = nl + 1
    body_start = None
    body_end = len(text)

    while pos < len(text):
        nl = text.find("\n", pos)
        if nl == -1:
            nl = len(text)
        line = text[pos:nl]
        stripped = line.lstrip()
        if stripped and not stripped.startswith("#"):
            indent = len(line) - len(stripped)
            if body_start is None:
                if indent > def_indent:
                    body_start = pos
                else:
                    return (0, 0)
            elif indent <= def_indent:
                body_end = pos
                break
        pos = nl + 1

    if body_start is None:
        return (0, 0)
    return (body_start, body_end)


def _find_js_func_body(text, search_start):
    """Return (body_start, body_end) for a JS/TS function body using brace counting."""
    brace_pos = text.find("{", search_start)
    if brace_pos == -1:
        return (0, 0)
    body_start = brace_pos + 1
    depth = 1
    i = body_start
    in_string = None
    while i < len(text) and depth > 0:
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif ch in ('"', "'", "`"):
            in_string = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    body_end = i - 1
    return (body_start, body_end)


def _highlight_param_usages(buf, text, param_names, body_start, body_end, param_tag):
    """Highlight all usages of parameter names within the given text range."""
    pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(param_names, key=len, reverse=True)) + r")\b")
    body_text = text[body_start:body_end]
    for m in pattern.finditer(body_text):
        s = body_start + m.start()
        if s > 0 and text[s - 1] == ".":
            continue
        if _is_inside_string_or_comment(buf, s):
            continue
        e = body_start + m.end()
        _apply_tag_at_offsets(buf, param_tag, s, e)
