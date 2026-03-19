"""
Terraform/HCL completion provider for Zen IDE autocomplete.

Provides Terraform-specific completions: keywords, built-in functions,
meta-arguments, and symbols extracted from the current buffer (locals,
variables, data sources, resources, outputs, modules).
"""

import os
import re

from editor.autocomplete import CompletionItem, CompletionKind

# Top-level block keywords
TF_KEYWORDS = [
    "resource",
    "data",
    "variable",
    "output",
    "locals",
    "module",
    "provider",
    "terraform",
    "moved",
    "import",
    "check",
]

# Block-level / meta-argument keywords
TF_META_ARGS = [
    "for_each",
    "count",
    "depends_on",
    "lifecycle",
    "provisioner",
    "connection",
    "triggers",
    "dynamic",
    "content",
    "source",
    "version",
    "providers",
    "prevent_destroy",
    "create_before_destroy",
    "ignore_changes",
    "replace_triggered_by",
    "precondition",
    "postcondition",
]

# Expression keywords
TF_EXPR_KEYWORDS = [
    "true",
    "false",
    "null",
    "each",
    "self",
    "path",
    "terraform",
]

# Variable block arguments
TF_VAR_ARGS = [
    "default",
    "type",
    "description",
    "validation",
    "sensitive",
    "nullable",
]

# Output block arguments
TF_OUTPUT_ARGS = [
    "value",
    "description",
    "sensitive",
]

# Common type constructors
TF_TYPES = [
    "string",
    "number",
    "bool",
    "list",
    "map",
    "set",
    "object",
    "tuple",
    "any",
    "optional",
]

# Built-in functions
TF_FUNCTIONS = [
    "abs",
    "abspath",
    "alltrue",
    "anytrue",
    "base64decode",
    "base64encode",
    "base64gzip",
    "base64sha256",
    "base64sha512",
    "basename",
    "bcrypt",
    "can",
    "ceil",
    "chomp",
    "cidrhost",
    "cidrnetmask",
    "cidrsubnet",
    "cidrsubnets",
    "coalesce",
    "coalescelist",
    "compact",
    "concat",
    "contains",
    "csvdecode",
    "dirname",
    "distinct",
    "element",
    "endswith",
    "file",
    "filebase64",
    "filebase64sha256",
    "filebase64sha512",
    "fileexists",
    "filemd5",
    "fileset",
    "filesha1",
    "filesha256",
    "filesha512",
    "flatten",
    "floor",
    "format",
    "formatdate",
    "formatlist",
    "indent",
    "index",
    "join",
    "jsondecode",
    "jsonencode",
    "keys",
    "length",
    "log",
    "lookup",
    "lower",
    "matchkeys",
    "max",
    "md5",
    "merge",
    "min",
    "nonsensitive",
    "one",
    "parseint",
    "pathexpand",
    "plantimestamp",
    "pow",
    "range",
    "regex",
    "regexall",
    "replace",
    "reverse",
    "rsadecrypt",
    "sensitive",
    "setintersection",
    "setproduct",
    "setsubtract",
    "setunion",
    "sha1",
    "sha256",
    "sha512",
    "signum",
    "slice",
    "sort",
    "split",
    "startswith",
    "strcontains",
    "strrev",
    "substr",
    "sum",
    "templatefile",
    "textdecodebase64",
    "textencodebase64",
    "timeadd",
    "timecmp",
    "timestamp",
    "title",
    "tobool",
    "tolist",
    "tomap",
    "tonumber",
    "toset",
    "tostring",
    "transpose",
    "trim",
    "trimprefix",
    "trimspace",
    "trimsuffix",
    "try",
    "type",
    "upper",
    "urlencode",
    "uuid",
    "uuidv5",
    "values",
    "yamldecode",
    "yamlencode",
    "zipmap",
]


