"""Tests for path utility functions."""

import pytest

from sparkwheel.path_utils import PathPatterns, find_references, get_by_id


class TestPathPatterns:
    """Test PathPatterns class."""

    def test_find_absolute_references_in_expression(self):
        """Test finding references in expression."""
        refs = PathPatterns.find_absolute_references("$some_func(@model::lr, @optimizer)")
        # The function returns IDs without the @ symbol
        assert "model::lr" in refs
        assert "optimizer" in refs

    def test_find_absolute_references_in_plain_text(self):
        """Test finding references returns empty for plain text."""
        refs = PathPatterns.find_absolute_references("plain text without references")
        assert refs == []

    def test_find_references_function(self):
        """Test find_references utility function."""
        # Test the wrapper function - returns IDs without @
        refs = find_references("$some_func(@model::lr)")
        assert "model::lr" in refs

    def test_find_references_empty_for_plain_text(self):
        """Test find_references returns empty for plain text."""
        refs = find_references("just plain text")
        assert refs == []


class TestGetById:
    """Test get_by_id function for navigating config structures."""

    def test_empty_id_returns_whole_config(self):
        """Test get_by_id with empty ID returns whole config."""
        config = {"key": "value", "nested": {"item": 123}}
        result = get_by_id(config, "")

        assert result == config

    def test_list_indexing(self):
        """Test get_by_id with list indexing."""
        config = {"items": [10, 20, 30]}
        result = get_by_id(config, "items::1")

        assert result == 20

    def test_nested_list(self):
        """Test get_by_id with nested structures including lists."""
        config = {"data": {"values": [{"x": 1}, {"x": 2}, {"x": 3}]}}
        result = get_by_id(config, "data::values::2::x")

        assert result == 3

    def test_type_error_on_primitive(self):
        """Test get_by_id raises TypeError when trying to index a primitive value."""
        config = {"value": 42}

        with pytest.raises(TypeError, match="Cannot index int"):
            get_by_id(config, "value::subkey")

    def test_missing_key_first_level(self):
        """Test get_by_id with missing key at first level shows non-redundant error."""
        config = {"foo": 1, "bar": 2}

        with pytest.raises(KeyError) as exc_info:
            get_by_id(config, "missing")

        error_msg = str(exc_info.value)
        assert "Key 'missing' not found" in error_msg
        assert "Available keys:" in error_msg
        assert "'foo'" in error_msg
        assert "'bar'" in error_msg
        # Should NOT say "at path 'missing'" for first level
        assert "at path" not in error_msg

    def test_missing_key_nested(self):
        """Test get_by_id with missing nested key shows parent path."""
        config = {"data": {"train": {"lr": 0.001, "epochs": 10}}}

        with pytest.raises(KeyError) as exc_info:
            get_by_id(config, "data::train::missing")

        error_msg = str(exc_info.value)
        assert "Key 'missing' not found in 'data::train'" in error_msg
        assert "Available keys:" in error_msg
        assert "'lr'" in error_msg
        assert "'epochs'" in error_msg

    def test_invalid_list_index(self):
        """Test get_by_id with invalid list index."""
        config = {"items": [1, 2, 3]}

        with pytest.raises(KeyError) as exc_info:
            get_by_id(config, "items::10")

        error_msg = str(exc_info.value)
        assert "List index '10' out of range" in error_msg
        assert "in 'items'" in error_msg

    def test_invalid_list_index_first_level(self):
        """Test get_by_id with invalid list index at first level."""
        config = [1, 2, 3]

        with pytest.raises(KeyError) as exc_info:
            get_by_id(config, "10")

        error_msg = str(exc_info.value)
        assert "List index '10' out of range" in error_msg
        # Should not mention parent path for first level
        assert "in '" not in error_msg

    def test_invalid_list_index_non_integer(self):
        """Test get_by_id with non-integer list index."""
        config = {"items": [1, 2, 3]}

        with pytest.raises(KeyError) as exc_info:
            get_by_id(config, "items::abc")

        error_msg = str(exc_info.value)
        assert "Invalid list index 'abc'" in error_msg
        assert "not an integer" in error_msg

    def test_type_error_first_level(self):
        """Test type error at first level shows clean message."""
        config = "string_value"

        with pytest.raises(TypeError) as exc_info:
            get_by_id(config, "foo")

        error_msg = str(exc_info.value)
        assert "Cannot index str with key 'foo'" in error_msg
        # Should not mention parent path for first level
        assert "in '" not in error_msg

    def test_type_error_nested(self):
        """Test type error in nested path shows parent."""
        config = {"data": {"value": 42}}

        with pytest.raises(TypeError) as exc_info:
            get_by_id(config, "data::value::foo")

        error_msg = str(exc_info.value)
        assert "Cannot index int with key 'foo'" in error_msg
        assert "in 'data::value'" in error_msg

    def test_available_keys_truncated(self):
        """Test that available keys list is truncated when > 10 keys."""
        config = {f"key_{i}": i for i in range(20)}

        with pytest.raises(KeyError) as exc_info:
            get_by_id(config, "missing")

        error_msg = str(exc_info.value)
        assert "Available keys:" in error_msg
        assert "..." in error_msg  # Should be truncated
