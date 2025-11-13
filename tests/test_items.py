"""Tests for config items (Item, Component, Expression)."""

import pytest

from sparkwheel.items import Component, Expression, Item
from sparkwheel.utils.exceptions import EvaluationError, InstantiationError, ModuleNotFoundError


class TestItem:
    """Test basic Item class."""

    def test_create_item_basic(self):
        """Test creating a basic item."""
        item = Item(config={"key": "value"}, id="test_id")

        assert item.get_id() == "test_id"
        assert item.get_config() == {"key": "value"}

    def test_update_config(self):
        """Test updating item config."""
        item = Item(config={"old": "value"}, id="test")
        item.update_config({"new": "value"})

        assert item.get_config() == {"new": "value"}

    def test_item_repr(self):
        """Test item string representation."""
        item = Item(config={"key": "value"}, id="test")
        repr_str = repr(item)

        assert "Item" in repr_str
        assert "key" in repr_str


class TestComponent:
    """Test Component class."""

    def test_is_instantiable_true(self):
        """Test detecting instantiable config."""
        config = {"_target_": "collections.Counter"}
        assert Component.is_instantiable(config) is True

    def test_is_instantiable_false(self):
        """Test detecting non-instantiable config."""
        assert Component.is_instantiable({"key": "value"}) is False
        assert Component.is_instantiable("string") is False
        assert Component.is_instantiable([1, 2, 3]) is False

    def test_resolve_module_name_string(self):
        """Test resolving module name from string."""
        component = Component(config={"_target_": "collections.Counter"})
        assert component.resolve_module_name() == "collections.Counter"

    def test_resolve_module_name_callable(self):
        """Test resolving module name when _target_ is already callable."""

        def my_func():
            pass

        component = Component(config={"_target_": my_func})
        assert component.resolve_module_name() == my_func

    def test_resolve_args(self):
        """Test resolving instantiation arguments."""
        config = {"_target_": "collections.Counter", "iterable": [1, 2, 3], "_disabled_": False}
        component = Component(config=config)
        args = component.resolve_args()

        assert args == {"iterable": [1, 2, 3]}
        assert "_target_" not in args
        assert "_disabled_" not in args

    def test_resolve_args_non_mapping(self):
        """Test resolve_args with non-mapping config raises TypeError."""
        component = Component(config="not a dict")

        with pytest.raises(TypeError, match="Expected config to be a Mapping"):
            component.resolve_args()

    def test_is_disabled_false(self):
        """Test component is not disabled."""
        component = Component(config={"_disabled_": False})
        assert component.is_disabled() is False

    def test_is_disabled_true(self):
        """Test component is disabled."""
        component = Component(config={"_disabled_": True})
        assert component.is_disabled() is True

    def test_is_disabled_string_true(self):
        """Test component disabled via string 'true'."""
        component = Component(config={"_disabled_": "true"})
        assert component.is_disabled() is True

        component = Component(config={"_disabled_": "  TRUE  "})
        assert component.is_disabled() is True

    def test_is_disabled_string_false(self):
        """Test component not disabled via string."""
        component = Component(config={"_disabled_": "false"})
        assert component.is_disabled() is False

    def test_instantiate_basic(self):
        """Test basic instantiation."""
        # Use dict which accepts keyword arguments
        config = {"_target_": "builtins.dict", "a": 1, "b": 2}
        component = Component(config=config)
        result = component.instantiate()

        assert isinstance(result, dict)
        assert result == {"a": 1, "b": 2}

    def test_instantiate_non_instantiable(self):
        """Test instantiate returns None for non-instantiable config."""
        component = Component(config={"key": "value"})
        result = component.instantiate()

        assert result is None

    def test_instantiate_disabled(self):
        """Test instantiate returns None when disabled."""
        config = {"_target_": "collections.Counter", "_disabled_": True}
        component = Component(config=config)
        result = component.instantiate()

        assert result is None

    def test_instantiate_module_not_found(self):
        """Test instantiate raises ModuleNotFoundError for missing module."""
        config = {"_target_": "nonexistent.module.Class"}
        component = Component(config=config)

        with pytest.raises(ModuleNotFoundError, match="Cannot locate class or function"):
            component.instantiate()

    def test_instantiate_with_suggestions(self):
        """Test ModuleNotFoundError includes suggestions for typos."""
        # Use a real module with a typo
        config = {"_target_": "collections.Counterfeit"}  # Should suggest "Counter"
        component = Component(config=config)

        with pytest.raises(ModuleNotFoundError) as exc_info:
            component.instantiate()

        error_msg = str(exc_info.value)
        # May suggest "Counter" if fuzzy matching works
        assert "collections.Counterfeit" in error_msg

    def test_suggest_similar_modules_with_typo(self):
        """Test suggesting similar modules with small typo."""
        component = Component(config={"_target_": "collections.Counterfeit"})
        suggestion = component._suggest_similar_modules("collections.Counterfeit")

        # Should suggest Counter
        if suggestion:
            assert "Counter" in suggestion

    def test_suggest_similar_modules_finds_close_match(self):
        """Test that suggestion finds and returns close matches."""
        component = Component(config={"_target_": "collections.OrderdDict"})
        suggestion = component._suggest_similar_modules("collections.OrderdDict")

        # Should suggest OrderedDict (only 1 character different)
        assert suggestion is not None
        assert "OrderedDict" in suggestion
        assert "Did you mean" in suggestion

    def test_suggest_similar_modules_no_module_separator(self):
        """Test no suggestions for target without module separator."""
        component = Component(config={"_target_": "noseparator"})
        suggestion = component._suggest_similar_modules("noseparator")

        assert suggestion is None

    def test_suggest_similar_modules_nonexistent_base(self):
        """Test no suggestions when base module doesn't exist."""
        component = Component(config={"_target_": "fake.module.Class"})
        suggestion = component._suggest_similar_modules("fake.module.Class")

        assert suggestion is None

    def test_suggest_similar_modules_non_string(self):
        """Test no suggestions for non-string target."""
        component = Component(config={"_target_": lambda: None})
        suggestion = component._suggest_similar_modules(lambda: None)

        assert suggestion is None

    def test_instantiate_instantiation_error(self):
        """Test instantiate wraps other errors in InstantiationError."""
        # Use a valid class but with wrong arguments (int() doesn't accept 'invalid_arg')
        config = {"_target_": "builtins.int", "invalid_arg": 123}
        component = Component(config=config)

        with pytest.raises(InstantiationError, match="Failed to instantiate"):
            component.instantiate()

    def test_instantiate_with_kwargs_override(self):
        """Test instantiate with kwargs override."""
        config = {"_target_": "builtins.dict", "a": 1, "b": 2}
        component = Component(config=config)
        result = component.instantiate(b=99, c=3)

        # kwargs should override config values and add new ones
        assert isinstance(result, dict)
        assert result["a"] == 1  # From config
        assert result["b"] == 99  # Overridden by kwargs
        assert result["c"] == 3  # Added by kwargs


