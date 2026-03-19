"""Tests for editor/openapi_preview.py - OpenAPI content detection and parsing."""

import json

from editor.preview.openapi_preview import _parse_spec, _resolve_ref, _schema_to_rows, is_openapi_content


class TestIsOpenAPIContent:
    """Test OpenAPI/Swagger content detection."""

    def test_yaml_openapi(self):
        assert is_openapi_content("openapi: 3.0.0\ninfo:\n  title: Test") is True

    def test_yaml_swagger(self):
        assert is_openapi_content("swagger: '2.0'\ninfo:\n  title: Test") is True

    def test_json_openapi(self):
        spec = json.dumps({"openapi": "3.0.0", "info": {"title": "Test"}})
        assert is_openapi_content(spec) is True

    def test_json_swagger(self):
        spec = json.dumps({"swagger": "2.0", "info": {"title": "Test"}})
        assert is_openapi_content(spec) is True

    def test_empty_string(self):
        assert is_openapi_content("") is False

    def test_none_like(self):
        assert is_openapi_content("") is False

    def test_plain_yaml(self):
        assert is_openapi_content("name: test\nvalue: 42") is False

    def test_plain_json(self):
        assert is_openapi_content('{"name": "test"}') is False

    def test_yaml_with_comments(self):
        text = "# API spec\n---\nopenapi: 3.0.0\n"
        assert is_openapi_content(text) is True

    def test_yaml_with_document_marker(self):
        text = "---\nopenapi: 3.1.0\n"
        assert is_openapi_content(text) is True


class TestParseSpec:
    """Test OpenAPI spec parsing."""

    def test_parse_yaml(self):
        result = _parse_spec("openapi: 3.0.0\ninfo:\n  title: My API")
        assert result is not None
        assert result["openapi"] == "3.0.0"

    def test_parse_json(self):
        spec = json.dumps({"openapi": "3.0.0", "info": {"title": "My API"}})
        result = _parse_spec(spec)
        assert result is not None
        assert result["openapi"] == "3.0.0"

    def test_parse_empty(self):
        assert _parse_spec("") is None

    def test_parse_none_like(self):
        assert _parse_spec("   ") is None

    def test_parse_invalid_json(self):
        assert _parse_spec("{invalid json}") is None


class TestResolveRef:
    """Test $ref JSON pointer resolution."""

    def test_resolve_simple_ref(self):
        spec = {"components": {"schemas": {"User": {"type": "object", "properties": {"name": {"type": "string"}}}}}}
        result = _resolve_ref(spec, "#/components/schemas/User")
        assert result is not None
        assert result["type"] == "object"

    def test_resolve_nested_ref(self):
        spec = {"components": {"schemas": {"Address": {"type": "object"}}}}
        result = _resolve_ref(spec, "#/components/schemas/Address")
        assert result is not None

    def test_resolve_nonexistent_ref(self):
        spec = {"components": {}}
        result = _resolve_ref(spec, "#/components/schemas/Missing")
        assert result == {}


class TestSchemaToRows:
    """Test _schema_to_rows flattening, especially additionalProperties depth gaps."""

    def test_additional_properties_creates_key_parent_row(self):
        """additionalProperties with nested objects must produce a <key> parent row
        so the toggleSchema JS can expand the tree without depth gaps."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                        },
                    },
                },
            },
        }
        rows = _schema_to_rows(schema, {})
        names = [r[0] for r in rows]
        assert "items" in names
        assert "items.<key>" in names, "missing synthetic <key> parent row"
        assert "items.<key>.value" in names

    def test_no_depth_gaps_in_row_names(self):
        """Every nested row name must have all ancestor rows present."""
        schema = {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    },
                },
            },
        }
        rows = _schema_to_rows(schema, {})
        names = [r[0] for r in rows]
        for name in names:
            parts = name.split(".")
            for i in range(1, len(parts)):
                parent = ".".join(parts[:i])
                assert parent in names, f"depth gap: parent '{parent}' missing for '{name}'"