class TerraformCompletionProvider:
    """Terraform/HCL-specific completion provider."""

    def get_completions(self, buffer_text, file_path=None):
        """Get Terraform keyword, function, and symbol completions.

        Scans all .tf files in the same directory (Terraform module) for symbols.
        """
        completions = []

        # Keywords
        all_keywords = TF_KEYWORDS + TF_META_ARGS + TF_EXPR_KEYWORDS + TF_VAR_ARGS + TF_OUTPUT_ARGS + TF_TYPES
        completions.extend(CompletionItem(kw, CompletionKind.KEYWORD) for kw in all_keywords)

        # Built-in functions
        completions.extend(CompletionItem(fn, CompletionKind.FUNCTION, f"{fn}()") for fn in TF_FUNCTIONS)

        # Collect all .tf file contents in the same directory (Terraform module)
        module_text = self._get_module_text(buffer_text, file_path)

        # Buffer-extracted symbols from entire module
        completions.extend(self._get_locals(module_text))
        completions.extend(self._get_variables(module_text))
        completions.extend(self._get_resources(module_text))
        completions.extend(self._get_data_sources(module_text))
        completions.extend(self._get_outputs(module_text))
        completions.extend(self._get_modules(module_text))

        return completions

    def _get_module_text(self, buffer_text, file_path):
        """Read all .tf files in the same directory to form the full module text."""
        if not file_path:
            return buffer_text
        directory = os.path.dirname(file_path)
        if not directory or not os.path.isdir(directory):
            return buffer_text
        parts = [buffer_text]
        try:
            for name in os.listdir(directory):
                if not name.endswith(".tf"):
                    continue
                full = os.path.join(directory, name)
                if full == file_path:
                    continue
                with open(full, encoding="utf-8", errors="replace") as f:
                    parts.append(f.read())
        except OSError:
            pass
        return "\n".join(parts)

    def _get_locals(self, text):
        """Extract local value names from locals {} blocks and offer local.X completions."""
        items = []
        for body in self._extract_block_bodies("locals", text):
            for m in re.finditer(r"^\s*(\w+)\s*=", body, re.MULTILINE):
                name = m.group(1)
                items.append(CompletionItem(f"local.{name}", CompletionKind.PROPERTY, "local value"))
        return items

    @staticmethod
    def _extract_block_bodies(keyword, text):
        """Extract block bodies using brace-counting to handle nested braces."""
        bodies = []
        for m in re.finditer(rf"{keyword}\s*\{{", text):
            start = m.end()
            depth = 1
            i = start
            while i < len(text) and depth > 0:
                ch = text[i]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                i += 1
            if depth == 0:
                bodies.append(text[start : i - 1])
        return bodies

    def _get_variables(self, text):
        """Extract variable names and offer var.X completions."""
        items = []
        for m in re.finditer(r'variable\s+"(\w+)"', text):
            name = m.group(1)
            items.append(CompletionItem(f"var.{name}", CompletionKind.PROPERTY, "input variable"))
        return items

    def _get_resources(self, text):
        """Extract resource type.name pairs for reference completions."""
        items = []
        for m in re.finditer(r'resource\s+"(\w+)"\s+"(\w+)"', text):
            rtype, rname = m.group(1), m.group(2)
            items.append(CompletionItem(f"{rtype}.{rname}", CompletionKind.PROPERTY, "resource"))
        return items

    def _get_data_sources(self, text):
        """Extract data source references for data.type.name completions."""
        items = []
        for m in re.finditer(r'data\s+"(\w+)"\s+"(\w+)"', text):
            dtype, dname = m.group(1), m.group(2)
            items.append(CompletionItem(f"data.{dtype}.{dname}", CompletionKind.PROPERTY, "data source"))
        return items

    def _get_outputs(self, text):
        """Extract output names."""
        items = []
        for m in re.finditer(r'output\s+"(\w+)"', text):
            items.append(CompletionItem(m.group(1), CompletionKind.VARIABLE, "output"))
        return items

    def _get_modules(self, text):
        """Extract module names for module.X completions."""
        items = []
        for m in re.finditer(r'module\s+"(\w+)"', text):
            name = m.group(1)
            items.append(CompletionItem(f"module.{name}", CompletionKind.PROPERTY, "module"))
        return items
