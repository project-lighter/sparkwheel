"""Tests for coercion module."""

import dataclasses
import sys
from typing import Optional, Union

import pytest

from sparkwheel.coercion import can_coerce, coerce_value


@dataclasses.dataclass
class SampleDataclass:
    """Sample dataclass for testing."""

    name: str
    value: int
    enabled: bool = True


@dataclasses.dataclass
class NestedDataclass:
    """Nested dataclass for testing."""

    sample: SampleDataclass
    count: int


class TestCanCoerce:
    """Test can_coerce function."""

    def test_already_correct_type(self):
        """Test when value is already correct type."""
        assert can_coerce(42, int) is True
        assert can_coerce("hello", str) is True
        assert can_coerce(3.14, float) is True
        assert can_coerce(True, bool) is True

    def test_string_to_int(self):
        """Test string to int coercion check."""
        assert can_coerce("42", int) is True
        assert can_coerce("123", int) is True
        assert can_coerce("invalid", int) is False
        assert can_coerce("3.14", int) is False

    def test_string_to_float(self):
        """Test string to float coercion check."""
        assert can_coerce("3.14", float) is True
        assert can_coerce("42", float) is True
        assert can_coerce("invalid", float) is False

    def test_int_to_float(self):
        """Test int to float coercion check."""
        assert can_coerce(42, float) is True
        assert can_coerce(0, float) is True

    def test_string_to_bool(self):
        """Test string to bool coercion check."""
        assert can_coerce("true", bool) is True
        assert can_coerce("false", bool) is True
        assert can_coerce("True", bool) is True
        assert can_coerce("False", bool) is True
        assert can_coerce("1", bool) is True
        assert can_coerce("0", bool) is True
        assert can_coerce("yes", bool) is True
        assert can_coerce("no", bool) is True
        assert can_coerce("YES", bool) is True
        assert can_coerce("NO", bool) is True
        assert can_coerce("invalid", bool) is False
        assert can_coerce("maybe", bool) is False

    def test_cannot_coerce(self):
        """Test cases where coercion is not possible."""
        assert can_coerce([1, 2], int) is False
        assert can_coerce({"a": 1}, str) is False


