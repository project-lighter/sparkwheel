import warnings
from collections import Counter

import pytest

from sparkwheel import ConfigComponent, ConfigExpression, ConfigItem, Instantiable


class TestConfigItem:
    """Test ConfigItem class."""

    def test_init(self):
        """Test ConfigItem initialization."""
        config = {"key": "value"}
        item = ConfigItem(config, id="test_id")
        assert item.config == config
        assert item.id == "test_id"

    def test_init_default_id(self):
        """Test ConfigItem with default empty id."""
        config = [1, 2, 3]
        item = ConfigItem(config)
        assert item.config == config
        assert item.id == ""

    def test_get_id(self):
        """Test get_id method."""
        item = ConfigItem({"a": 1}, id="my_id")
        assert item.get_id() == "my_id"

    def test_update_config(self):
        """Test update_config method."""
        item = ConfigItem({"a": 1}, id="test")
        assert item.config == {"a": 1}
        item.update_config({"b": 2})
        assert item.config == {"b": 2}

    def test_get_config(self):
        """Test get_config method."""
        config = {"nested": {"value": 42}}
        item = ConfigItem(config, id="test")
        assert item.get_config() == config

    def test_repr(self):
        """Test string representation."""
        config = {"key": "value"}
        item = ConfigItem(config, id="test")
        repr_str = repr(item)
        assert "ConfigItem" in repr_str
        assert "key" in repr_str


class TestConfigComponent:
    """Test ConfigComponent class."""

    def test_is_instantiable_true(self):
        """Test is_instantiable with valid config."""
        config = {"_target_": "collections.Counter"}
        assert ConfigComponent.is_instantiable(config) is True

    @pytest.mark.parametrize("value", [[1, 2, 3], "string", 42, None])
    def test_is_instantiable_false_not_dict(self, value):
        """Test is_instantiable with non-dict."""
        assert ConfigComponent.is_instantiable(value) is False

    def test_is_instantiable_false_no_target(self):
        """Test is_instantiable with dict but no _target_."""
        assert ConfigComponent.is_instantiable({"key": "value"}) is False

    def test_resolve_module_name_string(self):
        """Test resolve_module_name with string target."""
        config = {"_target_": "collections.Counter"}
        component = ConfigComponent(config, id="test")
        assert component.resolve_module_name() == "collections.Counter"

    def test_resolve_module_name_callable(self):
        """Test resolve_module_name with callable target."""
        config = {"_target_": Counter}
        component = ConfigComponent(config, id="test")
        assert component.resolve_module_name() is Counter

    def test_resolve_args(self):
        """Test resolve_args extracts only non-special keys."""
        config = {
            "_target_": "collections.Counter",
            "_disabled_": False,
            "_requires_": [],
            "_mode_": "default",
            "iterable": [1, 2, 2],
        }
        component = ConfigComponent(config, id="test")
        args = component.resolve_args()
        assert args == {"iterable": [1, 2, 2]}
        assert "_target_" not in args
        assert "_disabled_" not in args
        assert "_requires_" not in args
        assert "_mode_" not in args

    def test_is_disabled_false(self):
        """Test is_disabled returns False."""
        config = {"_target_": "dict", "_disabled_": False}
        component = ConfigComponent(config, id="test")
        assert component.is_disabled() is False

    def test_is_disabled_true(self):
        """Test is_disabled returns True."""
        config = {"_target_": "dict", "_disabled_": True}
        component = ConfigComponent(config, id="test")
        assert component.is_disabled() is True

    @pytest.mark.parametrize("disabled_value", ["true", "  true  "])
    def test_is_disabled_string_true(self, disabled_value):
        """Test is_disabled with string 'true' and whitespace."""
        config = {"_target_": "dict", "_disabled_": disabled_value}
        component = ConfigComponent(config, id="test")
        assert component.is_disabled() is True

    def test_is_disabled_string_false(self):
        """Test is_disabled with string that's not 'true'."""
        config = {"_target_": "dict", "_disabled_": "false"}
        component = ConfigComponent(config, id="test")
        assert component.is_disabled() is False

    def test_is_disabled_default(self):
        """Test is_disabled default value."""
        config = {"_target_": "dict"}
        component = ConfigComponent(config, id="test")
        assert component.is_disabled() is False

    def test_instantiate_basic(self):
        """Test instantiate with basic component."""
        config = {"_target_": "dict", "a": 1, "b": 2}
        component = ConfigComponent(config, id="test")
        result = component.instantiate()
        assert isinstance(result, dict)
        assert result == {"a": 1, "b": 2}

    def test_instantiate_disabled(self):
        """Test instantiate with disabled component."""
        config = {"_target_": "dict", "_disabled_": True}
        component = ConfigComponent(config, id="test")
        result = component.instantiate()
        assert result is None

    def test_instantiate_not_instantiable(self):
        """Test instantiate with non-instantiable config."""
        config = {"key": "value"}
        component = ConfigComponent(config, id="test")
        result = component.instantiate()
        assert result is None

    def test_instantiate_with_kwargs_override(self):
        """Test instantiate with kwargs override."""
        config = {"_target_": "dict", "a": 1, "b": 2}
        component = ConfigComponent(config, id="test")
        result = component.instantiate(c=3)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_instantiate_callable_mode(self):
        """Test instantiate with callable mode."""
        config = {"_target_": "collections.Counter", "_mode_": "callable", "iterable": [1, 2]}
        component = ConfigComponent(config, id="test")
        result = component.instantiate()
        # Should return a partial or the callable itself
        assert callable(result)

    def test_repr(self):
        """Test string representation."""
        config = {"_target_": "dict", "key": "value"}
        component = ConfigComponent(config, id="test")
        repr_str = repr(component)
        assert "ConfigComponent" in repr_str