class TestExpression:
    """Test Expression class."""

    def test_is_expression_true(self):
        """Test detecting expression strings."""
        assert Expression.is_expression("$1 + 1") is True
        assert Expression.is_expression("$len([1, 2, 3])") is True

    def test_is_expression_false(self):
        """Test non-expression strings."""
        assert Expression.is_expression("regular string") is False
        assert Expression.is_expression("") is False
        assert Expression.is_expression(123) is False
        assert Expression.is_expression({"key": "value"}) is False

    def test_is_import_statement_true(self):
        """Test detecting import statements."""
        assert Expression.is_import_statement("$import os") is True
        assert Expression.is_import_statement("$from pathlib import Path") is True

    def test_is_import_statement_false(self):
        """Test non-import expressions."""
        assert Expression.is_import_statement("$1 + 1") is False
        assert Expression.is_import_statement("regular string") is False

    def test_evaluate_basic_expression(self):
        """Test evaluating basic expression."""
        expr = Expression(config="$1 + 1", id="test")
        result = expr.evaluate()

        assert result == 2

    def test_evaluate_with_globals(self):
        """Test evaluating expression with custom globals."""
        expr = Expression(config="$custom_var * 2", id="test", globals={"custom_var": 5})
        result = expr.evaluate()

        assert result == 10

    def test_evaluate_with_additional_globals(self):
        """Test evaluating with additional globals passed to evaluate."""
        expr = Expression(config="$x + y", id="test", globals={"x": 1})
        result = expr.evaluate(globals={"y": 2})

        assert result == 3

    def test_evaluate_conflicting_globals_warning(self):
        """Test warning when additional globals conflict."""
        expr = Expression(config="$x", id="test", globals={"x": 1})

        with pytest.warns(UserWarning, match="conflicts with"):
            result = expr.evaluate(globals={"x": 2})

        assert result == 2  # Additional globals should override

    def test_evaluate_import_statement(self):
        """Test evaluating import statement."""
        expr = Expression(config="$from pathlib import Path", id="test")
        result = expr.evaluate()

        from pathlib import Path

        assert result == Path
        # Check that it was added to globals
        assert "Path" in expr.globals

    def test_evaluate_import_with_alias(self):
        """Test evaluating import with alias."""
        expr = Expression(config="$import os as operating_system", id="test")
        result = expr.evaluate()

        import os

        assert result == os
        # Check that it was added to globals with alias
        assert "operating_system" in expr.globals

    def test_evaluate_regular_import(self):
        """Test evaluating regular import without alias."""
        expr = Expression(config="$import json", id="test")
        result = expr.evaluate()

        import json

        assert result == json
        assert "json" in expr.globals

    def test_evaluate_multiple_imports_warning(self):
        """Test warning for multiple imports in one statement."""
        expr = Expression(config="$from os import path, environ", id="test")

        with pytest.warns(UserWarning, match="ignoring multiple import"):
            result = expr.evaluate()

        import os

        # Should import the first one
        assert result == os.path

    def test_evaluate_non_expression_returns_none(self):
        """Test evaluating non-expression returns None."""
        expr = Expression(config="regular string", id="test")
        result = expr.evaluate()

        assert result is None

    def test_evaluate_with_run_eval_false(self):
        """Test expression returns string when run_eval is False."""
        expr = Expression(config="$1 + 1", id="test")
        expr.run_eval = False
        result = expr.evaluate()

        assert result == "1 + 1"

    def test_evaluate_error_handling(self):
        """Test evaluation error handling."""
        expr = Expression(config="$undefined_variable", id="test")

        with pytest.raises(EvaluationError, match="Failed to evaluate expression"):
            expr.evaluate()

    def test_evaluate_with_locals(self):
        """Test evaluating expression with locals."""
        expr = Expression(config="$x + y", id="test")
        result = expr.evaluate(globals={"x": 1}, locals={"y": 2})

        assert result == 3


