"""
Comprehensive tests for utility functions.

This module contains tests for utility functions across different modules:
- Miscellaneous utilities (first, ensure_tuple, etc.)
- Module utilities (instantiate, look_up_option, etc.)
- Enums (CompInitMode, StrEnum)
"""

import os
import warnings
from collections import Counter
from enum import Enum
from functools import partial

import pytest

from sparkwheel.utils import (
    CheckKeyDuplicatesYamlLoader,
    check_key_duplicates,
    damerau_levenshtein_distance,
    ensure_tuple,
    first,
    instantiate,
    issequenceiterable,
    look_up_option,
    optional_import,
)
from sparkwheel.utils.enums import CompInitMode, StrEnum
from sparkwheel.utils.exceptions import InstantiationError
from sparkwheel.utils.module import OptionalImportError


class TestMiscUtils:
    """Test miscellaneous utility functions."""

    @pytest.mark.parametrize(
        "iterable,expected",
        [
            ([1, 2, 3], 1),
            ((10, 20, 30), 10),
            ("abc", "a"),
        ],
    )
    def test_first_with_items(self, iterable, expected):
        """Test first returns first item."""
        assert first(iterable) == expected

    @pytest.mark.parametrize("iterable", [[], ()])
    def test_first_empty_default_none(self, iterable):
        """Test first returns None for empty iterable."""
        assert first(iterable) is None

    @pytest.mark.parametrize(
        "iterable,default,expected",
        [
            ([], 42, 42),
            ((), "default", "default"),
        ],
    )
    def test_first_empty_with_default(self, iterable, default, expected):
        """Test first returns default for empty iterable."""
        assert first(iterable, default=default) == expected

    def test_first_generator(self):
        """Test first works with generator."""

        def gen():
            yield 1
            yield 2

        assert first(gen()) == 1

    @pytest.mark.parametrize("value", [[1, 2, 3], (1, 2, 3), {1, 2, 3}, {"a": 1}, range(5)])
    def test_issequenceiterable_true(self, value):
        """Test issequenceiterable with iterable sequences."""
        assert issequenceiterable(value) is True

    @pytest.mark.parametrize("value", ["string", b"bytes", 42, 3.14, None])
    def test_issequenceiterable_false(self, value):
        """Test issequenceiterable returns False for non-iterables."""
        assert issequenceiterable(value) is False

    def test_issequenceiterable_exception_handling(self):
        """Test issequenceiterable handles exceptions from ndim."""

        class BadNdim:
            @property
            def ndim(self):
                raise RuntimeError("Bad")

        assert issequenceiterable(BadNdim()) is False

    @pytest.mark.parametrize(
        "value,expected",
        [
            ([1, 2, 3], (1, 2, 3)),
            ((1, 2, 3), (1, 2, 3)),
            (42, (42,)),
            ("string", ("string",)),
            (None, (None,)),
        ],
    )
    def test_ensure_tuple(self, value, expected):
        """Test ensure_tuple converts values to tuple."""
        result = ensure_tuple(value)
        assert result == expected
        assert isinstance(result, tuple)

    def test_ensure_tuple_from_set(self):
        """Test ensure_tuple converts set to tuple."""
        result = ensure_tuple({1, 2, 3})
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_check_key_duplicates_no_duplicates(self):
        """Test check_key_duplicates with unique keys."""
        pairs = [("a", 1), ("b", 2), ("c", 3)]
        result = check_key_duplicates(pairs)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_check_key_duplicates_with_duplicates_warning(self):
        """Test check_key_duplicates warns on duplicates."""
        pairs = [("a", 1), ("b", 2), ("a", 3)]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = check_key_duplicates(pairs)
            assert len(w) > 0
            assert "Duplicate key" in str(w[0].message)
            assert result == {"a": 3, "b": 2}

    def test_check_key_duplicates_strict_mode(self):
        """Test check_key_duplicates raises error in strict mode."""
        original = os.environ.get("SPARKWHEEL_STRICT_KEYS")
        try:
            os.environ["SPARKWHEEL_STRICT_KEYS"] = "1"
            pairs = [("a", 1), ("b", 2), ("a", 3)]
            with pytest.raises(ValueError, match="Duplicate key"):
                check_key_duplicates(pairs)
        finally:
            if original is None:
                os.environ.pop("SPARKWHEEL_STRICT_KEYS", None)
            else:
                os.environ["SPARKWHEEL_STRICT_KEYS"] = original

    def test_yaml_loader_duplicate_warning(self):
        """Test CheckKeyDuplicatesYamlLoader warns on duplicates."""
        import yaml

        yaml_str = """
a: 1
b: 2
a: 3
"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = yaml.load(yaml_str, CheckKeyDuplicatesYamlLoader)
            assert len(w) > 0
            assert result["a"] == 3

    def test_yaml_loader_duplicate_strict(self):
        """Test CheckKeyDuplicatesYamlLoader raises error in strict mode."""
        import yaml

        original = os.environ.get("SPARKWHEEL_STRICT_KEYS")
        try:
            os.environ["SPARKWHEEL_STRICT_KEYS"] = "1"
            yaml_str = """
