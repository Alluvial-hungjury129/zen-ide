"""OpenAPIBlockRenderer — convert parsed OpenAPI spec into ContentBlocks.

Produces swagger-style collapsible ContentBlocks from a parsed OpenAPI/Swagger
spec dict for rendering in MarkdownCanvas.  Each endpoint is a collapsible
card (collapsed by default) with a colored HTTP method badge; expanding it
reveals parameters, request body, responses, and auto-composed examples.
"""

from __future__ import annotations

import json
import re

from editor.preview.content_block import ContentBlock, InlineSpan
from icons import IconsManager

_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _parse_inline_spans(text: str) -> list[InlineSpan]:
    """Split text on backtick-delimited code spans into styled InlineSpans."""
    if not isinstance(text, str):
        text = str(text)
    spans: list[InlineSpan] = []
    last = 0
    for m in _BACKTICK_RE.finditer(text):
        if m.start() > last:
            spans.append(InlineSpan(text[last : m.start()]))
        spans.append(InlineSpan(m.group(1), code=True))
        last = m.end()
    if last < len(text):
        spans.append(InlineSpan(text[last:]))
    return spans or [InlineSpan(text)]


def _response_badge_color(code: str) -> str:
    """Return a badge colour for an HTTP status code."""
    first = str(code)[0] if code else ""
    return {
        "2": "#49aa26",
        "3": "#d4a017",
        "4": "#e04040",
        "5": "#e04040",
    }.get(first, "#888888")


