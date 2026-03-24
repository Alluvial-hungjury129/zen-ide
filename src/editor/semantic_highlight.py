"""
Semantic-like syntax highlighting for GtkSourceView.

GtkSourceView's regex-based lexer only highlights class/function names at
definition sites (e.g. `class Foo:`, `def bar(`). This module adds
call-site highlighting via text tags applied on top of GtkSourceView's
syntax highlighting:

- PascalCase identifiers → class color (e.g. `ServicingProcessor()`)
- function/method calls → function color (e.g. `.process()`, `len()`)

Uses tree-sitter AST for token extraction (see tree_sitter_semantic.py).
Supported languages: Python, JavaScript, TypeScript, JSX, TSX.
"""

from gi.repository import Gdk, GLib

# Languages that support semantic highlighting
_PYTHON_LANGS = frozenset({"python3", "python"})
_JS_TS_LANGS = frozenset({"javascript", "typescript", "jsx", "typescript-jsx", "js"})

TAG_CLASS_USAGE = "zen-class-usage"
TAG_FUNC_CALL = "zen-func-call"
TAG_PARAM = "zen-param"
TAG_SELF = "zen-self"
TAG_PROPERTY = "zen-property"

_SEM_TAGS = (TAG_CLASS_USAGE, TAG_FUNC_CALL, TAG_PARAM, TAG_SELF, TAG_PROPERTY)


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

    # Debounced re-highlight on text changes and scroll.
    state = {"pending_id": 0}

    def _schedule_highlight(*_args):
        if state["pending_id"]:
            GLib.source_remove(state["pending_id"])
        state["pending_id"] = GLib.timeout_add(150, _enqueue_highlight)

    def _schedule_scroll_highlight(*_args):
        if state["pending_id"]:
            GLib.source_remove(state["pending_id"])
        state["pending_id"] = GLib.timeout_add(100, _enqueue_highlight)

    def _enqueue_highlight():
        state["pending_id"] = 0
        GLib.idle_add(_do_highlight, priority=GLib.PRIORITY_LOW)
        return GLib.SOURCE_REMOVE

    def _do_highlight():
        _apply_semantic_tags(buf, tab)
        return GLib.SOURCE_REMOVE

    if not getattr(tab, "_semantic_handler_id", None):
        hid = buf.connect("changed", _schedule_highlight)
        tab._semantic_handler_id = hid

        # Re-apply semantic tags after GtkSourceView finishes highlighting.
        buf.connect("highlight-updated", _schedule_highlight)

        view = tab.view
        vadj = view.get_vadjustment()
        if vadj:
            vadj.connect("value-changed", _schedule_scroll_highlight)


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