a: 1
a: 2
"""
            with pytest.raises(ValueError, match="Duplicate key"):
                yaml.load(yaml_str, CheckKeyDuplicatesYamlLoader)
        finally:
            if original is None:
                os.environ.pop("SPARKWHEEL_STRICT_KEYS", None)
            else:
                os.environ["SPARKWHEEL_STRICT_KEYS"] = original


class TestModuleUtils:
    """Test module-related utility functions."""

    @pytest.mark.parametrize(
        "str1,str2,expected",
        [
            ("test", "test", 0),
            ("", "", 0),
            ("", "abc", 3),
            ("abc", "", 3),
            ("cat", "bat", 1),
            ("cat", "cats", 1),
            ("cats", "cat", 1),
            ("ab", "ba", 1),
        ],
    )
    def test_damerau_levenshtein_distance(self, str1, str2, expected):
        """Test Damerau-Levenshtein distance calculation."""
        assert damerau_levenshtein_distance(str1, str2) == expected

    def test_look_up_option_string_in_set(self):
        """Test look_up_option finds string in set."""
        result = look_up_option("red", {"red", "blue", "green"})
        assert result == "red"

    def test_look_up_option_string_in_list(self):
        """Test look_up_option finds string in list."""
        result = look_up_option("apple", ["apple", "banana", "cherry"])
        assert result == "apple"

    def test_look_up_option_string_in_dict(self):
        """Test look_up_option finds key in dict."""
        result = look_up_option("key1", {"key1": "value1", "key2": "value2"})
        assert result == "value1"

    def test_look_up_option_enum_by_value(self):
        """Test look_up_option finds enum by value string."""
        result = look_up_option("default", CompInitMode)
        assert result == CompInitMode.DEFAULT

    def test_look_up_option_enum_by_member(self):
        """Test look_up_option finds enum by member."""
        result = look_up_option(CompInitMode.DEFAULT, CompInitMode)
        assert result == CompInitMode.DEFAULT

    def test_look_up_option_enum_not_in_values(self):
        """Test look_up_option with enum member not matching."""
        with pytest.raises(ValueError):
            look_up_option(999, CompInitMode)

    def test_look_up_option_not_found_with_default(self):
        """Test look_up_option returns default when not found."""
        result = look_up_option("missing", {"a", "b", "c"}, default="fallback")
        assert result == "fallback"

    def test_look_up_option_not_found_raises(self):
        """Test look_up_option raises ValueError when not found."""
        with pytest.raises(ValueError, match="Unsupported option"):
            look_up_option("missing", {"a", "b", "c"})

    def test_look_up_option_close_match_suggestion(self):
        """Test look_up_option suggests close match."""
        with pytest.raises(ValueError, match="did you mean"):
            look_up_option("rad", {"red", "blue", "green"})

    def test_look_up_option_no_close_match(self):
        """Test look_up_option without close match."""
        with pytest.raises(ValueError):
            look_up_option("wxyz", {"abc", "def", "ghi"})

    def test_look_up_option_empty_collection(self):
        """Test look_up_option with empty collection."""
        with pytest.raises(ValueError, match="No options available"):
            look_up_option("any", set())

    def test_look_up_option_with_none_collection(self):
        """Test look_up_option with None as collection."""
        with pytest.raises(ValueError, match="No options"):
            look_up_option("any", None)

    def test_look_up_option_whitespace_stripped(self):
        """Test look_up_option strips whitespace from string."""
        result = look_up_option("  red  ", {"red", "blue"})
        assert result == "red"

    def test_look_up_option_non_hashable(self):
        """Test look_up_option raises error for non-hashable."""
        with pytest.raises(ValueError, match="Unrecognized option type"):
            look_up_option([1, 2], {"a", "b"})

    def test_look_up_option_print_all_options_false(self):
        """Test look_up_option with print_all_options=False."""
        with pytest.raises(ValueError) as exc_info:
            look_up_option("missing", {"a", "b", "c"}, print_all_options=False)
        assert "Available options" not in str(exc_info.value)

    def test_optional_import_success(self):
        """Test optional_import with valid module."""
        module, success = optional_import("os")
        assert success is True
        import os as expected_os

        assert module is expected_os

    def test_optional_import_with_name(self):
        """Test optional_import with specific name."""
        module, success = optional_import("collections", name="Counter")
        assert success is True
        assert module is Counter

    def test_optional_import_failure(self):
        """Test optional_import with invalid module."""
        module, success = optional_import("nonexistent_module_xyz")
        assert success is False

    def test_optional_import_failure_raises_on_access(self):
        """Test optional_import raises on accessing failed import."""
        module, success = optional_import("nonexistent_module_xyz")
        assert success is False
        with pytest.raises(OptionalImportError):
            _ = module.some_attribute

    def test_instantiate_class_default_mode(self):
        """Test instantiate with class in default mode."""
        result = instantiate("dict", "default", a=1, b=2)
        assert isinstance(result, dict)
        assert result == {"a": 1, "b": 2}

    def test_instantiate_callable_mode_no_kwargs(self):
        """Test instantiate with callable mode and no kwargs."""
        result = instantiate("collections.Counter", "callable")
        assert result is Counter

    def test_instantiate_callable_mode_with_kwargs(self):
        """Test instantiate with callable mode and kwargs."""
        result = instantiate("collections.Counter", "callable", iterable=[1, 2])
        assert isinstance(result, partial)
        counter = result()
        assert isinstance(counter, Counter)

    def test_instantiate_callable_mode_returns_partial(self):
        """Test callable mode with kwargs returns partial."""
        result = instantiate("dict", "callable", a=1)
        assert isinstance(result, partial)
        assert result() == {"a": 1}

    def test_instantiate_with_callable_object(self):
        """Test instantiate with callable object instead of string."""
        result = instantiate(dict, "default", a=1, b=2)
        assert isinstance(result, dict)
        assert result == {"a": 1, "b": 2}

    def test_instantiate_not_found(self):
        """Test instantiate raises error for non-existent path."""
        from sparkwheel.utils.exceptions import ModuleNotFoundError

        with pytest.raises(ModuleNotFoundError, match="Cannot locate"):
            instantiate("nonexistent.module.Class", "default")

    def test_instantiate_not_callable_warning(self):
        """Test instantiate warns for non-callable."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            instantiate("sys.version", "default")
            assert len(w) > 0
            assert "not callable" in str(w[0].message)

    def test_instantiate_invalid_mode(self):
        """Test instantiate with invalid mode."""
        with pytest.raises(ValueError):
            instantiate("dict", "invalid_mode")

    def test_instantiate_error_handling(self):
        """Test instantiate error handling."""
        with pytest.raises((InstantiationError, RuntimeError, TypeError)):
            instantiate("int", "default", invalid_arg="not_an_int")

    def test_instantiate_debug_mode_with_dict(self):
        """Test instantiate in debug mode."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = instantiate("dict", "debug", a=1)
            assert any("pdb" in str(warning.message).lower() for warning in w)
            assert result == {"a": 1}


class TestEnums:
    """Test enum classes."""

    @pytest.mark.parametrize(
        "mode,value",
        [
            (CompInitMode.DEFAULT, "default"),
            (CompInitMode.CALLABLE, "callable"),
            (CompInitMode.DEBUG, "debug"),
        ],
    )
    def test_comp_init_mode_values(self, mode, value):
        """Test CompInitMode enum values."""
        assert mode == value
        assert isinstance(mode, str)

    def test_str_enum_inheritance(self):
        """Test StrEnum is subclass of str and Enum."""
        assert issubclass(StrEnum, str)
        assert issubclass(StrEnum, Enum)

    def test_comp_init_mode_iteration(self):
        """Test iterating over CompInitMode."""
        modes = list(CompInitMode)
        assert len(modes) == 3
        assert CompInitMode.DEFAULT in modes
        assert CompInitMode.CALLABLE in modes
        assert CompInitMode.DEBUG in modes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
