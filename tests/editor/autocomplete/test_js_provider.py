"""Tests for editor/autocomplete/js_provider.py - JS/TS completions."""

from editor.autocomplete.js_completion_provider import JsCompletionProvider


class TestGetImports:
    """Test import extraction from JS/TS source."""

    def test_named_imports(self):
        p = JsCompletionProvider()
        items = p._get_imports("import { useState, useEffect } from 'react'")
        names = [i.name for i in items]
        assert "useState" in names
        assert "useEffect" in names

    def test_default_import(self):
        p = JsCompletionProvider()
        items = p._get_imports("import React from 'react'")
        names = [i.name for i in items]
        assert "React" in names

    def test_aliased_import(self):
        p = JsCompletionProvider()
        items = p._get_imports("import { Component as Comp } from 'react'")
        names = [i.name for i in items]
        assert "Comp" in names

    def test_namespace_import(self):
        p = JsCompletionProvider()
        items = p._get_imports("import * as utils from './utils'")
        names = [i.name for i in items]
        assert "utils" in names


class TestGetSymbols:
    """Test local symbol extraction from JS/TS."""

    def test_class_declaration(self):
        p = JsCompletionProvider()
        items = p._get_symbols("class MyComponent extends React.Component {}")
        names = [i.name for i in items]
        assert "MyComponent" in names

    def test_function_declaration(self):
        p = JsCompletionProvider()
        items = p._get_symbols("function handleClick(e) {}")
        names = [i.name for i in items]
        assert "handleClick" in names

    def test_const_declaration(self):
        p = JsCompletionProvider()
        items = p._get_symbols("const API_URL = 'http://example.com'")
        names = [i.name for i in items]
        assert "API_URL" in names

    def test_let_declaration(self):
        p = JsCompletionProvider()
        items = p._get_symbols("let counter = 0")
        names = [i.name for i in items]
        assert "counter" in names

    def test_interface(self):
        p = JsCompletionProvider()
        items = p._get_symbols("interface UserProps {\n  name: string;\n}")
        names = [i.name for i in items]
        assert "UserProps" in names

    def test_type_alias(self):
        p = JsCompletionProvider()
        items = p._get_symbols("type ID = string | number")
        names = [i.name for i in items]
        assert "ID" in names


class TestGetCompletions:
    """Test full completions list."""

    def test_includes_keywords(self):
        p = JsCompletionProvider()
        items = p.get_completions("")
        names = [i.name for i in items]
        assert "const" in names
        assert "function" in names
        assert "class" in names

    def test_includes_globals(self):
        p = JsCompletionProvider()
        items = p.get_completions("")
        names = [i.name for i in items]
        assert "console" in names
        assert "Promise" in names
        assert "Array" in names
