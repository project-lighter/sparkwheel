"""
Basic tests for sparkwheel.
"""

import pytest

from sparkwheel import ConfigParser


def test_basic_config():
    """Test basic configuration parsing."""
    config = {"key1": "value1", "key2": 42}
    parser = ConfigParser(config)
    assert parser["key1"] == "value1"
    assert parser["key2"] == 42


def test_reference():
    """Test reference resolution."""
    config = {"value": 10, "reference": "@value"}
    parser = ConfigParser.from_dict(config)
    result = parser.resolve("reference")
    assert result == 10


def test_expression():
    """Test expression evaluation."""
    config = {"base": 5, "computed": "$@base * 2"}
    parser = ConfigParser.from_dict(config)
    result = parser.resolve("computed")
    assert result == 10


def test_nested_reference():
    """Test nested reference with ::."""
    config = {"nested": {"value": 100}, "ref": "@nested::value"}
    parser = ConfigParser.from_dict(config)
    result = parser.resolve("ref")
    assert result == 100


def test_macro():
    """Test macro expansion with %."""
    config = {"original": {"a": 1, "b": 2}, "copy": "%original"}
    parser = ConfigParser.from_dict(config)
    # After resolve(), macros are expanded
    parser.resolve()
    assert parser["copy"] == {"a": 1, "b": 2}
    # Ensure it's a copy, not the same object
    assert parser["copy"] is not parser["original"]


def test_set_and_get():
    """Test setting and getting config values."""
    config = {}
    parser = ConfigParser(config)
    parser["new_key"] = "new_value"
    assert parser["new_key"] == "new_value"


def test_nested_set():
    """Test setting nested config values."""
    config = {"level1": {}}
    parser = ConfigParser(config)
    parser["level1::level2"] = "nested_value"
    assert parser["level1"]["level2"] == "nested_value"


def test_contains():
    """Test __contains__ method."""
    config = {"exists": True}
    parser = ConfigParser(config)
    assert "exists" in parser
    assert "not_exists" not in parser


def test_disabled_component():
    """Test that disabled components return None."""
    config = {
        "component": {
            "_target_": "dict",  # Simple callable
            "_disabled_": True,
        }
    }
    parser = ConfigParser.from_dict(config)
    result = parser.resolve("component", instantiate=True)
    assert result is None


def test_expression_with_builtin():
    """Test expression using Python builtins."""
    config = {"items": [1, 2, 3, 4, 5], "count": "$len(@items)"}
    parser = ConfigParser.from_dict(config)
    result = parser.resolve("count")
    assert result == 5


def test_multiple_references():
    """Test multiple references in one expression."""
    config = {"a": 10, "b": 20, "sum": "$@a + @b"}
    parser = ConfigParser.from_dict(config)
    result = parser.resolve("sum")
    assert result == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
