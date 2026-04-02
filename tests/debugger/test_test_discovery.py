"""Tests for debugger test discovery."""

from debugger.test_discovery import DiscoveredTest, _discover_with_regex, discover_tests


class TestDiscoveredTestNodeId:
    def test_module_level_function(self):
        item = DiscoveredTest(name="test_foo", line=5)
        assert item.node_id == "test_foo"
        assert item.display_name == "test_foo"

    def test_class_method(self):
        item = DiscoveredTest(name="test_bar", class_name="TestMyClass", line=10)
        assert item.node_id == "TestMyClass::test_bar"
        assert item.display_name == "TestMyClass::test_bar"


class TestRegexDiscovery:
    def test_module_level_functions(self):
        content = """\
import pytest

def test_add():
    assert 1 + 1 == 2

def test_subtract():
    assert 2 - 1 == 1

def helper():
    pass
"""
        tests = _discover_with_regex(content)
        assert len(tests) == 2
        assert tests[0].name == "test_add"
        assert tests[0].class_name == ""
        assert tests[0].line == 3
        assert tests[1].name == "test_subtract"

    def test_class_methods(self):
        content = """\
class TestMath:
    def test_add(self):
        assert 1 + 1 == 2

    def test_subtract(self):
        assert 2 - 1 == 1

    def helper(self):
        pass
"""
        tests = _discover_with_regex(content)
        assert len(tests) == 2
        assert tests[0].name == "test_add"
        assert tests[0].class_name == "TestMath"
        assert tests[1].name == "test_subtract"
        assert tests[1].class_name == "TestMath"

    def test_mixed(self):
        content = """\
def test_standalone():
    pass

class TestGroup:
    def test_inside(self):
        pass
"""
        tests = _discover_with_regex(content)
        assert len(tests) == 2
        assert tests[0].class_name == ""
        assert tests[1].class_name == "TestGroup"


class TestDiscoverTests:
    def test_nonexistent_file(self):
        assert discover_tests("/nonexistent/test_file.py") == []

    def test_non_python_file(self):
        assert discover_tests("test_file.js") == []

    def test_real_file(self, tmp_path):
        f = tmp_path / "test_example.py"
        f.write_text("""\
class TestExample:
    def test_one(self):
        pass

    def test_two(self):
        pass

def test_standalone():
    pass
""")
        tests = discover_tests(str(f))
        names = [t.display_name for t in tests]
        assert "TestExample::test_one" in names
        assert "TestExample::test_two" in names
        assert "test_standalone" in names

    def test_decorated_tests(self, tmp_path):
        f = tmp_path / "test_decorated.py"
        f.write_text("""\
import pytest

@pytest.mark.parametrize("x", [1, 2])
def test_param(x):
    assert x > 0

@pytest.fixture
def my_fixture():
    return 42

class TestDeco:
    @pytest.mark.slow
    def test_slow(self):
        pass
""")
        tests = discover_tests(str(f))
        names = [t.name for t in tests]
        assert "test_param" in names
        assert "test_slow" in names
        assert "my_fixture" not in names
