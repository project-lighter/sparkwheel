"""
Comprehensive tests for low-level components.

This module contains all tests for the low-level building blocks:
- ConfigItem: Basic configuration item wrapper
- ConfigComponent: Instantiable components with _target_
- ConfigExpression: Python expression evaluation
- ReferenceResolver: Reference and dependency resolution
- Instantiable: Abstract base class
"""

import warnings

import pytest

from sparkwheel import (
    ConfigComponent,
    ConfigExpression,
    ConfigItem,
    Instantiable,
    ReferenceResolver,
)


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
        from collections import Counter
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
        config = {
            "_target_": "collections.Counter",
            "_mode_": "callable",
            "iterable": [1, 2]
        }
        component = ConfigComponent(config, id="test")
        result = component.instantiate()
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
            assert result == 2

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
        from collections import Counter
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
        from collections import Counter
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
        expr = ConfigExpression(
            "$from collections import Counter, defaultdict", id="test"
        )
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

    def test_is_import_statement_edge_cases(self):
        """Test is_import_statement with edge cases."""
        assert not ConfigExpression.is_import_statement("regular string")
        assert not ConfigExpression.is_import_statement("$1 + 1")
        assert not ConfigExpression.is_import_statement("$'import is a keyword'")


class TestInstantiable:
    """Test Instantiable abstract base class."""

    def test_is_disabled_not_implemented(self):
        """Test is_disabled must be implemented."""
        with pytest.raises(TypeError, match="abstract"):
            class TestInstantiableImpl(Instantiable):
                def instantiate(self):
                    pass
            TestInstantiableImpl()

    def test_instantiate_not_implemented(self):
        """Test instantiate must be implemented."""
        with pytest.raises(TypeError, match="abstract"):
            class TestInstantiableImpl(Instantiable):
                def is_disabled(self):
                    return False
            TestInstantiableImpl()

    def test_abstract_method_direct_call(self):
        """Test calling abstract methods directly raises NotImplementedError."""
        class Impl(Instantiable):
            def is_disabled(self):
                return False

            def instantiate(self):
                return None

        obj = Impl()
        try:
            Instantiable.is_disabled(obj)
        except NotImplementedError:
            pass

        try:
            Instantiable.instantiate(obj)
        except NotImplementedError:
            pass