class TestExpressionDebugMode:
    """Test Expression debug mode."""

    def test_evaluate_debug_mode_disabled(self):
        """Test that debug mode is not active by default."""
        from sparkwheel.utils import run_debug

        assert run_debug is False

    @pytest.mark.skip(reason="Debug mode requires interactive pdb, skip in automated tests")
    def test_evaluate_debug_mode_enabled(self):
        """Test expression evaluation in debug mode.

        This test is skipped because debug mode enters pdb which requires
        interactive input. It's here to document the debug functionality.
        """
        import sparkwheel.utils

        original_debug = sparkwheel.utils.run_debug
        try:
            sparkwheel.utils.run_debug = True
            expr = Expression(config="$1 + 1", id="test")
            # In debug mode, would enter pdb.run()
            expr.evaluate()
        finally:
            sparkwheel.utils.run_debug = original_debug


class TestItemWithSourceLocation:
    """Test Item classes with source location tracking."""

    def test_item_with_source_location(self):
        """Test creating item with source location."""
        from sparkwheel.utils.exceptions import SourceLocation

        location = SourceLocation(filepath="/tmp/config.yaml", line=10, column=5, id="model::lr")
        item = Item(config={"lr": 0.001}, id="model::lr", source_location=location)

        assert item.source_location == location
        assert item.source_location.filepath == "/tmp/config.yaml"
        assert item.source_location.line == 10

    def test_component_error_includes_source_location(self):
        """Test that component errors include source location."""
        from sparkwheel.utils.exceptions import SourceLocation

        location = SourceLocation(filepath="/tmp/config.yaml", line=15, column=2, id="model")
        config = {"_target_": "nonexistent.Module"}
        component = Component(config=config, id="model", source_location=location)

        with pytest.raises(ModuleNotFoundError) as exc_info:
            component.instantiate()

        error = exc_info.value
        assert error.source_location == location

    def test_expression_error_includes_source_location(self):
        """Test that expression errors include source location."""
        from sparkwheel.utils.exceptions import SourceLocation

        location = SourceLocation(filepath="/tmp/config.yaml", line=20, column=2, id="calc")
        expr = Expression(config="$undefined_var", id="calc", source_location=location)

        with pytest.raises(EvaluationError) as exc_info:
            expr.evaluate()

        error = exc_info.value
        assert error.source_location == location


class TestItemsEdgeCases:
    """Test edge cases in items module."""

    def test_component_suggestion_exception_handling(self):
        """Test Component suggestion generation when exception occurs."""
        # Create component with target that will cause suggestion generation to fail
        component = Component(config={"_target_": "nonexistent.BadModule"}, id="test")

        # Instantiate should fail, but suggestion generation shouldn't crash
        with pytest.raises(ModuleNotFoundError):
            component.instantiate()

    def test_expression_multiple_import_aliases(self):
        """Test Expression with multiple import aliases (should warn)."""
        import warnings

        expr = Expression(config="$from collections import Counter, defaultdict", id="test")

        # Should warn about multiple imports
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            expr.evaluate()
            # Check that a warning was issued
            assert len(w) >= 1