def _apply_semantic_tags(buf, tab=None):
    """Apply semantic highlighting tags to the visible range via tree-sitter."""
    lang = buf.get_language()
    if not lang:
        return

    lang_id = lang.get_id()
    if lang_id not in _PYTHON_LANGS and lang_id not in _JS_TS_LANGS:
        return

    cache = getattr(tab, "_ts_cache", None) if tab else None
    if cache is None:
        return

    try:
        from .tree_sitter_buffer import ts_lang_for_buffer
        from .tree_sitter_semantic import extract_semantic_tokens
    except Exception:
        return

    ts_lang = ts_lang_for_buffer(buf)
    if not ts_lang:
        return

    start = buf.get_start_iter()
    end = buf.get_end_iter()
    text = buf.get_text(start, end, True)

    # Determine visible line range.
    view = getattr(tab, "view", None)
    if view and view.get_mapped():
        visible_rect = view.get_visible_rect()
        top_iter = view.get_iter_at_location(visible_rect.x, visible_rect.y)
        bot_iter = view.get_iter_at_location(visible_rect.x, visible_rect.y + visible_rect.height)
        top_line = (top_iter[1] if isinstance(top_iter, tuple) else top_iter).get_line()
        bot_line = (bot_iter[1] if isinstance(bot_iter, tuple) else bot_iter).get_line()
        margin = max((bot_line - top_line), 40)
        vis_start_line = max(0, top_line - margin)
        vis_end_line = bot_line + margin
    else:
        vis_start_line = 0
        vis_end_line = 80

    vis_start_iter = buf.get_iter_at_line(vis_start_line)
    vis_end_iter = buf.get_iter_at_line(vis_end_line)
    if isinstance(vis_start_iter, tuple):
        vis_start_iter = vis_start_iter[1]
    if isinstance(vis_end_iter, tuple):
        vis_end_iter = vis_end_iter[1]
    if not vis_end_iter.ends_line():
        vis_end_iter.forward_to_line_end()
    vis_start_char = vis_start_iter.get_offset()
    vis_end_char = vis_end_iter.get_offset()

    # Only remove+reapply tags when the text has actually changed.
    # When called from highlight-updated (same text, engine just
    # re-highlighted), skip removal so we don't invalidate the display
    # cache that our previous emit("changed") set up.
    text_gen = buf.get_char_count()  # cheap proxy for "text changed"
    text_changed = getattr(tab, "_sem_last_gen", -1) != text_gen
    if tab:
        tab._sem_last_gen = text_gen

    buf_start = buf.get_start_iter()
    buf_end = buf.get_end_iter()
    if text_changed:
        for tag_name in _SEM_TAGS:
            buf.remove_tag_by_name(tag_name, buf_start, buf_end)

    tag_table = buf.get_tag_table()
    class_tag = tag_table.lookup(TAG_CLASS_USAGE)
    func_tag = tag_table.lookup(TAG_FUNC_CALL)
    param_tag = tag_table.lookup(TAG_PARAM)
    self_tag = tag_table.lookup(TAG_SELF)
    prop_tag = tag_table.lookup(TAG_PROPERTY)
    if not class_tag or not func_tag:
        return

    tree = cache.get_tree(text, ts_lang)
    if tree is None:
        return

    text_bytes = text.encode("utf-8")
    need_mapping = len(text) != len(text_bytes)
    if need_mapping:
        byte_to_char = _build_byte_to_char_map(text)
        char_to_byte = {v: k for k, v in byte_to_char.items()}
        vis_start_byte = char_to_byte.get(vis_start_char, 0)
        vis_end_byte = char_to_byte.get(vis_end_char, len(text_bytes))
    else:
        byte_to_char = None
        vis_start_byte = vis_start_char
        vis_end_byte = vis_end_char

    tokens = extract_semantic_tokens(
        tree.root_node,
        ts_lang,
        vis_start_byte=vis_start_byte,
        vis_end_byte=vis_end_byte,
    )

    tag_map = {
        "class": class_tag,
        "func_call": func_tag,
        "param": param_tag,
        "self_kw": self_tag,
        "property": prop_tag,
    }

    if need_mapping:
        for start_byte, end_byte, token_type in tokens:
            s = byte_to_char.get(start_byte)
            e = byte_to_char.get(end_byte)
            if s is not None and e is not None:
                tag = tag_map.get(token_type)
                if tag is not None:
                    _apply_tag_at_offsets(buf, tag, s, e)
    else:
        for start_byte, end_byte, token_type in tokens:
            tag = tag_map.get(token_type)
            if tag is not None:
                _apply_tag_at_offsets(buf, tag, start_byte, end_byte)

    # Ensure our tags always win over GtkSourceView's engine tags.
    max_prio = tag_table.get_size() - 1
    for tag in (class_tag, func_tag, param_tag, self_tag, prop_tag):
        if tag:
            tag.set_priority(max_prio)

    # After the very first tag application, defer an emit("changed") to
    # force GtkSourceView to rebuild its display cache with our tags.
    # Must run AFTER the current highlight-updated cycle finishes.
    if tab and not getattr(tab, "_sem_first_paint_done", False):
        tab._sem_first_paint_done = True
        if tokens:
            def _deferred_emit():
                handler_id = getattr(tab, "_semantic_handler_id", None)
                if handler_id:
                    buf.handler_block(handler_id)
                buf.emit("changed")
                if handler_id:
                    buf.handler_unblock(handler_id)
                return GLib.SOURCE_REMOVE
            GLib.idle_add(_deferred_emit, priority=GLib.PRIORITY_HIGH)


def _build_byte_to_char_map(text: str) -> dict:
    """Build a byte-offset → char-offset mapping for UTF-8 text."""
    mapping = {}
    byte_off = 0
    for char_off, ch in enumerate(text):
        mapping[byte_off] = char_off
        byte_off += len(ch.encode("utf-8"))
    mapping[byte_off] = len(text)
    return mapping


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