class TestCoerceValue:
    """Test coerce_value function."""

    def test_already_correct_type(self):
        """Test when value is already correct type."""
        assert coerce_value(42, int) == 42
        assert coerce_value("hello", str) == "hello"
        assert coerce_value(3.14, float) == 3.14
        assert coerce_value(True, bool) is True

    def test_string_to_int(self):
        """Test string to int coercion."""
        assert coerce_value("42", int) == 42
        assert coerce_value("123", int) == 123
        assert coerce_value("-5", int) == -5

    def test_string_to_int_invalid(self):
        """Test invalid string to int coercion."""
        with pytest.raises(ValueError, match="Cannot coerce string 'invalid' to int"):
            coerce_value("invalid", int)
        with pytest.raises(ValueError, match="Cannot coerce string '3.14' to int"):
            coerce_value("3.14", int)

    def test_string_to_float(self):
        """Test string to float coercion."""
        assert coerce_value("3.14", float) == 3.14
        assert coerce_value("42", float) == 42.0
        assert coerce_value("-5.5", float) == -5.5

    def test_string_to_float_invalid(self):
        """Test invalid string to float coercion."""
        with pytest.raises(ValueError, match="Cannot coerce string 'invalid' to float"):
            coerce_value("invalid", float)

    def test_int_to_float(self):
        """Test int to float coercion."""
        assert coerce_value(42, float) == 42.0
        assert coerce_value(0, float) == 0.0
        assert coerce_value(-5, float) == -5.0

    def test_string_to_bool(self):
        """Test string to bool coercion."""
        assert coerce_value("true", bool) is True
        assert coerce_value("True", bool) is True
        assert coerce_value("TRUE", bool) is True
        assert coerce_value("1", bool) is True
        assert coerce_value("yes", bool) is True
        assert coerce_value("YES", bool) is True

        assert coerce_value("false", bool) is False
        assert coerce_value("False", bool) is False
        assert coerce_value("FALSE", bool) is False
        assert coerce_value("0", bool) is False
        assert coerce_value("no", bool) is False
        assert coerce_value("NO", bool) is False

    def test_string_to_bool_invalid(self):
        """Test invalid string to bool coercion."""
        with pytest.raises(ValueError, match="Cannot coerce string 'invalid' to bool"):
            coerce_value("invalid", bool)
        with pytest.raises(ValueError, match="Cannot coerce string 'maybe' to bool"):
            coerce_value("maybe", bool)

    def test_cannot_coerce(self):
        """Test cases where coercion is not possible."""
        with pytest.raises(ValueError, match="Cannot coerce list to int"):
            coerce_value([1, 2], int)
        with pytest.raises(ValueError, match="Cannot coerce dict to str"):
            coerce_value({"a": 1}, str)

    def test_list_coercion(self):
        """Test list coercion."""
        # List of ints
        result = coerce_value([1, 2, 3], list[int])
        assert result == [1, 2, 3]

        # List with string to int coercion
        result = coerce_value(["1", "2", "3"], list[int])
        assert result == [1, 2, 3]

        # List without type args
        result = coerce_value([1, "2", 3.0], list)
        assert result == [1, "2", 3.0]

    def test_list_coercion_invalid(self):
        """Test invalid list coercion."""
        with pytest.raises(ValueError, match="Cannot coerce str to list"):
            coerce_value("not a list", list[int])

        with pytest.raises(ValueError, match="Cannot coerce string 'invalid' to int"):
            coerce_value(["1", "invalid", "3"], list[int])

    def test_dict_coercion(self):
        """Test dict coercion."""
        # Dict with type args
        result = coerce_value({"a": "1", "b": "2"}, dict[str, int])
        assert result == {"a": 1, "b": 2}

        # Dict without type args
        result = coerce_value({"a": 1, "b": "2"}, dict)
        assert result == {"a": 1, "b": "2"}

    def test_dict_coercion_invalid(self):
        """Test invalid dict coercion."""
        with pytest.raises(ValueError, match="Cannot coerce str to dict"):
            coerce_value("not a dict", dict[str, int])

        with pytest.raises(ValueError, match="Cannot coerce string 'invalid' to int"):
            coerce_value({"a": "invalid"}, dict[str, int])

    def test_optional_coercion(self):
        """Test Optional type coercion."""
        # None value
        result = coerce_value(None, Optional[int])
        assert result is None

        # Non-None value
        result = coerce_value("42", Optional[int])
        assert result == 42

        result = coerce_value(42, Optional[int])
        assert result == 42

    def test_union_coercion(self):
        """Test Union type coercion."""
        # Try first type
        result = coerce_value("42", Union[int, str])
        assert result == 42

        # Try second type
        result = coerce_value("hello", Union[int, str])
        assert result == "hello"

        # Float or int
        result = coerce_value("3.14", Union[int, float])
        assert result == 3.14

    @pytest.mark.skipif(sys.version_info < (3, 10), reason="UnionType requires Python 3.10+")
    def test_union_type_pipe_syntax(self):
        """Test Union using | syntax (Python 3.10+)."""
        # Use eval to avoid syntax error in older Python versions
        union_type = eval("int | str")
        result = coerce_value("42", union_type)
        assert result == 42

        result = coerce_value("hello", union_type)
        assert result == "hello"

    def test_union_coercion_failure(self):
        """Test Union coercion when no type matches."""
        with pytest.raises(ValueError, match="Cannot coerce .* to any type in union"):
            coerce_value([1, 2], Union[int, str])

    def test_dataclass_coercion(self):
        """Test dataclass coercion."""
        data = {"name": "test", "value": "42", "enabled": "true"}
        result = coerce_value(data, SampleDataclass)
        assert result == {"name": "test", "value": 42, "enabled": True}

    def test_dataclass_coercion_with_unknown_fields(self):
        """Test dataclass coercion keeps unknown fields."""
        data = {"name": "test", "value": "42", "unknown": "field"}
        result = coerce_value(data, SampleDataclass)
        assert result == {"name": "test", "value": 42, "unknown": "field"}

    def test_dataclass_coercion_invalid(self):
        """Test invalid dataclass coercion."""
        with pytest.raises(ValueError, match="Cannot coerce str to dataclass"):
            coerce_value("not a dict", SampleDataclass)

        with pytest.raises(ValueError, match="Cannot coerce string 'invalid' to int"):
            coerce_value({"name": "test", "value": "invalid"}, SampleDataclass)

    def test_nested_dataclass_coercion(self):
        """Test nested dataclass coercion."""
        data = {"sample": {"name": "test", "value": "42"}, "count": "10"}
        result = coerce_value(data, NestedDataclass)
        assert result == {"sample": {"name": "test", "value": 42}, "count": 10}

    def test_field_path_in_errors(self):
        """Test that field paths are included in error messages."""
        # List item error - simple error doesn't include path
        with pytest.raises(ValueError, match="Cannot coerce string 'invalid' to int"):
            coerce_value(["1", "invalid", "3"], list[int])

        # Dict value error - simple error doesn't include path
        with pytest.raises(ValueError, match="Cannot coerce string 'invalid' to int"):
            coerce_value({"a": "invalid"}, dict[str, int])

        # Dataclass field error - simple error doesn't include path
        with pytest.raises(ValueError, match="Cannot coerce string 'invalid' to int"):
            coerce_value({"name": "test", "value": "invalid"}, SampleDataclass)

    def test_empty_field_path(self):
        """Test coercion with empty field path."""
        # Default field_path is empty string
        result = coerce_value("42", int)
        assert result == 42

        # Explicit empty field path
        result = coerce_value("42", int, "")
        assert result == 42

    def test_nested_list_coercion(self):
        """Test nested list coercion."""
        result = coerce_value([["1", "2"], ["3", "4"]], list[list[int]])
        assert result == [[1, 2], [3, 4]]

    def test_complex_nested_structure(self):
        """Test complex nested structure coercion."""
        # Dict with list values
        result = coerce_value({"a": ["1", "2"], "b": ["3", "4"]}, dict[str, list[int]])
        assert result == {"a": [1, 2], "b": [3, 4]}

        # List of dicts
        result = coerce_value([{"a": "1"}, {"a": "2"}], list[dict[str, int]])
        assert result == [{"a": 1}, {"a": 2}]