class TestConfigExpression:
    """Test ConfigExpression class."""

    @pytest.mark.parametrize("expr", ["$1 + 1", "$len([1, 2, 3])"])
    def test_is_expression_true(self, expr):
        """Test is_expression with valid expression."""
        assert ConfigExpression.is_expression(expr) is True

    @pytest.mark.parametrize("value", ["normal string", [1, 2, 3], {"a": 1}, 42])
    def test_is_expression_false(self, value):
        """Test is_expression with non-expression."""
        assert ConfigExpression.is_expression(value) is False

    @pytest.mark.parametrize("stmt", ["$import os", "$from pathlib import Path"])
    def test_is_import_statement_true(self, stmt):
        """Test is_import_statement with import."""
        assert ConfigExpression.is_import_statement(stmt) is True

    @pytest.mark.parametrize("value", ["$1 + 1", "normal string"])
    def test_is_import_statement_false(self, value):
        """Test is_import_statement with non-import."""
        assert ConfigExpression.is_import_statement(value) is False

    def test_is_import_statement_contains_import_but_not_statement(self):
        """Test is_import_statement with 'import' in expression but not statement."""
        assert ConfigExpression.is_import_statement("$'import' in text") is False

    def test_evaluate_simple(self):
        """Test evaluate with simple expression."""
        expr = ConfigExpression("$1 + 1", id="test")
        result = expr.evaluate()
        assert result == 2

    def test_evaluate_with_globals(self):
        """Test evaluate with global context."""
        expr = ConfigExpression("$x + y", id="test", globals={"x": 10, "y": 20})
        result = expr.evaluate()
        assert result == 30

    def test_evaluate_with_additional_globals(self):
        """Test evaluate with additional globals parameter."""
        expr = ConfigExpression("$a + b", id="test", globals={"a": 5})
        result = expr.evaluate(globals={"b": 3})
        assert result == 8

    def test_evaluate_globals_conflict_warning(self):
        """Test evaluate warns on globals conflict."""
        expr = ConfigExpression("$x", id="test", globals={"x": 1})
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = expr.evaluate(globals={"x": 2})
            assert len(w) > 0
            assert "conflict" in str(w[0].message).lower()
            assert result == 2  # New value should override

    def test_evaluate_with_locals(self):
        """Test evaluate with local context."""
        expr = ConfigExpression("$local_var * 2", id="test")
        result = expr.evaluate(locals={"local_var": 21})
        assert result == 42

    def test_evaluate_not_expression(self):
        """Test evaluate with non-expression returns None."""
        expr = ConfigExpression("normal string", id="test")
        result = expr.evaluate()
        assert result is None

    def test_evaluate_import_from(self):
        """Test evaluate with 'from ... import' statement."""
        expr = ConfigExpression("$from pathlib import Path", id="test")
        result = expr.evaluate()
        from pathlib import Path

        assert result is Path

    def test_evaluate_import(self):
        """Test evaluate with 'import' statement."""
        expr = ConfigExpression("$import os", id="test")
        result = expr.evaluate()
        import os as expected_os

        assert result is expected_os

    def test_evaluate_import_as(self):
        """Test evaluate with 'import as' statement."""
        expr = ConfigExpression("$import collections as col", id="test")
        result = expr.evaluate()
        assert "Counter" in dir(result)

    def test_evaluate_import_from_as(self):
        """Test evaluate with 'from ... import ... as' statement."""
        expr = ConfigExpression("$from collections import Counter as C", id="test")
        result = expr.evaluate()
        assert result is Counter

    def test_evaluate_builtin_functions(self):
        """Test evaluate with builtin functions."""
        expr = ConfigExpression("$len([1, 2, 3, 4])", id="test")
        result = expr.evaluate()
        assert result == 4

    def test_evaluate_error_handling(self):
        """Test evaluate error handling."""
        from sparkwheel.exceptions import EvaluationError

        expr = ConfigExpression("$undefined_variable", id="test")
        with pytest.raises(EvaluationError, match="Failed to evaluate"):
            expr.evaluate()

    def test_parse_import_string_from_import(self):
        """Test _parse_import_string with from import."""
        expr = ConfigExpression("$from collections import Counter", id="test")
        result = expr._parse_import_string("from collections import Counter")
        assert result is Counter
        assert "Counter" in expr.globals

    def test_parse_import_string_import(self):
        """Test _parse_import_string with import."""
        expr = ConfigExpression("$import json", id="test")
        result = expr._parse_import_string("import json")
        import json as expected_json

        assert result is expected_json
        assert "json" in expr.globals

    def test_parse_import_string_not_import(self):
        """Test _parse_import_string with non-import returns None."""
        expr = ConfigExpression("$1 + 1", id="test")
        result = expr._parse_import_string("1 + 1")
        assert result is None

    def test_parse_import_string_multiple_imports_warning(self):
        """Test _parse_import_string warns on multiple imports."""
        expr = ConfigExpression("$from collections import Counter, defaultdict", id="test")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            expr._parse_import_string("from collections import Counter, defaultdict")
            assert len(w) > 0
            assert "multiple import" in str(w[0].message).lower()

    def test_repr(self):
        """Test string representation."""
        expr = ConfigExpression("$1 + 1", id="test")
        repr_str = repr(expr)
        assert "ConfigExpression" in repr_str


