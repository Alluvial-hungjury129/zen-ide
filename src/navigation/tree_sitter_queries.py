"""
Tree-sitter query patterns for code navigation.

Defines S-expression queries for finding symbol definitions and imports
across supported languages. Queries use capture groups:
  @name  — the identifier name of the definition
  @node  — the full definition node (for line number extraction)
"""

# ---------------------------------------------------------------------------
# Python queries
# ---------------------------------------------------------------------------

PY_DEFINITIONS = """
(function_definition
  name: (identifier) @name) @node

(class_definition
  name: (identifier) @name) @node

(assignment
  left: (identifier) @name) @node

(assignment
  left: (pattern_list
    (identifier) @name)) @node
"""

PY_IMPORTS = """
(import_statement
  name: (dotted_name) @module) @node

(import_statement
  name: (aliased_import
    name: (dotted_name) @module
    alias: (identifier) @alias)) @node

(import_from_statement
  module_name: (dotted_name) @module
  name: (dotted_name) @name) @node

(import_from_statement
  module_name: (dotted_name) @module
  name: (aliased_import
    name: (dotted_name) @name
    alias: (identifier) @alias)) @node

(import_from_statement
  module_name: (relative_import) @module
  name: (dotted_name) @name) @node

(import_from_statement
  module_name: (relative_import) @module
  name: (aliased_import
    name: (dotted_name) @name
    alias: (identifier) @alias)) @node
"""

# ---------------------------------------------------------------------------
# TypeScript / JavaScript queries
# ---------------------------------------------------------------------------

TS_DEFINITIONS = """
(function_declaration
  name: (identifier) @name) @node

(class_declaration
  name: (type_identifier) @name) @node

(interface_declaration
  name: (type_identifier) @name) @node

(type_alias_declaration
  name: (type_identifier) @name) @node

(enum_declaration
  name: (identifier) @name) @node

(lexical_declaration
  (variable_declarator
    name: (identifier) @name)) @node

(variable_declaration
  (variable_declarator
    name: (identifier) @name)) @node

(export_statement
  declaration: (function_declaration
    name: (identifier) @name)) @node

(export_statement
  declaration: (class_declaration
    name: (type_identifier) @name)) @node

(export_statement
  declaration: (interface_declaration
    name: (type_identifier) @name)) @node

(export_statement
  declaration: (type_alias_declaration
    name: (type_identifier) @name)) @node

(export_statement
  declaration: (enum_declaration
    name: (identifier) @name)) @node

(export_statement
  declaration: (lexical_declaration
    (variable_declarator
      name: (identifier) @name))) @node
"""

JS_DEFINITIONS = """
(function_declaration
  name: (identifier) @name) @node

(class_declaration
  name: (identifier) @name) @node

(lexical_declaration
  (variable_declarator
    name: (identifier) @name)) @node

(variable_declaration
  (variable_declarator
    name: (identifier) @name)) @node

(export_statement
  declaration: (function_declaration
    name: (identifier) @name)) @node

(export_statement
  declaration: (class_declaration
    name: (identifier) @name)) @node

(export_statement
  declaration: (lexical_declaration
    (variable_declarator
      name: (identifier) @name))) @node
"""

TS_IMPORTS = """
(import_statement
  (import_clause
    (named_imports
      (import_specifier
        name: (identifier) @name))) @clause
  source: (string) @module) @node

(import_statement
  (import_clause
    (identifier) @name) @clause
  source: (string) @module) @node

(import_statement
  (import_clause
    (namespace_import
      (identifier) @name)) @clause
  source: (string) @module) @node
"""
