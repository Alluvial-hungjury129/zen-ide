"""Tests for navigation/terraform_provider.py - Terraform HCL navigation."""

import os
import tempfile

from navigation.terraform_provider import TerraformProvider


class TestSupportsLanguage:
    """Test file extension support."""

    def test_supports_tf(self):
        p = TerraformProvider()
        assert p.supports_language(".tf") is True

    def test_case_insensitive(self):
        p = TerraformProvider()
        assert p.supports_language(".TF") is True

    def test_py_not_supported(self):
        p = TerraformProvider()
        assert p.supports_language(".py") is False


class TestParseImports:
    """Terraform doesn't have imports."""

    def test_always_empty(self):
        p = TerraformProvider()
        assert p.parse_imports("resource {}", ".tf") == {}


class TestFindSymbol:
    """Test finding Terraform symbols."""

    def test_find_resource(self):
        p = TerraformProvider()
        content = 'resource "aws_instance" "web" {\n  ami = "abc"\n}'
        assert p.find_symbol_in_content(content, "web", ".tf") == 1

    def test_find_variable(self):
        p = TerraformProvider()
        content = 'variable "region" {\n  default = "us-east-1"\n}'
        assert p.find_symbol_in_content(content, "region", ".tf") == 1

    def test_find_output(self):
        p = TerraformProvider()
        content = 'output "ip_address" {\n  value = aws_instance.web.public_ip\n}'
        assert p.find_symbol_in_content(content, "ip_address", ".tf") == 1

    def test_find_module(self):
        p = TerraformProvider()
        content = 'module "vpc" {\n  source = "./modules/vpc"\n}'
        assert p.find_symbol_in_content(content, "vpc", ".tf") == 1

    def test_find_data(self):
        p = TerraformProvider()
        content = 'data "aws_ami" "latest" {\n  owners = ["self"]\n}'
        assert p.find_symbol_in_content(content, "latest", ".tf") == 1

    def test_find_local_assignment(self):
        p = TerraformProvider()
        content = 'locals {\n  env = "prod"\n}'
        assert p.find_symbol_in_content(content, "env", ".tf") == 2

    def test_symbol_not_found(self):
        p = TerraformProvider()
        assert p.find_symbol_in_content("", "nonexistent", ".tf") is None

    def test_unsupported_ext(self):
        p = TerraformProvider()
        assert p.find_symbol_in_content("", "x", ".py") is None


class TestBuildSearchPattern:
    """Test regex pattern building for Terraform references."""

    def test_data_reference(self):
        p = TerraformProvider()
        pattern = p._build_search_pattern(["data", "aws_ami", "latest"])
        assert pattern is not None
        assert "data" in pattern

    def test_var_reference(self):
        p = TerraformProvider()
        pattern = p._build_search_pattern(["var", "region"])
        assert pattern is not None
        assert "variable" in pattern

    def test_local_reference(self):
        p = TerraformProvider()
        pattern = p._build_search_pattern(["local", "env"])
        assert pattern is not None
        assert "env" in pattern

    def test_module_reference(self):
        p = TerraformProvider()
        pattern = p._build_search_pattern(["module", "vpc"])
        assert pattern is not None
        assert "module" in pattern

    def test_output_reference(self):
        p = TerraformProvider()
        pattern = p._build_search_pattern(["output", "ip"])
        assert pattern is not None
        assert "output" in pattern

    def test_resource_reference(self):
        p = TerraformProvider()
        pattern = p._build_search_pattern(["aws_instance", "web"])
        assert pattern is not None
        assert "resource" in pattern

    def test_empty_parts(self):
        p = TerraformProvider()
        assert p._build_search_pattern([]) is None


class TestResolveReference:
    """Test reference resolution across files."""

    def test_resolve_variable(self):
        p = TerraformProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            tf_file = os.path.join(tmpdir, "main.tf")
            vars_file = os.path.join(tmpdir, "vars.tf")
            with open(tf_file, "w") as f:
                f.write('resource "aws_instance" "web" {}')
            with open(vars_file, "w") as f:
                f.write('variable "region" {\n  default = "us-east-1"\n}')
            result = p.resolve_reference("var.region", tf_file)
            assert result is not None
            assert result[1] == 1  # Line 1

    def test_resolve_not_found(self):
        p = TerraformProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            tf_file = os.path.join(tmpdir, "main.tf")
            with open(tf_file, "w") as f:
                f.write("")
            result = p.resolve_reference("var.nonexistent", tf_file)
            assert result is None


class TestGetTfFiles:
    """Test .tf file discovery."""

    def test_finds_tf_files(self):
        p = TerraformProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["main.tf", "vars.tf", "readme.md"]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write("")
            files = p._get_tf_files(tmpdir)
            assert len(files) == 2
            assert all(f.endswith(".tf") for f in files)

    def test_sorted_output(self):
        p = TerraformProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["z.tf", "a.tf"]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write("")
            files = p._get_tf_files(tmpdir)
            assert files[0].endswith("a.tf")
