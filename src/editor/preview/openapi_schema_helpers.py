"""
OpenAPI schema helper functions.

Ref resolution, schema summarisation, allOf merging, schema-to-rows flattening,
example composition, and external $ref resolution.  Split from openapi_preview.py.
"""

import os


def _resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a $ref pointer in the spec."""
    if not ref.startswith("#/"):
        return {}
    parts = ref[2:].split("/")
    current = spec
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return {}
    return current if isinstance(current, dict) else {}


def _schema_summary(schema: dict, spec: dict, depth: int = 0, indent: int = 0) -> str:
    """Generate a brief text summary of a JSON schema."""
    if not schema or depth > 5:
        return ""
    pad = "  " * indent
    inner = "  " * (indent + 1)
    if "$ref" in schema:
        resolved = _resolve_ref(spec, schema["$ref"])
        ref_name = schema["$ref"].split("/")[-1]
        if resolved and depth < 3:
            return f"{ref_name}: {_schema_summary(resolved, spec, depth + 1, indent)}"
        return ref_name
    schema_type = schema.get("type", "")
    if schema_type == "object":
        props = schema.get("properties", {})
        if props:
            fields = []
            for name, prop in list(props.items())[:10]:
                ptype = _schema_summary(prop, spec, depth + 1, indent + 1) or prop.get("type", "any")
                desc = prop.get("description", "")
                desc_str = f"  // {desc}" if desc else ""
                fields.append(f"{inner}{name}: {ptype}{desc_str}")
            result = "{\n" + ",\n".join(fields)
            if len(props) > 10:
                result += f",\n{inner}... ({len(props) - 10} more)"
            return result + f"\n{pad}}}"
        return "object"
    if schema_type == "array":
        items = schema.get("items", {})
        items_summary = _schema_summary(items, spec, depth + 1, indent) or "any"
        return f"[{items_summary}]"
    if "enum" in schema:
        vals = " | ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in schema["enum"][:6])
        return vals
    if schema_type:
        fmt = schema.get("format", "")
        return f"{schema_type}({fmt})" if fmt else schema_type
    # oneOf / anyOf / allOf
    for keyword in ("oneOf", "anyOf", "allOf"):
        if keyword in schema:
            parts = [_schema_summary(s, spec, depth + 1, indent) for s in schema[keyword][:4]]
            joiner = " | " if keyword != "allOf" else " & "
            return joiner.join(p for p in parts if p)
    return ""


def _merge_allof(schemas: list, spec: dict) -> dict:
    """Merge allOf schemas into a single combined schema."""
    merged: dict = {"type": "object", "properties": {}, "required": []}
    for s in schemas:
        if "$ref" in s:
            s = _resolve_ref(spec, s["$ref"]) or s
        if "allOf" in s:
            s = _merge_allof(s["allOf"], spec)
        merged["properties"].update(s.get("properties", {}))
        merged["required"].extend(s.get("required", []))
        if s.get("description") and not merged.get("description"):
            merged["description"] = s["description"]
    return merged


def _schema_to_rows(schema: dict, spec: dict, required_set: set | None = None, prefix: str = "", depth: int = 0) -> list:
    """Flatten a JSON schema into table rows: [(name, type_str, required, description), ...]."""
    if not schema or depth > 5:
        return []
    if "$ref" in schema:
        resolved = _resolve_ref(spec, schema["$ref"])
        if resolved and depth < 4:
            return _schema_to_rows(resolved, spec, resolved.get("required"), prefix, depth + 1)
        return []
    # Handle allOf composition
    if "allOf" in schema:
        merged = _merge_allof(schema["allOf"], spec)
        return _schema_to_rows(merged, spec, required_set, prefix, depth)
    # Handle oneOf/anyOf - show rows from each variant
    for kw in ("oneOf", "anyOf"):
        if kw in schema:
            rows = []
            for s in schema[kw][:4]:
                rows.extend(_schema_to_rows(s, spec, required_set, prefix, depth + 1))
            return rows
    schema_type = schema.get("type", "")
    # Treat schemas with properties as objects even without explicit type
    has_properties = bool(schema.get("properties"))
    if required_set is None:
        required_set = set(schema.get("required", []))
    if schema_type == "object" or has_properties:
        props = schema.get("properties", {})
        req = set(schema.get("required", [])) if schema.get("required") else required_set
        rows = []
        for name, prop in list(props.items())[:20]:
            if "$ref" in prop:
                resolved = _resolve_ref(spec, prop["$ref"])
                if resolved:
                    prop = resolved
            # Handle allOf inside property
            if "allOf" in prop:
                prop = _merge_allof(prop["allOf"], spec)
            full_name = f"{prefix}{name}" if prefix else name
            ptype = prop.get("type", "")
            fmt = prop.get("format", "")
            if "enum" in prop:
                vals = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in prop["enum"][:6])
                type_str = f"enum({vals})"
            elif ptype == "array":
                items = prop.get("items", {})
                if "$ref" in items:
                    ref_resolved = _resolve_ref(spec, items["$ref"])
                    item_type = items["$ref"].split("/")[-1]
                    if ref_resolved:
                        items = ref_resolved
                else:
                    item_type = items.get("type", "any")
                type_str = f"array[{item_type}]"
            elif ptype == "object" or prop.get("properties"):
                type_str = "object"
            else:
                type_str = f"{ptype}({fmt})" if fmt else (ptype or "any")
            # oneOf / anyOf
            for kw in ("oneOf", "anyOf"):
                if kw in prop:
                    parts = []
                    for s in prop[kw][:4]:
                        if "$ref" in s:
                            parts.append(s["$ref"].split("/")[-1])
                        else:
                            parts.append(s.get("type", ""))
                    type_str = " | ".join(p for p in parts if p)
            is_req = name in req
            desc = prop.get("description", "")
            rows.append((full_name, type_str, is_req, desc))
            # Recurse into nested objects (check properties, not just type)
            if prop.get("properties") and depth < 3:
                nested = _schema_to_rows(prop, spec, None, f"{full_name}.", depth + 1)
                rows.extend(nested)
            # Recurse into additionalProperties if it's an object schema
            elif prop.get("additionalProperties") and isinstance(prop["additionalProperties"], dict) and depth < 3:
                add_props = prop["additionalProperties"]
                if "$ref" in add_props:
                    add_props = _resolve_ref(spec, add_props["$ref"]) or add_props
                if add_props.get("properties"):
                    key_name = f"{full_name}.<key>"
                    add_type = add_props.get("type", "object")
                    add_desc = add_props.get("description", "")
                    rows.append((key_name, add_type, False, add_desc))
                    nested = _schema_to_rows(add_props, spec, None, f"{key_name}.", depth + 1)
                    rows.extend(nested)
            # Recurse into array items if they're objects
            if ptype == "array":
                arr_items = prop.get("items", {})
                if "$ref" in arr_items:
                    arr_items = _resolve_ref(spec, arr_items["$ref"]) or arr_items
                if "allOf" in arr_items:
                    arr_items = _merge_allof(arr_items["allOf"], spec)
                if arr_items.get("properties") and depth < 3:
                    nested = _schema_to_rows(arr_items, spec, None, f"{full_name}[].", depth + 1)
                    rows.extend(nested)
        return rows
    if schema_type == "array":
        items = schema.get("items", {})
        if "$ref" in items:
            items = _resolve_ref(spec, items["$ref"]) or items
        if "allOf" in items:
            items = _merge_allof(items["allOf"], spec)
        if items.get("properties"):
            return _schema_to_rows(items, spec, None, prefix, depth + 1)
        return []
    return []


def _compose_example(schema: dict, spec: dict, depth: int = 0) -> object:
    """Auto-compose an example JSON value from a schema."""
    if not schema or depth > 5:
        return None
    if "$ref" in schema:
        resolved = _resolve_ref(spec, schema["$ref"])
        return _compose_example(resolved, spec, depth + 1) if resolved else None
    if "allOf" in schema:
        merged = _merge_allof(schema["allOf"], spec)
        return _compose_example(merged, spec, depth)
    if "example" in schema:
        return schema["example"]
    schema_type = schema.get("type", "")
    has_properties = bool(schema.get("properties"))
    if schema_type == "object" or has_properties:
        obj = {}
        for name, prop in list(schema.get("properties", {}).items())[:20]:
            if "$ref" in prop:
                prop = _resolve_ref(spec, prop["$ref"]) or prop
            if "allOf" in prop:
                prop = _merge_allof(prop["allOf"], spec)
            val = _compose_example(prop, spec, depth + 1)
            if val is not None:
                obj[name] = val
            else:
                # Generate a placeholder based on type
                pt = prop.get("type", "")
                if "enum" in prop:
                    obj[name] = prop["enum"][0] if prop["enum"] else ""
                elif pt == "string":
                    obj[name] = prop.get("format", "string")
                elif pt == "integer":
                    obj[name] = 0
                elif pt == "number":
                    obj[name] = 0.0
                elif pt == "boolean":
                    obj[name] = True
                elif pt == "array":
                    items = prop.get("items", {})
                    if "$ref" in items:
                        items = _resolve_ref(spec, items["$ref"]) or items
                    item_ex = _compose_example(items, spec, depth + 1)
                    obj[name] = [item_ex] if item_ex is not None else []
                elif prop.get("properties"):
                    obj[name] = _compose_example(prop, spec, depth + 1) or {}
        return obj
    if schema_type == "array":
        items = schema.get("items", {})
        if "$ref" in items:
            items = _resolve_ref(spec, items["$ref"]) or items
        item_ex = _compose_example(items, spec, depth + 1)
        return [item_ex] if item_ex is not None else []
    if "enum" in schema:
        return schema["enum"][0] if schema["enum"] else ""
    if schema_type == "string":
        return schema.get("format", "string")
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    if schema_type == "boolean":
        return True
    return None


def _resolve_internal_refs_with_doc(obj, full_doc: dict, seen: set | None = None):
    """Resolve internal #/ $ref pointers against the full source document."""
    if not isinstance(obj, dict):
        return obj
    if seen is None:
        seen = set()
    if "$ref" in obj and isinstance(obj["$ref"], str) and obj["$ref"].startswith("#"):
        ref_key = obj["$ref"]
        if ref_key in seen:
            return obj
        resolved = _resolve_ref(full_doc, ref_key)
        if resolved:
            seen.add(ref_key)
            return _resolve_internal_refs_with_doc(resolved, full_doc, seen)
        return obj
    for key, value in list(obj.items()):
        if isinstance(value, dict):
            obj[key] = _resolve_internal_refs_with_doc(value, full_doc, seen)
        elif isinstance(value, list):
            obj[key] = [
                _resolve_internal_refs_with_doc(item, full_doc, seen) if isinstance(item, dict) else item for item in value
            ]
    return obj


