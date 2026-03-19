"""
Terraform (HCL) navigation provider.

Provides Cmd+Click navigation for Terraform files (.tf).
Supports navigation to:
- resource definitions (aws_instance.my_name)
- data source definitions (data.aws_secretsmanager_secret.name)
- variable definitions (var.name)
- local value definitions (local.name)
- module definitions (module.name)
- output definitions (output.name)
"""

import os
import re
from typing import Dict, List, Optional, Tuple

from navigation.navigation_provider import NavigationProvider


class TerraformProvider(NavigationProvider):
    """Regex-based navigation provider for Terraform/HCL files."""

    SUPPORTED_EXTENSIONS = {".tf"}

    # Reference prefixes that map to block keywords
    BLOCK_PREFIXES = {"data", "var", "local", "module", "output"}

    def supports_language(self, file_ext: str) -> bool:
        return file_ext.lower() in self.SUPPORTED_EXTENSIONS

    def parse_imports(self, content: str, file_ext: str) -> Dict[str, str]:
        return {}

    def find_symbol_in_content(self, content: str, symbol: str, file_ext: str) -> Optional[int]:
        if file_ext.lower() not in self.SUPPORTED_EXTENSIONS:
            return None
        return self._find_terraform_symbol(content, symbol)

    def _find_terraform_symbol(self, content: str, symbol: str) -> Optional[int]:
        """Find a simple symbol definition in Terraform content."""
        patterns = [
            rf'^resource\s+"[^"]+"\s+"{re.escape(symbol)}"\s*\{{',
            rf'^data\s+"[^"]+"\s+"{re.escape(symbol)}"\s*\{{',
            rf'^variable\s+"{re.escape(symbol)}"\s*\{{',
            rf'^output\s+"{re.escape(symbol)}"\s*\{{',
            rf'^module\s+"{re.escape(symbol)}"\s*\{{',
            rf"^\s+{re.escape(symbol)}\s*=",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                matched_text = match.group()
                symbol_offset = matched_text.find(symbol)
                pos = match.start() + symbol_offset if symbol_offset >= 0 else match.start()
                return content[:pos].count("\n") + 1

        return None

    def resolve_reference(self, chain: str, current_file: str) -> Optional[Tuple[str, int]]:
        """
        Resolve a Terraform reference chain to a (file_path, line_number) tuple.

        Examples:
            data.aws_secretsmanager_secret.kafka_config.id -> data "aws_secretsmanager_secret" "kafka_config"
            var.schema_registry_secrets -> variable "schema_registry_secrets"
            local.msk_enabled -> msk_enabled = ... inside locals {}
            module.my_module.output_name -> module "my_module"
            aws_instance.web.id -> resource "aws_instance" "web"
        """
        parts = chain.split(".")
        if not parts:
            return None

        search_pattern = self._build_search_pattern(parts)
        if not search_pattern:
            return None

        tf_dir = os.path.dirname(current_file)
        tf_files = self._get_tf_files(tf_dir)

        for tf_file in tf_files:
            try:
                with open(tf_file, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, IOError):
                continue

            match = re.search(search_pattern, content, re.MULTILINE)
            if match:
                pos = match.start()
                line = content[:pos].count("\n") + 1
                return (tf_file, line)

        return None

    def _build_search_pattern(self, parts: List[str]) -> Optional[str]:
        """Build a regex pattern to find the Terraform block definition."""
        if not parts:
            return None

        prefix = parts[0]

        if prefix == "data" and len(parts) >= 3:
            resource_type = re.escape(parts[1])
            name = re.escape(parts[2])
            return rf'^data\s+"{resource_type}"\s+"{name}"\s*\{{'

        if prefix == "var" and len(parts) >= 2:
            name = re.escape(parts[1])
            return rf'^variable\s+"{name}"\s*\{{'

        if prefix == "local" and len(parts) >= 2:
            name = re.escape(parts[1])
            return rf"^\s+{name}\s*="

        if prefix == "module" and len(parts) >= 2:
            name = re.escape(parts[1])
            return rf'^module\s+"{name}"\s*\{{'

        if prefix == "output" and len(parts) >= 2:
            name = re.escape(parts[1])
            return rf'^output\s+"{name}"\s*\{{'

        # Resource reference: TYPE.NAME -> resource "TYPE" "NAME" {
        if len(parts) >= 2 and prefix not in self.BLOCK_PREFIXES:
            resource_type = re.escape(parts[0])
            name = re.escape(parts[1])
            return rf'^resource\s+"{resource_type}"\s+"{name}"\s*\{{'

        return None

    def _get_tf_files(self, directory: str) -> List[str]:
        """Get all .tf files in a directory."""
        tf_files = []
        try:
            for entry in os.listdir(directory):
                if entry.endswith(".tf"):
                    tf_files.append(os.path.join(directory, entry))
        except OSError:
            pass
        return sorted(tf_files)
