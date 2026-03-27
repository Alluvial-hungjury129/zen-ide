"""
OpenAPI HTML rendering functions.

Generates HTML body and plain-text representations of parsed OpenAPI specs.
Split from openapi_preview.py — all rendering helpers live here.
"""

import json

from editor.preview.openapi_css import _HTML_TEMPLATE, _build_openapi_css  # noqa: F401
from themes import get_theme


def _html_escape(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _render_schema_table(schema: dict, spec: dict) -> str:
    """Render a JSON schema as an HTML table with Name, Type, Required, Description columns."""
    from editor.preview.openapi_schema_helpers import (
        _compose_example,
        _schema_summary,
        _schema_to_rows,
    )

    rows = _schema_to_rows(schema, spec)
    if not rows:
        summary = _schema_summary(schema, spec)
        if summary:
            return f'<pre class="schema-block">{_html_escape(summary)}</pre>'
        return ""
    # Determine which rows are parents (have nested children)
    names = [r[0] for r in rows]
    parent_set = set()
    for n in names:
        parts = n.split(".")
        for i in range(1, len(parts)):
            parent_set.add(".".join(parts[:i]))
    html = '<table class="schema-table"><tr><th>Name</th><th>Type</th><th>Req</th><th>Description</th></tr>'
    for name, type_str, required, desc in rows:
        is_nested = "." in name
        is_parent = name in parent_set
        nested_class = " nested" if is_nested else ""
        collapsed_class = " collapsed" if is_parent else ""
        hidden = ' style="display:none"' if is_nested else ""
        display_name = name.split(".")[-1] if is_nested else name
        indent_level = name.count(".")
        indent_pad = "&nbsp;&nbsp;" * indent_level
        req_mark = '<span class="param-required">✓</span>' if required else ""
        html += f'<tr class="{nested_class}{collapsed_class}" data-name="{_html_escape(name)}"{hidden}>'
        if is_parent:
            html += f'<td>{indent_pad}<span class="schema-toggle" onclick="toggleSchema(this)">{_html_escape(display_name)}</span></td>'
        else:
            html += f'<td>{indent_pad}<span class="param-name">{_html_escape(display_name)}</span></td>'
        html += f'<td class="param-type">{_html_escape(type_str)}</td>'
        html += f'<td style="text-align:center">{req_mark}</td>'
        html += f"<td>{_html_escape(desc)}</td></tr>"
    html += "</table>"
    # Auto-compose example as collapsible section
    example = _compose_example(schema, spec)
    if example is not None:
        try:
            example_json = json.dumps(example, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            example_json = str(example)
        html += '<details class="example-section"><summary>Example</summary>'
        html += f'<pre class="example-block">{_html_escape(example_json)}</pre>'
        html += "</details>"
    return html


def _render_parameters(params: list, spec: dict) -> str:
    """Render parameters as an HTML table."""
    from editor.preview.openapi_schema_helpers import _resolve_ref, _schema_summary

    if not params:
        return ""
    html = '<div class="detail-section"><h4>Parameters</h4>'
    html += '<table class="param-table"><tr><th>Name</th><th>In</th><th>Type</th><th>Description</th></tr>'
    for p in params:
        if "$ref" in p:
            p = _resolve_ref(spec, p["$ref"])
        name = _html_escape(p.get("name", ""))
        location = _html_escape(p.get("in", ""))
        required = p.get("required", False)
        schema = p.get("schema", {})
        ptype = _html_escape(_schema_summary(schema, spec) or schema.get("type", ""))
        desc = _html_escape(p.get("description", ""))
        req_badge = ' <span class="param-required">*</span>' if required else ""
        html += f'<tr><td><span class="param-name">{name}</span>{req_badge}</td>'
        html += f'<td>{location}</td><td class="param-type">{ptype}</td>'
        html += f"<td>{desc}</td></tr>"
    html += "</table></div>"
    return html


def _render_request_body(body: dict, spec: dict) -> str:
    """Render request body section."""
    from editor.preview.openapi_schema_helpers import _resolve_ref

    if not body:
        return ""
    if "$ref" in body:
        body = _resolve_ref(spec, body["$ref"])
    content = body.get("content", {})
    html = '<div class="detail-section"><h4>Request Body</h4>'
    desc = body.get("description", "")
    if desc:
        html += f"<p>{_html_escape(desc)}</p>"
    for media_type, media_obj in content.items():
        schema = media_obj.get("schema", {})
        table_html = _render_schema_table(schema, spec)
        if table_html:
            html += f"<div><em>{_html_escape(media_type)}</em></div>"
            html += table_html
    html += "</div>"
    return html


def _render_responses(responses: dict, spec: dict) -> str:
    """Render responses section."""
    from editor.preview.openapi_schema_helpers import _resolve_ref

    if not responses:
        return ""
    html = '<div class="detail-section"><h4>Responses</h4>'
    for code, resp in sorted(responses.items()):
        if "$ref" in resp:
            resp = _resolve_ref(spec, resp["$ref"])
        css_class = f"response-{str(code)[0]}xx" if str(code)[0].isdigit() else ""
        desc = _html_escape(resp.get("description", ""))
        html += (
            f'<div style="margin-bottom:8px"><span class="response-code {css_class}">{_html_escape(str(code))}</span> {desc}'
        )
        content = resp.get("content", {})
        for media_type, media_obj in content.items():
            schema = media_obj.get("schema", {})
            table_html = _render_schema_table(schema, spec)
            if table_html:
                html += f'<div style="margin-top:4px"><em>{_html_escape(media_type)}</em></div>'
                html += table_html
        html += "</div>"
    html += "</div>"
    return html


def _render_spec_html(spec: dict) -> str:
    """Render the full OpenAPI spec as HTML body."""
    from editor.preview.openapi_preview import _method_colors
    from editor.preview.openapi_schema_helpers import _resolve_ref

    if not spec or not isinstance(spec, dict):
        return '<div class="empty-state"><div class="icon">📋</div><div class="title">Not a valid OpenAPI spec</div><div>Edit the file to add a valid OpenAPI or Swagger definition.</div></div>'

    html_parts = []

    # API Info header
    info = spec.get("info", {})
    title = _html_escape(info.get("title", "Untitled API"))
    version = _html_escape(info.get("version", ""))
    description = _html_escape(info.get("description", ""))

    header = f'<div class="api-header"><div class="api-title">{title}'
    if version:
        header += f'<span class="api-version">{version}</span>'
    header += "</div>"
    if description:
        header += f'<div class="api-description">{description}</div>'

    # Servers
    servers = spec.get("servers", [])
    if servers:
        header += '<div class="api-servers">Servers: '
        header += ", ".join(f"<code>{_html_escape(s.get('url', ''))}</code>" for s in servers[:5])
        header += "</div>"
    # Swagger 2.0 host/basePath
    elif spec.get("host"):
        scheme = (spec.get("schemes") or ["https"])[0]
        base = spec.get("basePath", "")
        header += f'<div class="api-servers">Base URL: <code>{_html_escape(scheme)}://{_html_escape(spec["host"])}{_html_escape(base)}</code></div>'

    header += "</div>"
    html_parts.append(header)

    # Collect endpoints grouped by tag
    paths = spec.get("paths", {})
    tagged: dict[str, list] = {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        # Resolve $ref at path-item level (internal or leftover external)
        if "$ref" in path_item:
            ref_val = path_item["$ref"]
            if isinstance(ref_val, str) and ref_val.startswith("#"):
                path_item = _resolve_ref(spec, ref_val)
                if not isinstance(path_item, dict):
                    continue
        for method in ("get", "post", "put", "delete", "patch", "options", "head"):
            if method not in path_item:
                continue
            op = path_item[method]
            if not isinstance(op, dict):
                continue
            tags = op.get("tags", ["default"])
            for tag in tags:
                tagged.setdefault(tag, []).append((method, path, op, path_item))

    # Render each tag group
    for tag_name, endpoints in tagged.items():
        group = f'<div class="tag-group"><div class="tag-name">{_html_escape(tag_name)}</div>'
        for method, path, op, path_item in endpoints:
            color = _method_colors().get(method, get_theme().fg_dim)
            summary = _html_escape(op.get("summary", ""))
            desc = _html_escape(op.get("description", ""))
            deprecated = op.get("deprecated", False)
            dep_class = " deprecated" if deprecated else ""

            group += '<div class="endpoint">'
            group += f'<div class="endpoint-summary{dep_class}" onclick="toggleEndpoint(this)">'
            group += f'<span class="method-badge" style="background:{color}">{method.upper()}</span>'
            group += f'<span class="endpoint-path">{_html_escape(path)}</span>'
            if summary:
                group += f'<span class="endpoint-desc">{summary}</span>'
            group += "</div>"

            # Details section
            group += '<div class="endpoint-details">'
            if desc:
                group += f"<p>{desc}</p>"

            # Parameters (path-level + operation-level)
            params = list(path_item.get("parameters", []))
            params.extend(op.get("parameters", []))
            group += _render_parameters(params, spec)

            # Request body (OpenAPI 3.x)
            if "requestBody" in op:
                group += _render_request_body(op["requestBody"], spec)

            # Responses
            group += _render_responses(op.get("responses", {}), spec)

            group += "</div></div>"  # endpoint-details, endpoint

        group += "</div>"  # tag-group
        html_parts.append(group)

    if not paths:
        html_parts.append(
            '<div class="empty-state"><div class="icon">📭</div>'
            '<div class="title">No paths defined</div>'
            "<div>Add paths to your OpenAPI spec to see them here.</div></div>"
        )

    return "\n".join(html_parts)


def _render_spec_text(spec: dict) -> str:
    """Render a plain-text summary of the spec for the textview fallback."""
    from editor.preview.openapi_schema_helpers import _resolve_ref

    if not spec or not isinstance(spec, dict):
        return "Not a valid OpenAPI spec."

    lines = []
    info = spec.get("info", {})
    version = info.get("version", "?")
    version_str = version if version.startswith("v") else f"v{version}"
    lines.append(f"  {info.get('title', 'Untitled API')}  {version_str}")
    lines.append("=" * 50)
    desc = info.get("description", "")
    if desc:
        lines.append(desc)
        lines.append("")

    paths = spec.get("paths", {})
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        # Resolve $ref at path-item level (internal or leftover external)
        if "$ref" in path_item:
            ref_val = path_item["$ref"]
            if isinstance(ref_val, str) and ref_val.startswith("#"):
                path_item = _resolve_ref(spec, ref_val)
                if not isinstance(path_item, dict):
                    continue
        for method in ("get", "post", "put", "delete", "patch", "options", "head"):
            if method not in path_item:
                continue
            op = path_item[method]
            if not isinstance(op, dict):
                continue
            summary = op.get("summary", "")
            line = f"  {method.upper():8s} {path}"
            if summary:
                line += f"  — {summary}"
            lines.append(line)

            params = op.get("parameters", [])
            for p in params:
                pname = p.get("name", "?")
                ploc = p.get("in", "?")
                lines.append(f"           param: {pname} ({ploc})")

            responses = op.get("responses", {})
            for code in sorted(responses.keys()):
                rdesc = responses[code].get("description", "") if isinstance(responses[code], dict) else ""
                lines.append(f"           {code}: {rdesc}")
            lines.append("")

    if not paths:
        lines.append("  No paths defined.")

    return "\n".join(lines)