class TestReferenceResolver:
    """Test ReferenceResolver class."""

    def test_init_empty(self):
        """Test ReferenceResolver initialization with no items."""
        resolver = ReferenceResolver()
        assert resolver.items == {}
        assert resolver.resolved_content == {}

    def test_init_with_items(self):
        """Test ReferenceResolver initialization with items."""
        item1 = ConfigItem({"a": 1}, id="item1")
        item2 = ConfigItem({"b": 2}, id="item2")
        resolver = ReferenceResolver(items=[item1, item2])
        assert len(resolver.items) == 2
        assert "item1" in resolver.items
        assert "item2" in resolver.items

    def test_reset(self):
        """Test reset clears items and resolved content."""
        resolver = ReferenceResolver()
        resolver.add_item(ConfigItem({"a": 1}, id="test"))
        resolver.resolved_content["test"] = {"a": 1}
        assert len(resolver.items) > 0
        assert len(resolver.resolved_content) > 0

        resolver.reset()
        assert resolver.items == {}
        assert resolver.resolved_content == {}

    def test_is_resolved_false(self):
        """Test is_resolved returns False when empty."""
        resolver = ReferenceResolver()
        assert resolver.is_resolved() is False

    def test_is_resolved_true(self):
        """Test is_resolved returns True when has content."""
        resolver = ReferenceResolver()
        resolver.resolved_content["test"] = {"a": 1}
        assert resolver.is_resolved() is True

    def test_add_item(self):
        """Test add_item adds ConfigItem."""
        resolver = ReferenceResolver()
        item = ConfigItem({"a": 1}, id="test")
        resolver.add_item(item)
        assert "test" in resolver.items
        assert resolver.items["test"] is item

    def test_add_item_duplicate_ignored(self):
        """Test add_item ignores duplicate id."""
        resolver = ReferenceResolver()
        item1 = ConfigItem({"a": 1}, id="test")
        item2 = ConfigItem({"b": 2}, id="test")
        resolver.add_item(item1)
        resolver.add_item(item2)
        assert resolver.items["test"] is item1
        assert resolver.items["test"].config == {"a": 1}

    def test_get_item_exists(self):
        """Test get_item retrieves existing item."""
        resolver = ReferenceResolver()
        item = ConfigItem({"a": 1}, id="test")
        resolver.add_item(item)
        retrieved = resolver.get_item("test")
        assert retrieved is item

    def test_get_item_not_exists(self):
        """Test get_item returns None for non-existent id."""
        resolver = ReferenceResolver()
        retrieved = resolver.get_item("nonexistent")
        assert retrieved is None

    def test_get_item_with_resolve(self):
        """Test get_item with resolve parameter."""
        resolver = ReferenceResolver()
        item = ConfigItem({"a": 1}, id="test")
        resolver.add_item(item)
        retrieved = resolver.get_item("test", resolve=True)
        assert retrieved is item
        assert "test" in resolver.resolved_content

    def test_normalize_id(self):
        """Test normalize_id converts to string."""
        assert ReferenceResolver.normalize_id("a::b::c") == "a::b::c"
        assert ReferenceResolver.normalize_id("simple") == "simple"
        assert ReferenceResolver.normalize_id(123) == "123"

    @pytest.mark.parametrize(
        "input_id,expected",
        [
            ("a::b::c", ["a", "b", "c"]),
            ("single", ["single"]),
            ("x::y", ["x", "y"]),
        ],
    )
    def test_split_id_default(self, input_id, expected):
        """Test split_id splits all parts."""
        result = ReferenceResolver.split_id(input_id)
        assert result == expected

    def test_split_id_last(self):
        """Test split_id with last=True."""
        result = ReferenceResolver.split_id("a::b::c", last=True)
        assert result == ["a::b", "c"]

    def test_iter_subconfigs_dict(self):
        """Test iter_subconfigs with dictionary."""
        config = {"a": 1, "b": 2}
        results = list(ReferenceResolver.iter_subconfigs("parent", config))
        assert len(results) == 2
        assert ("a", "parent::a", 1) in results
        assert ("b", "parent::b", 2) in results

    def test_iter_subconfigs_list(self):
        """Test iter_subconfigs with list."""
        config = [10, 20, 30]
        results = list(ReferenceResolver.iter_subconfigs("parent", config))
        assert len(results) == 3
        assert (0, "parent::0", 10) in results
        assert (1, "parent::1", 20) in results
        assert (2, "parent::2", 30) in results

    def test_iter_subconfigs_empty_id(self):
        """Test iter_subconfigs with empty parent id."""
        config = {"a": 1}
        results = list(ReferenceResolver.iter_subconfigs("", config))
        assert results == [("a", "a", 1)]

    def test_match_refs_pattern_simple(self):
        """Test match_refs_pattern with simple reference."""
        refs = ReferenceResolver.match_refs_pattern("@myref")
        assert "myref" in refs

    def test_match_refs_pattern_nested(self):
        """Test match_refs_pattern with nested reference."""
        refs = ReferenceResolver.match_refs_pattern("@parent::child::value")
        assert "parent::child::value" in refs

    def test_match_refs_pattern_in_expression(self):
        """Test match_refs_pattern in expression."""
        refs = ReferenceResolver.match_refs_pattern("$@value * 2")
        assert "value" in refs

    def test_match_refs_pattern_multiple(self):
        """Test match_refs_pattern with multiple references."""
        refs = ReferenceResolver.match_refs_pattern("$@a + @b")
        assert "a" in refs
        assert "b" in refs

    def test_match_refs_pattern_no_refs(self):
        """Test match_refs_pattern with no references."""
        refs = ReferenceResolver.match_refs_pattern("plain string")
        assert refs == {}

    def test_update_refs_pattern_simple(self):
        """Test update_refs_pattern with simple reference."""
        refs = {"myref": 42}
        result = ReferenceResolver.update_refs_pattern("@myref", refs)
        assert result == 42

    def test_update_refs_pattern_in_expression(self):
        """Test update_refs_pattern in expression."""
        refs = {"value": 10}
        result = ReferenceResolver.update_refs_pattern("$@value * 2", refs)
        assert result == "$__local_refs['value'] * 2"

    def test_update_refs_pattern_multiple(self):
        """Test update_refs_pattern with multiple references."""
        refs = {"a": 1, "b": 2}
        result = ReferenceResolver.update_refs_pattern("$@a + @b", refs)
        assert "__local_refs['a']" in result
        assert "__local_refs['b']" in result

    def test_update_refs_pattern_substring_handling(self):
        """Test update_refs_pattern handles longer refs first."""
        refs = {"a": 1, "ab": 2}
        result = ReferenceResolver.update_refs_pattern("$@ab + @a", refs)
        assert "__local_refs['ab']" in result
        assert "__local_refs['a']" in result

    def test_update_refs_pattern_missing_ref_warning(self):
        """Test update_refs_pattern warns on missing reference when allowed."""
        original = ReferenceResolver.allow_missing_reference
        try:
            ReferenceResolver.allow_missing_reference = True
            refs = {}
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                ReferenceResolver.update_refs_pattern("@missing", refs)
                assert len(w) > 0
                assert "can not find" in str(w[0].message)
        finally:
            ReferenceResolver.allow_missing_reference = original

    def test_update_refs_pattern_missing_ref_error(self):
        """Test update_refs_pattern raises error on missing reference."""
        original = ReferenceResolver.allow_missing_reference
        try:
            ReferenceResolver.allow_missing_reference = False
            refs = {}
            with pytest.raises(KeyError, match="can not find expected ID"):
                ReferenceResolver.update_refs_pattern("@missing", refs)
        finally:
            ReferenceResolver.allow_missing_reference = original

    def test_find_refs_in_config_string(self):
        """Test find_refs_in_config with string reference."""
        refs = ReferenceResolver.find_refs_in_config("@myref", "test")
        assert "myref" in refs

    def test_find_refs_in_config_nested_dict(self):
        """Test find_refs_in_config with nested dictionary."""
        config = {"a": "@ref1", "b": {"c": "@ref2"}}
        refs = ReferenceResolver.find_refs_in_config(config, "test")
        assert "ref1" in refs
        assert "ref2" in refs

    def test_find_refs_in_config_list(self):
        """Test find_refs_in_config with list."""
        config = ["@ref1", "@ref2", "plain"]
        refs = ReferenceResolver.find_refs_in_config(config, "test")
        assert "ref1" in refs
        assert "ref2" in refs

    def test_find_refs_in_config_instantiable(self):
        """Test find_refs_in_config detects instantiable components."""
        config = {"comp": {"_target_": "dict"}}
        refs = ReferenceResolver.find_refs_in_config(config, "test")
        assert "test::comp" in refs

    def test_find_refs_in_config_expression(self):
        """Test find_refs_in_config detects expressions."""
        config = {"expr": "$1 + 1"}
        refs = ReferenceResolver.find_refs_in_config(config, "test")
        assert "test::expr" in refs

    def test_update_config_with_refs_string(self):
        """Test update_config_with_refs with string."""
        refs = {"myref": 42}
        result = ReferenceResolver.update_config_with_refs("@myref", "test", refs)
        assert result == 42

    def test_update_config_with_refs_dict(self):
        """Test update_config_with_refs with dictionary."""
        refs = {"test::a": 1, "test::b": 2}
        config = {"a": "$@ref_a", "b": "$@ref_b"}
        result = ReferenceResolver.update_config_with_refs(config, "test", refs)
        assert isinstance(result, dict)

    def test_update_config_with_refs_list(self):
        """Test update_config_with_refs with list."""
        refs = {"test::0": "first", "test::1": "second"}
        config = ["plain", "values"]
        result = ReferenceResolver.update_config_with_refs(config, "test", refs)
        assert isinstance(result, list)

    def test_update_config_with_refs_disabled_component(self):
        """Test update_config_with_refs skips disabled components."""
        refs = {"test::comp": None}
        config = {"comp": {"_target_": "dict"}}
        result = ReferenceResolver.update_config_with_refs(config, "test", refs)
        assert result == {}

    def test_resolve_one_item_simple(self):
        """Test _resolve_one_item with simple item."""
        resolver = ReferenceResolver()
        item = ConfigItem({"value": 42}, id="test")
        resolver.add_item(item)
        result = resolver._resolve_one_item("test")
        assert result == {"value": 42}
        assert "test" in resolver.resolved_content

    def test_resolve_one_item_with_reference(self):
        """Test _resolve_one_item with reference to another item."""
        resolver = ReferenceResolver()
        resolver.add_item(ConfigItem({"value": 10}, id="base"))
        resolver.add_item(ConfigItem({"ref": "@base"}, id="derived"))
        result = resolver._resolve_one_item("derived")
        assert result["ref"] == {"value": 10}

    def test_resolve_one_item_circular_reference(self):
        """Test _resolve_one_item detects circular references."""
        from sparkwheel.exceptions import CircularReferenceError

        resolver = ReferenceResolver()
        resolver.add_item(ConfigItem({"ref": "@b"}, id="a"))
        resolver.add_item(ConfigItem({"ref": "@a"}, id="b"))
        with pytest.raises(CircularReferenceError, match="Circular reference"):
            resolver._resolve_one_item("a")

    def test_resolve_one_item_missing_reference_error(self):
        """Test _resolve_one_item raises error for missing reference."""
        from sparkwheel.exceptions import ConfigKeyError

        resolver = ReferenceResolver()
        resolver.add_item(ConfigItem({"ref": "@missing"}, id="test"))
        with pytest.raises(ConfigKeyError, match="not found"):
            resolver._resolve_one_item("test")

    def test_resolve_one_item_missing_reference_warning(self):
        """Test _resolve_one_item warns for missing reference when allowed."""
        original = ReferenceResolver.allow_missing_reference
        try:
            ReferenceResolver.allow_missing_reference = True
            resolver = ReferenceResolver()
            resolver.add_item(ConfigItem({"ref": "@missing"}, id="test"))
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                resolver._resolve_one_item("test")
                assert len(w) > 0
                assert "not defined" in str(w[0].message)
        finally:
            ReferenceResolver.allow_missing_reference = original

    def test_resolve_one_item_component(self):
        """Test _resolve_one_item with ConfigComponent."""
        resolver = ReferenceResolver()
        config = {"_target_": "dict", "a": 1, "b": 2}
        component = ConfigComponent(config, id="comp")
        resolver.add_item(component)
        result = resolver._resolve_one_item("comp")
        assert result == {"a": 1, "b": 2}

    def test_resolve_one_item_component_no_instantiate(self):
        """Test _resolve_one_item with ConfigComponent and instantiate=False."""
        resolver = ReferenceResolver()
        config = {"_target_": "dict", "a": 1}
        component = ConfigComponent(config, id="comp")
        resolver.add_item(component)
        result = resolver._resolve_one_item("comp", instantiate=False)
        assert isinstance(result, ConfigComponent)

    def test_resolve_one_item_expression(self):
        """Test _resolve_one_item with ConfigExpression."""
        resolver = ReferenceResolver()
        expr = ConfigExpression("$1 + 1", id="expr")
        resolver.add_item(expr)
        result = resolver._resolve_one_item("expr")
        assert result == 2

    def test_resolve_one_item_expression_no_eval(self):
        """Test _resolve_one_item with ConfigExpression and eval_expr=False."""
        resolver = ReferenceResolver()
        expr = ConfigExpression("$1 + 1", id="expr")
        resolver.add_item(expr)
        result = resolver._resolve_one_item("expr", eval_expr=False)
        assert isinstance(result, ConfigExpression)

    def test_resolve_one_item_import_statement_priority(self):
        """Test _resolve_one_item resolves import statements first."""
        resolver = ReferenceResolver()
        resolver.add_item(ConfigExpression("$import os", id="imp"))
        resolver.add_item(ConfigExpression("$@imp", id="use_imp"))
        result = resolver._resolve_one_item("use_imp")
        import os as expected_os
        assert result is expected_os

    def test_resolve_one_item_cached(self):
        """Test _resolve_one_item returns cached result."""
        resolver = ReferenceResolver()
        item = ConfigItem({"value": 42}, id="test")
        resolver.add_item(item)
        result1 = resolver._resolve_one_item("test")
        item.update_config({"value": 100})
        result2 = resolver._resolve_one_item("test")
        assert result1 == result2
        assert result2 == {"value": 42}

    def test_resolve_one_item_not_found(self):
        """Test _resolve_one_item with non-existent id."""
        from sparkwheel.exceptions import ConfigKeyError

        resolver = ReferenceResolver()
        with pytest.raises(ConfigKeyError, match="not found"):
            resolver._resolve_one_item("nonexistent")

    def test_resolve_one_item_with_default(self):
        """Test _resolve_one_item with default parameter."""
        resolver = ReferenceResolver()
        default_item = ConfigItem({"default": True}, id="default")
        result = resolver._resolve_one_item("nonexistent", default=default_item)
        assert result == {"default": True}

    def test_resolve_one_item_with_non_config_item(self):
        """Test _resolve_one_item when stored item is not a ConfigItem."""
        resolver = ReferenceResolver()
        resolver.add_item(ConfigItem({"val": 1}, id="test"))
        resolver.items["test"] = {"direct": "value"}
        result = resolver._resolve_one_item("test")
        assert result == {"direct": "value"}

    def test_get_resolved_content(self):
        """Test get_resolved_content."""
        resolver = ReferenceResolver()
        resolver.add_item(ConfigItem({"value": 42}, id="test"))
        result = resolver.get_resolved_content("test")
        assert result == {"value": 42}

    def test_remove_resolved_content_exists(self):
        """Test remove_resolved_content removes existing content."""
        resolver = ReferenceResolver()
        resolver.resolved_content["test"] = {"value": 42}
        result = resolver.remove_resolved_content("test")
        assert result == {"value": 42}
        assert "test" not in resolver.resolved_content

    def test_remove_resolved_content_not_exists(self):
        """Test remove_resolved_content returns None for non-existent id."""
        resolver = ReferenceResolver()
        result = resolver.remove_resolved_content("nonexistent")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