def _resolve_file_ref(ref: str, base_dir: str) -> dict | None:
    """Load and parse an external file $ref, optionally following a JSON pointer."""
    from editor.preview.openapi_preview import _parse_spec

    if "#" in ref:
        file_ref, pointer = ref.split("#", 1)
    else:
        file_ref, pointer = ref, None
    ref_path = os.path.normpath(os.path.join(base_dir, file_ref))
    try:
        with open(ref_path, "r", encoding="utf-8") as f:
            content = f.read()
        full_doc = _parse_spec(content)
        if full_doc and isinstance(full_doc, dict):
            resolved = full_doc
            if pointer:
                resolved = _resolve_ref(full_doc, "#" + pointer)
            # Resolve internal $refs against the full source document
            if pointer and isinstance(resolved, dict):
                resolved = _resolve_internal_refs_with_doc(resolved, full_doc)
            return resolved
    except Exception:
        pass
    return None


def _deep_resolve_refs(obj, base_dir: str, depth: int = 0):
    """Recursively resolve all external $ref references in a parsed spec tree.

    depth tracks file-resolution hops only (not object tree depth) to prevent
    circular-reference loops while still resolving deeply nested specs.
    """
    if not isinstance(obj, dict):
        return obj
    if "$ref" in obj and isinstance(obj["$ref"], str) and not obj["$ref"].startswith("#"):
        if depth > 10:
            return obj
        ref = obj["$ref"]
        file_part = ref.split("#")[0] if "#" in ref else ref
        new_base = os.path.normpath(os.path.join(base_dir, os.path.dirname(file_part)))
        resolved = _resolve_file_ref(ref, base_dir)
        if resolved is not None:
            return _deep_resolve_refs(resolved, new_base, depth + 1)
        return obj
    for key, value in list(obj.items()):
        if isinstance(value, dict):
            obj[key] = _deep_resolve_refs(value, base_dir, depth)
        elif isinstance(value, list):
            obj[key] = [_deep_resolve_refs(item, base_dir, depth) if isinstance(item, dict) else item for item in value]
    return obj


def _resolve_external_refs(spec: dict, base_dir: str | None) -> dict:
    """Resolve all external file $ref references throughout the spec."""
    if not spec or not isinstance(spec, dict) or not base_dir:
        return spec
    return _deep_resolve_refs(spec, base_dir)