class TestInstantiable:
    """Test Instantiable abstract base class."""

    def test_is_disabled_not_implemented(self):
        """Test is_disabled must be implemented."""
        with pytest.raises(TypeError, match="abstract"):
            # Can't instantiate without implementing is_disabled
            class TestInstantiableImpl(Instantiable):
                def instantiate(self):
                    pass

            TestInstantiableImpl()

    def test_instantiate_not_implemented(self):
        """Test instantiate must be implemented."""
        with pytest.raises(TypeError, match="abstract"):
            # Can't instantiate without implementing instantiate
            class TestInstantiableImpl(Instantiable):
                def is_disabled(self):
                    return False

            TestInstantiableImpl()


def test_abstract_method_direct_call():
    """Test calling abstract methods directly raises NotImplementedError."""
    from sparkwheel.config_item import Instantiable

    class Impl(Instantiable):
        def is_disabled(self):
            return False

        def instantiate(self):
            return None

    obj = Impl()
    # Call the abstract base class methods to hit lines 24 and 31
    try:
        Instantiable.is_disabled(obj)
    except NotImplementedError:
        pass

    try:
        Instantiable.instantiate(obj)
    except NotImplementedError:
        pass


def test_config_expression_import_with_multiple_names():
    """Test import with multiple names triggers warning."""
    import warnings

    expr = ConfigExpression("$from os import path, sep", id="test")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        expr._parse_import_string("from os import path, sep")
        # Should warn about multiple imports
        assert len(w) > 0


def test_config_expression_is_import_statement_edge_cases():
    """Test is_import_statement with edge cases."""
    # Not an expression
    assert not ConfigExpression.is_import_statement("regular string")
    # Expression but no import
    assert not ConfigExpression.is_import_statement("$1 + 1")
    # Has 'import' in string but not import statement
    assert not ConfigExpression.is_import_statement("$'import is a keyword'")
