"""Tests for editor/autocomplete/terraform_provider.py - Terraform completions."""

from editor.autocomplete.terraform_provider import TerraformCompletionProvider


class TestExtractBlockBodies:
    """Test brace-counting block body extraction."""

    def test_simple_block(self):
        text = 'locals {\n  env = "prod"\n}'
        bodies = TerraformCompletionProvider._extract_block_bodies("locals", text)
        assert len(bodies) == 1
        assert "env" in bodies[0]

    def test_nested_braces(self):
        text = "locals {\n  map = {\n    a = 1\n  }\n}"
        bodies = TerraformCompletionProvider._extract_block_bodies("locals", text)
        assert len(bodies) == 1
        assert "map" in bodies[0]

    def test_multiple_blocks(self):
        text = "locals {\n  a = 1\n}\n\nlocals {\n  b = 2\n}"
        bodies = TerraformCompletionProvider._extract_block_bodies("locals", text)
        assert len(bodies) == 2

    def test_no_match(self):
        text = 'resource "aws_instance" "web" {}'
        bodies = TerraformCompletionProvider._extract_block_bodies("locals", text)
        assert len(bodies) == 0


class TestGetLocals:
    """Test local value extraction."""

    def test_extracts_locals(self):
        p = TerraformCompletionProvider()
        text = 'locals {\n  env = "prod"\n  region = "us-east-1"\n}'
        items = p._get_locals(text)
        names = [i.name for i in items]
        assert "local.env" in names
        assert "local.region" in names


class TestGetVariables:
    """Test variable extraction."""

    def test_extracts_variables(self):
        p = TerraformCompletionProvider()
        text = 'variable "region" {\n  default = "us-east-1"\n}\nvariable "env" {}'
        items = p._get_variables(text)
        names = [i.name for i in items]
        assert "var.region" in names
        assert "var.env" in names


class TestGetResources:
    """Test resource extraction."""

    def test_extracts_resources(self):
        p = TerraformCompletionProvider()
        text = 'resource "aws_instance" "web" {\n  ami = "abc"\n}'
        items = p._get_resources(text)
        names = [i.name for i in items]
        assert "aws_instance.web" in names


class TestGetDataSources:
    """Test data source extraction."""

    def test_extracts_data(self):
        p = TerraformCompletionProvider()
        text = 'data "aws_ami" "latest" {\n  owners = ["self"]\n}'
        items = p._get_data_sources(text)
        names = [i.name for i in items]
        assert "data.aws_ami.latest" in names


class TestGetOutputs:
    """Test output extraction."""

    def test_extracts_outputs(self):
        p = TerraformCompletionProvider()
        text = 'output "ip_address" {\n  value = "1.2.3.4"\n}'
        items = p._get_outputs(text)
        names = [i.name for i in items]
        assert "ip_address" in names


class TestGetModules:
    """Test module extraction."""

    def test_extracts_modules(self):
        p = TerraformCompletionProvider()
        text = 'module "vpc" {\n  source = "./vpc"\n}'
        items = p._get_modules(text)
        names = [i.name for i in items]
        assert "module.vpc" in names


class TestGetCompletions:
    """Test full completions."""

    def test_includes_keywords(self):
        p = TerraformCompletionProvider()
        items = p.get_completions("")
        names = [i.name for i in items]
        assert "resource" in names
        assert "variable" in names

    def test_includes_functions(self):
        p = TerraformCompletionProvider()
        items = p.get_completions("")
        names = [i.name for i in items]
        assert "length" in names
        assert "join" in names

    def test_includes_buffer_symbols(self):
        p = TerraformCompletionProvider()
        text = 'variable "region" {}\nlocals {\n  env = "dev"\n}'
        items = p.get_completions(text)
        names = [i.name for i in items]
        assert "var.region" in names
        assert "local.env" in names