class OpenAPIBlockRenderer:
    """Convert a parsed OpenAPI spec dict into a list of ContentBlocks."""

    def render(self, spec: dict) -> list[ContentBlock]:
        """Render the full OpenAPI spec as content blocks."""
        if not spec or not isinstance(spec, dict):
            return [
                ContentBlock(
                    kind="paragraph",
                    source_line=0,
                    spans=[InlineSpan("Not a valid OpenAPI spec.", italic=True)],
                )
            ]

        # Import helpers already defined in openapi_preview.py
        from editor.preview.openapi_preview import (
            _compose_example,
            _method_colors,
            _resolve_ref,
            _schema_summary,
            _schema_to_rows,
        )

        blocks: list[ContentBlock] = []
        line = 0

        # ── API Info header ──────────────────────────────────────────
        info = spec.get("info", {})
        title = info.get("title", "Untitled API")
        version = info.get("version", "")

        title_spans = [InlineSpan(title)]
        if version:
            prefix = "" if version.lower().startswith("v") else "v"
            title_spans.append(InlineSpan(f"  {prefix}{version}", code=True))
        blocks.append(ContentBlock(kind="heading", source_line=line, level=1, spans=title_spans))
        line += 2

        description = info.get("description", "")
        if description:
            blocks.append(ContentBlock(kind="paragraph", source_line=line, spans=_parse_inline_spans(description)))
            line += 2

        # Servers / base URL
        servers = spec.get("servers", [])
        if servers:
            blocks.append(ContentBlock(kind="paragraph", source_line=line, spans=[InlineSpan("Servers:", bold=True)]))
            line += 1
            for srv in servers[:5]:
                url = srv.get("url", "")
                desc = srv.get("description", "")
                spans = [InlineSpan(f"  {url} ", code=True)]
                if desc:
                    spans.append(InlineSpan(f" — {desc}"))
                blocks.append(ContentBlock(kind="paragraph", source_line=line, spans=spans))
                line += 1
        elif spec.get("host"):
            scheme = (spec.get("schemes") or ["https"])[0]
            base = spec.get("basePath", "")
            url = f"{scheme}://{spec['host']}{base}"
            blocks.append(
                ContentBlock(
                    kind="paragraph",
                    source_line=line,
                    spans=[InlineSpan("Base URL: ", bold=True), InlineSpan(url, code=True)],
                )
            )
            line += 1

        blocks.append(ContentBlock(kind="hr", source_line=line))
        line += 1

        # ── Collect endpoints by tag ─────────────────────────────────
        paths = spec.get("paths", {})
        tagged: dict[str, list] = {}
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            if "$ref" in path_item:
                ref_val = path_item["$ref"]
                if isinstance(ref_val, str) and ref_val.startswith("#"):
                    resolved = _resolve_ref(spec, ref_val)
                    if isinstance(resolved, dict):
                        path_item = resolved
                    else:
                        continue
            for method in ("get", "post", "put", "delete", "patch", "options", "head"):
                if method not in path_item:
                    continue
                op = path_item[method]
                if not isinstance(op, dict):
                    continue
                tags = op.get("tags", [])
                if tags:
                    for tag in tags:
                        tagged.setdefault(tag, []).append((method, path, op, path_item))
                else:
                    tagged.setdefault("", []).append((method, path, op, path_item))

        method_colors = _method_colors()

        # ── Render each tag group ────────────────────────────────────
        for tag_name, endpoints in tagged.items():
            if tag_name:
                blocks.append(ContentBlock(kind="heading", source_line=line, level=2, spans=[InlineSpan(tag_name)]))
            line += 1

            for method, path, op, path_item in endpoints:
                color = method_colors.get(method, "#888888")
                summary = op.get("summary", "")
                deprecated = op.get("deprecated", False)

                # Header spans: path only (summary moves inside)
                header_spans: list[InlineSpan] = [InlineSpan(path, bold=True)]
                if deprecated:
                    header_spans = [InlineSpan(path, bold=True, strikethrough=True)]

                # Build children (details shown when expanded)
                children: list[ContentBlock] = []

                # Summary (inside expandable section)
                if summary:
                    s_span = InlineSpan(summary, italic=True, strikethrough=deprecated)
                    children.append(ContentBlock(kind="paragraph", source_line=line, spans=[s_span]))

                # Description
                desc = op.get("description", "")
                if desc:
                    children.append(ContentBlock(kind="paragraph", source_line=line, spans=_parse_inline_spans(desc)))

                # Parameters
                params = list(path_item.get("parameters", []))
                params.extend(op.get("parameters", []))
                if params:
                    children.append(
                        ContentBlock(kind="heading", source_line=line, level=4, spans=[InlineSpan("Parameters")])
                    )
                    headers = ["Name", "In", "Type", "Req", "Description"]
                    rows = []
                    for p in params:
                        if not isinstance(p, dict):
                            continue
                        if "$ref" in p:
                            p = _resolve_ref(spec, p["$ref"]) or p
                        name = p.get("name", "?")
                        loc = p.get("in", "?")
                        schema = p.get("schema", {})
                        ptype = _schema_summary(schema, spec) or schema.get("type", "any")
                        required = IconsManager.SUCCESS if p.get("required") else ""
                        pdesc = p.get("description", "")
                        rows.append([name, loc, ptype, required, pdesc])
                    if rows:
                        children.append(ContentBlock(kind="table", source_line=line, headers=headers, rows=rows))

                # Request body
                req_body = op.get("requestBody", {})
                if req_body and isinstance(req_body, dict):
                    if "$ref" in req_body:
                        req_body = _resolve_ref(spec, req_body["$ref"]) or req_body
                    children.append(
                        ContentBlock(kind="heading", source_line=line, level=4, spans=[InlineSpan("Request Body")])
                    )
                    body_desc = req_body.get("description", "")
                    if body_desc:
                        children.append(
                            ContentBlock(kind="paragraph", source_line=line, spans=_parse_inline_spans(body_desc))
                        )
                    content = req_body.get("content", {})
                    for media_type, media_obj in content.items():
                        schema = media_obj.get("schema", {})
                        children.extend(
                            self._schema_blocks(
                                schema,
                                spec,
                                media_type,
                                line,
                                _resolve_ref,
                                _schema_to_rows,
                                _schema_summary,
                                _compose_example,
                            )
                        )

                # Responses — each status code is a collapsible sub-block
                responses = op.get("responses", {})
                if responses:
                    children.append(ContentBlock(kind="heading", source_line=line, level=4, spans=[InlineSpan("Responses")]))
                    for code, resp in sorted(responses.items()):
                        if not isinstance(resp, dict):
                            continue
                        if "$ref" in resp:
                            resp = _resolve_ref(spec, resp["$ref"]) or resp
                        rdesc = resp.get("description", "")

                        resp_children: list[ContentBlock] = []
                        if rdesc:
                            resp_children.append(
                                ContentBlock(kind="paragraph", source_line=line, spans=_parse_inline_spans(rdesc))
                            )
                        resp_content = resp.get("content", {})
                        for media_type, media_obj in resp_content.items():
                            schema = media_obj.get("schema", {})
                            resp_children.extend(
                                self._schema_blocks(
                                    schema,
                                    spec,
                                    media_type,
                                    line,
                                    _resolve_ref,
                                    _schema_to_rows,
                                    _schema_summary,
                                    _compose_example,
                                )
                            )

                        resp_label = rdesc if rdesc else f"Status {code}"
                        children.append(
                            ContentBlock(
                                kind="paragraph",
                                source_line=line,
                                spans=[InlineSpan(resp_label)],
                                collapsible=True,
                                collapsed=True,
                                badge_text=str(code),
                                badge_color=_response_badge_color(code),
                                children=resp_children,
                            )
                        )

                # Collapsible endpoint card
                blocks.append(
                    ContentBlock(
                        kind="paragraph",
                        source_line=line,
                        spans=header_spans,
                        collapsible=True,
                        collapsed=True,
                        badge_text=method.upper(),
                        badge_color=color,
                        border_color=color,
                        children=children,
                    )
                )
                line += 1

        if not paths:
            blocks.append(
                ContentBlock(
                    kind="paragraph",
                    source_line=line,
                    spans=[InlineSpan("No paths defined.", italic=True)],
                )
            )

        return blocks

    # ── helpers ───────────────────────────────────────────────────────

    def _schema_blocks(
        self,
        schema,
        spec,
        media_type,
        line,
        _resolve_ref,
        _schema_to_rows,
        _schema_summary,
        _compose_example,
    ) -> list[ContentBlock]:
        """Produce table + optional example blocks for a JSON Schema."""
        result: list[ContentBlock] = []

        # Media type label
        result.append(ContentBlock(kind="paragraph", source_line=line, spans=[InlineSpan(media_type, italic=True)]))

        # Schema table — top-level rows only; nested objects become collapsible sub-blocks
        rows = _schema_to_rows(schema, spec)
        if rows:
            # Identify parent names (rows that have nested children)
            names = [r[0] for r in rows]
            parent_set = set()
            for n in names:
                parts = n.split(".")
                for i in range(1, len(parts)):
                    parent_set.add(".".join(parts[:i]))

            headers = ["Name", "Type", "Req", "Description"]
            top_table_rows = []
            # Group nested rows by their top-level parent
            nested_groups: dict[str, list[tuple]] = {}
            for name, type_str, required, desc in rows:
                depth = name.count(".")
                if depth == 0:
                    req_mark = IconsManager.SUCCESS if required else ""
                    top_table_rows.append([name, type_str, req_mark, desc])
                else:
                    top_parent = name.split(".")[0]
                    nested_groups.setdefault(top_parent, []).append((name, type_str, required, desc))

            result.append(ContentBlock(kind="table", source_line=line, headers=headers, rows=top_table_rows))

            # Create a collapsible sub-block for each nested object group
            for parent_name, nested_rows in nested_groups.items():
                child_headers = ["Name", "Type", "Req", "Description"]
                child_table_rows = []
                prefix = f"{parent_name}."
                # Identify parents within the nested group
                nested_names = [r[0] for r in nested_rows]
                nested_parent_set = set()
                for n in nested_names:
                    rel = n[len(prefix) :] if n.startswith(prefix) else n
                    rel_parts = rel.split(".")
                    for i in range(1, len(rel_parts)):
                        nested_parent_set.add(prefix + ".".join(rel_parts[:i]))

                for name, type_str, required, desc in nested_rows:
                    rel_name = name[len(prefix) :] if name.startswith(prefix) else name
                    display_name = rel_name.split(".")[-1]
                    indent_level = rel_name.count(".")
                    indent_pad = "  " * indent_level
                    toggle = "▸ " if name in nested_parent_set else ""
                    req_mark = IconsManager.SUCCESS if required else ""
                    child_table_rows.append([f"{indent_pad}{toggle}{display_name}", type_str, req_mark, desc])

                child_table = ContentBlock(kind="table", source_line=line, headers=child_headers, rows=child_table_rows)
                result.append(
                    ContentBlock(
                        kind="collapsible",
                        source_line=line,
                        collapsible=True,
                        collapsed=True,
                        spans=[InlineSpan(f"  {parent_name}")],
                        badge_text="object",
                        badge_color="#6c757d",
                        children=[child_table],
                    )
                )
        else:
            summary = _schema_summary(schema, spec)
            if summary:
                result.append(ContentBlock(kind="code", source_line=line, language="json", code=summary))

        # Auto-composed example (collapsible)
        example = _compose_example(schema, spec)
        if example is not None:
            try:
                example_json = json.dumps(example, indent=2, ensure_ascii=False)
            except (TypeError, ValueError):
                example_json = str(example)
            result.append(
                ContentBlock(
                    kind="code",
                    source_line=line,
                    language="json",
                    code=example_json,
                    collapsible=True,
                    collapsed=True,
                    spans=[InlineSpan("Example")],
                )
            )

        return result
