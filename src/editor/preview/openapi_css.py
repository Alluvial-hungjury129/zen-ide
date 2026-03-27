"""
OpenAPI preview CSS and HTML template.

Contains the CSS builder and the HTML page template used by the WebKit-based
rendering backends.  Split from openapi_preview.py.
"""


def _build_openapi_css(theme) -> str:
    """Build CSS for the OpenAPI preview."""
    from fonts import get_font_settings

    md_settings = get_font_settings("markdown_preview")
    body_font = md_settings["family"]
    font_size = md_settings.get("size", 14)

    editor_settings = get_font_settings("editor")
    code_font = editor_settings["family"]
    mono_stack = f'"{code_font}", monospace'
    body_stack = f'"{body_font}", sans-serif'
    return f"""
    :root {{ color-scheme: dark; }}
    html {{ height: 100%; overflow-y: auto; }}
    body {{
        font-family: {body_stack};
        font-size: {font_size}px;
        line-height: 1.6;
        color: {theme.fg_color};
        background-color: {theme.main_bg};
        padding: 0;
        margin: 0;
        min-height: 100%;
    }}
    ::-webkit-scrollbar {{ width: 20px; background: transparent; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{
        background-color: {theme.fg_color}40;
        border-radius: 0;
        border: 3px solid transparent;
        background-clip: padding-box;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background-color: {theme.fg_color}66;
        border: 3px solid transparent;
        background-clip: padding-box;
    }}
    .api-header {{
        padding: 20px 24px;
        border-bottom: 1px solid {theme.border_color};
    }}
    .api-title {{
        font-size: 1.8em;
        font-weight: 700;
        margin: 0 0 8px 0;
        color: {theme.fg_color};
    }}
    .api-version {{
        display: inline-block;
        background: {theme.accent_color};
        color: {theme.main_bg};
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: 600;
        margin-left: 8px;
    }}
    .api-description {{
        color: {theme.fg_dim};
        margin-top: 8px;
        font-size: 0.95em;
    }}
    .api-servers {{
        margin-top: 8px;
        font-size: 0.85em;
        color: {theme.fg_dim};
    }}
    .api-servers code {{
        font-family: {mono_stack};
        background: {theme.panel_bg};
        padding: 2px 6px;
        border-radius: 3px;
        color: {theme.accent_color};
    }}
    .tag-group {{
        margin: 28px 0 16px 0;
    }}
    .tag-name {{
        font-size: 1.2em;
        font-weight: 600;
        padding: 12px 24px;
        color: {theme.fg_color};
        border-bottom: 1px solid {theme.border_color};
    }}
    .endpoint {{
        margin: 4px 16px;
        border: 1px solid {theme.border_color};
        border-radius: 6px;
        overflow: hidden;
    }}
    .endpoint-summary {{
        display: flex;
        align-items: center;
        padding: 10px 16px;
        gap: 12px;
        cursor: default;
    }}
    .method-badge {{
        font-family: {mono_stack};
        font-size: 0.75em;
        font-weight: 700;
        text-transform: uppercase;
        padding: 4px 10px;
        border-radius: 4px;
        min-width: 60px;
        text-align: center;
        color: #fff;
    }}
    .endpoint-path {{
        font-family: {mono_stack};
        font-size: 0.9em;
        color: {theme.fg_color};
        font-weight: 600;
    }}
    .endpoint-desc {{
        color: {theme.fg_dim};
        font-size: 0.85em;
        flex: 1;
    }}
    .endpoint-details {{
        padding: 12px 16px;
        border-top: 1px solid {theme.border_color};
        background: {theme.panel_bg};
        display: none;
    }}
    .endpoint.open .endpoint-details {{ display: block; }}
    .detail-section {{
        margin: 16px 0 12px 0;
    }}
    .detail-section h4 {{
        font-size: 0.85em;
        font-weight: 600;
        color: {theme.fg_dim};
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 12px 0 8px 0;
    }}
    .param-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85em;
        table-layout: fixed;
    }}
    .param-table th:nth-child(1), .param-table td:nth-child(1) {{ width: 25%; }}
    .param-table th:nth-child(2), .param-table td:nth-child(2) {{ width: 8%; }}
    .param-table th:nth-child(3), .param-table td:nth-child(3) {{ width: 12%; }}
    .param-table th:nth-child(4), .param-table td:nth-child(4) {{ width: 55%; }}
    .param-table th {{
        text-align: left;
        padding: 4px 8px;
        color: {theme.fg_dim};
        border-bottom: 1px solid {theme.border_color};
        font-weight: 600;
    }}
    .param-table td {{
        padding: 4px 8px;
        border-bottom: 1px solid {theme.border_color}40;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .param-name {{
        font-family: {mono_stack};
        color: {theme.accent_color};
    }}
    .param-required {{
        color: {theme.term_red};
        font-size: 0.8em;
    }}
    .param-type {{
        color: {theme.fg_dim};
        font-family: {mono_stack};
        font-size: 0.9em;
    }}
    .example-section {{
        margin: 6px 0 8px 0;
    }}
    .example-section summary {{
        cursor: pointer;
        font-size: 0.82em;
        font-weight: 600;
        color: {theme.accent_color};
        padding: 4px 0;
        user-select: none;
    }}
    .example-section summary:hover {{
        text-decoration: underline;
    }}
    .example-block {{
        font-family: {mono_stack};
        font-size: 0.8em;
        background: {theme.main_bg};
        padding: 8px 12px;
        border-radius: 4px;
        border: 1px solid {theme.border_color};
        white-space: pre-wrap;
        color: {theme.fg_dim};
        margin: 4px 0 0 0;
    }}
    .response-code {{
        font-family: {mono_stack};
        font-weight: 600;
        padding: 1px 6px;
        border-radius: 3px;
        font-size: 0.85em;
    }}
    .response-2xx {{ color: {theme.term_green}; }}
    .response-3xx {{ color: {theme.warning_color}; }}
    .response-4xx {{ color: {theme.term_red}; }}
    .response-5xx {{ color: {theme.term_red}; }}
    .schema-block {{
        font-family: {mono_stack};
        font-size: 0.8em;
        background: {theme.main_bg};
        padding: 8px 12px;
        border-radius: 4px;
        border: 1px solid {theme.border_color};
        white-space: pre-wrap;
        color: {theme.fg_dim};
    }}
    .schema-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85em;
        margin: 4px 0 8px 0;
        table-layout: fixed;
    }}
    .schema-table th:nth-child(1), .schema-table td:nth-child(1) {{ width: 25%; }}
    .schema-table th:nth-child(2), .schema-table td:nth-child(2) {{ width: 12%; }}
    .schema-table th:nth-child(3), .schema-table td:nth-child(3) {{ width: 8%; }}
    .schema-table th:nth-child(4), .schema-table td:nth-child(4) {{ width: 55%; }}
    .schema-table th {{
        text-align: left;
        padding: 4px 8px;
        color: {theme.fg_dim};
        border-bottom: 1px solid {theme.border_color};
        font-weight: 600;
    }}
    .schema-table td {{
        padding: 4px 8px;
        border-bottom: 1px solid {theme.border_color}40;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .schema-table td:first-child {{
        white-space: nowrap;
    }}
    .schema-table tr.nested td {{
        color: {theme.fg_dim};
    }}
    .schema-toggle {{
        cursor: pointer;
        user-select: none;
        font-weight: 600;
        color: {theme.accent_color};
        white-space: nowrap;
    }}
    .schema-toggle:hover {{ text-decoration: underline; }}
    .schema-toggle::before {{
        display: inline-block;
        margin-right: 4px;
    }}
    tr.collapsed .schema-toggle::before {{ content: "▶"; }}
    tr:not(.collapsed) .schema-toggle::before {{ content: "▼"; }}
    .empty-state {{
        text-align: center;
        padding: 60px 24px;
        color: {theme.fg_dim};
    }}
    .empty-state .icon {{ font-size: 3em; margin-bottom: 16px; }}
    .empty-state .title {{ font-size: 1.2em; font-weight: 600; margin-bottom: 8px; color: {theme.fg_color}; }}
    .deprecated {{ text-decoration: line-through; opacity: 0.6; }}
    """


_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{css}</style>
<script>
function toggleEndpoint(el) {{
    el.closest('.endpoint').classList.toggle('open');
}}
function toggleSchema(el) {{
    var row = el.closest('tr');
    var name = row.dataset.name;
    var table = row.closest('table');
    var rows = table.querySelectorAll('tr[data-name]');
    var isCollapsed = row.classList.toggle('collapsed');
    var depth = (name.match(/\\./g) || []).length;
    for (var i = 0; i < rows.length; i++) {{
        var r = rows[i];
        if (!r.dataset.name || !r.dataset.name.startsWith(name + '.')) continue;
        var childDepth = (r.dataset.name.match(/\\./g) || []).length;
        if (isCollapsed) {{
            r.style.display = 'none';
            r.classList.add('collapsed');
        }} else {{
            if (childDepth === depth + 1) {{
                r.style.display = '';
            }}
        }}
    }}
}}
</script>
</head>
<body>{body}</body>
</html>"""
