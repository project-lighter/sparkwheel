"""Comprehensive tests for operators module.

This module tests the operators.py module functionality:
- MergeContext class and location tracking
- Operator validation (_validate_delete_operator)
- apply_operators function with all edge cases
"""

import pytest

from sparkwheel.locations import LocationRegistry
from sparkwheel.operators import MergeContext, _validate_delete_operator, apply_operators, validate_operators
from sparkwheel.utils.exceptions import ConfigMergeError, Location


class TestMergeContext:
    """Test MergeContext class for tracking merge operations."""

    def test_child_path_empty_base(self):
        """Test creating child path from empty base."""
        ctx = MergeContext()
        child = ctx.child_path("model")
        assert child.current_path == "model"

    def test_child_path_with_base(self):
        """Test creating child path with existing base."""
        ctx = MergeContext(current_path="model")
        child = ctx.child_path("optimizer")
        assert child.current_path == "model::optimizer"

    def test_child_path_nested(self):
        """Test creating deeply nested child paths."""
        ctx = MergeContext()
        child1 = ctx.child_path("model")
        child2 = child1.child_path("optimizer")
        child3 = child2.child_path("lr")
        assert child3.current_path == "model::optimizer::lr"

    def test_get_source_location_no_registry(self):
        """Test get_source_location returns None when no registry."""
        ctx = MergeContext()
        location = ctx.get_source_location("key")
        assert location is None

    def test_get_source_location_with_registry(self):
        """Test get_source_location with registry."""
        registry = LocationRegistry()
        test_location = Location(filepath="config.yaml", line=10)
        registry.register("model::lr", test_location)

        ctx = MergeContext(locations=registry, current_path="model")
        location = ctx.get_source_location("lr")
        assert location == test_location

    def test_get_source_location_with_remove_operator(self):
        """Test get_source_location strips ~ operator prefix."""
        registry = LocationRegistry()
        test_location = Location(filepath="config.yaml", line=10)
        registry.register("model::lr", test_location)

        ctx = MergeContext(locations=registry, current_path="model")
        # Should strip ~ and find "lr"
        location = ctx.get_source_location("~lr")
        assert location == test_location

    def test_get_source_location_with_replace_operator(self):
        """Test get_source_location strips = operator prefix."""
        registry = LocationRegistry()
        test_location = Location(filepath="config.yaml", line=10)
        registry.register("model::lr", test_location)

        ctx = MergeContext(locations=registry, current_path="model")
        # Should strip = and find "lr"
        location = ctx.get_source_location("=lr")
        assert location == test_location

    def test_get_source_location_operator_key_takes_precedence(self):
        """Test that exact operator key match takes precedence."""
        registry = LocationRegistry()
        exact_location = Location(filepath="config.yaml", line=5)
        fallback_location = Location(filepath="config.yaml", line=10)

        # Register both ~lr and lr
        registry.register("model::~lr", exact_location)
        registry.register("model::lr", fallback_location)

        ctx = MergeContext(locations=registry, current_path="model")
        # Should find exact match first
        location = ctx.get_source_location("~lr")
        assert location == exact_location

    def test_get_source_location_not_found(self):
        """Test get_source_location returns None for missing keys."""
        registry = LocationRegistry()
        ctx = MergeContext(locations=registry, current_path="model")
        location = ctx.get_source_location("missing_key")
        assert location is None

    def test_get_source_location_empty_path(self):
        """Test get_source_location with empty current path."""
        registry = LocationRegistry()
        test_location = Location(filepath="config.yaml", line=10)
        registry.register("lr", test_location)

        ctx = MergeContext(locations=registry, current_path="")
        location = ctx.get_source_location("lr")
        assert location == test_location

    def test_get_source_location_operator_key_not_found(self):
        """Test get_source_location returns None when operator key not found."""
        registry = LocationRegistry()
        # Register only "other", not "lr" or "~lr"
        test_location = Location(filepath="config.yaml", line=10)
        registry.register("model::other", test_location)

        ctx = MergeContext(locations=registry, current_path="model")
        # Should not find ~lr or lr
        location = ctx.get_source_location("~lr")
        assert location is None

    def test_get_source_location_regular_key_not_found(self):
        """Test get_source_location returns None for regular key not found."""
        registry = LocationRegistry()
        test_location = Location(filepath="config.yaml", line=10)
        registry.register("model::other", test_location)

        ctx = MergeContext(locations=registry, current_path="model")
        # Should not find "missing" (regular key, no operator)
        location = ctx.get_source_location("missing")
        assert location is None


class TestValidateDeleteOperator:
    """Test _validate_delete_operator function."""

    def test_valid_null_value(self):
        """Test that null value is valid."""
        _validate_delete_operator("key", None)  # Should not raise

    def test_valid_empty_string(self):
        """Test that empty string is valid."""
        _validate_delete_operator("key", "")  # Should not raise

    def test_valid_list_value(self):
        """Test that list value is valid."""
        _validate_delete_operator("key", [0, 1, 2])  # Should not raise

    def test_invalid_string_value(self):
        """Test that non-empty string value raises error."""
        with pytest.raises(ConfigMergeError, match="must have null, empty, or list value"):
            _validate_delete_operator("key", "invalid")

    def test_invalid_dict_value(self):
        """Test that dict value raises error."""
        with pytest.raises(ConfigMergeError, match="must have null, empty, or list value"):
            _validate_delete_operator("key", {"nested": "value"})

    def test_invalid_int_value(self):
        """Test that int value raises error."""
        with pytest.raises(ConfigMergeError, match="must have null, empty, or list value"):
            _validate_delete_operator("key", 123)

    def test_empty_list_raises_error(self):
        """Test that empty list raises error."""
        with pytest.raises(ConfigMergeError, match="cannot be empty"):
            _validate_delete_operator("key", [])


class TestValidateOperators:
    """Test validate_operators function."""

    def test_validate_non_dict_config(self):
        """Test that non-dict config is handled gracefully."""
        # Should not raise for non-dict
        validate_operators("not a dict")  # type: ignore[arg-type]
        validate_operators(123)  # type: ignore[arg-type]
        validate_operators(None)  # type: ignore[arg-type]

    def test_validate_remove_operator(self):
        """Test validation of remove operator."""
        config = {"~key": None}
        validate_operators(config)  # Should not raise

    def test_validate_remove_operator_invalid_value(self):
        """Test validation catches invalid remove operator value."""
        config = {"~key": "invalid"}
        with pytest.raises(ConfigMergeError, match="must have null, empty, or list value"):
            validate_operators(config)

    def test_validate_replace_operator(self):
        """Test validation of replace operator."""
        config = {"=key": "value"}
        validate_operators(config)  # Should not raise

    def test_validate_nested_remove_operator(self):
        """Test validation of nested remove operator."""
        config = {"model": {"~lr": None}}
        validate_operators(config)  # Should not raise

    def test_validate_nested_remove_operator_invalid(self):
        """Test validation catches invalid nested remove operator."""
        config = {"model": {"~lr": 123}}
        with pytest.raises(ConfigMergeError, match="must have null, empty, or list value"):
            validate_operators(config)

    def test_validate_skips_dict_under_remove(self):
        """Test that validation doesn't recurse into remove operator dicts."""
        # This should be valid - the dict under ~key won't be recursed into
        config = {"~key": {"nested": "value"}}
        # This should raise because dict is invalid for remove operator
        with pytest.raises(ConfigMergeError, match="must have null, empty, or list value"):
            validate_operators(config)


class TestApplyOperatorsEdgeCases:
    """Test edge cases in apply_operators function."""

    def test_non_dict_base_returns_override(self):
        """Test that non-dict base returns deepcopy of override."""
        result = apply_operators("not a dict", {"key": "value"})  # type: ignore[arg-type]
        assert result == {"key": "value"}

    def test_non_dict_override_returns_override(self):
        """Test that non-dict override returns deepcopy of override."""
        result = apply_operators({"key": "value"}, "not a dict")  # type: ignore[arg-type]
        assert result == "not a dict"

    def test_both_non_dict_returns_override(self):
        """Test that both non-dict returns override."""
        result = apply_operators("base", "override")  # type: ignore[arg-type]
        assert result == "override"

    def test_non_string_key_copied_directly(self):
        """Test that non-string keys are copied directly."""
        base = {}
        override = {123: "numeric_key"}  # type: ignore[dict-item]
        result = apply_operators(base, override)
        assert result[123] == "numeric_key"  # type: ignore[index]

    def test_context_propagates_to_nested_merges(self):
        """Test that context is properly propagated in nested merges."""
        registry = LocationRegistry()
        ctx = MergeContext(locations=registry)

        base = {"model": {"lr": 0.001}}
        override = {"model": {"dropout": 0.1}}

        result = apply_operators(base, override, context=ctx)
        assert result == {"model": {"lr": 0.001, "dropout": 0.1}}

    def test_delete_with_context_location_tracking(self):
        """Test that delete operator uses context for error messages."""
        registry = LocationRegistry()
        test_location = Location(filepath="config.yaml", line=10)
        registry.register("~missing", test_location)

        ctx = MergeContext(locations=registry)

        base = {"existing": "value"}
        override = {"~missing": None}

        with pytest.raises(ConfigMergeError, match="Cannot delete key 'missing'"):
            apply_operators(base, override, context=ctx)

    def test_delete_list_items_no_context(self):
        """Test delete list items works without context."""
        base = {"items": [1, 2, 3, 4, 5]}
        override = {"~items": [0, 2, 4]}
        result = apply_operators(base, override)
        assert result == {"items": [2, 4]}

    def test_delete_dict_keys_with_context(self):
        """Test delete dict keys with context for better error messages."""
        registry = LocationRegistry()
        test_location = Location(filepath="config.yaml", line=10)
        registry.register("~model", test_location)

        ctx = MergeContext(locations=registry)

        base = {"model": {"lr": 0.001, "dropout": 0.1}}
        override = {"~model": ["missing_key"]}

        with pytest.raises(ConfigMergeError, match="Cannot remove non-existent key 'missing_key'"):
            apply_operators(base, override, context=ctx)

    def test_replace_operator_with_none_value(self):
        """Test replace operator can set value to None."""
        base = {"key": "value"}
        override = {"=key": None}
        result = apply_operators(base, override)
        assert result == {"key": None}

    def test_composition_list_extend_preserves_order(self):
        """Test that list composition preserves order."""
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5, 6]}
        result = apply_operators(base, override)
        assert result == {"items": [1, 2, 3, 4, 5, 6]}

    def test_composition_dict_merge_deep(self):
        """Test that dict composition merges deeply."""
        base = {"model": {"optimizer": {"lr": 0.001, "momentum": 0.9}}}
        override = {"model": {"optimizer": {"lr": 0.01}}}
        result = apply_operators(base, override)
        assert result == {"model": {"optimizer": {"lr": 0.01, "momentum": 0.9}}}

    def test_scalar_replacement_on_type_mismatch(self):
        """Test that type mismatches cause replacement."""
        base = {"value": [1, 2, 3]}
        override = {"value": "string"}
        result = apply_operators(base, override)
        assert result == {"value": "string"}

    def test_new_key_addition(self):
        """Test adding new keys to config."""
        base = {"existing": "value"}
        override = {"new_key": "new_value"}
        result = apply_operators(base, override)
        assert result == {"existing": "value", "new_key": "new_value"}

    def test_delete_list_negative_indices_normalized(self):
        """Test that negative indices are properly normalized."""
        base = {"items": [1, 2, 3, 4, 5]}
        override = {"~items": [-1, -2]}  # Remove last two items
        result = apply_operators(base, override)
        assert result == {"items": [1, 2, 3]}

    def test_delete_list_duplicate_indices_handled(self):
        """Test that duplicate indices are handled correctly."""
        base = {"items": [1, 2, 3, 4, 5]}
        override = {"~items": [1, 1, 1]}  # Duplicate index
        result = apply_operators(base, override)
        assert result == {"items": [1, 3, 4, 5]}  # Only removed once

    def test_delete_items_errors_on_scalar(self):
        """Test that deleting items from scalar raises error."""
        base = {"value": "scalar"}
        override = {"~value": [0]}

        with pytest.raises(ConfigMergeError, match="expected list or dict"):
            apply_operators(base, override)

    def test_multiple_operators_in_one_override(self):
        """Test multiple operators in single override dict."""
        base = {"a": 1, "b": 2, "c": 3, "d": {"x": 1, "y": 2}}
        override = {
            "a": 10,  # Compose (replace scalar)
            "=b": 20,  # Explicit replace
            "~c": None,  # Delete
            "d": {"x": 10},  # Compose dict (merge)
        }
        result = apply_operators(base, override)
        assert result == {"a": 10, "b": 20, "d": {"x": 10, "y": 2}}


class TestApplyOperatorsDeepCopy:
    """Test that apply_operators properly deep copies values."""

    def test_base_not_mutated(self):
        """Test that base dict is not mutated."""
        base = {"model": {"lr": 0.001}}
        override = {"model": {"dropout": 0.1}}
        result = apply_operators(base, override)

        # Modify result
        result["model"]["lr"] = 0.01

        # Base should be unchanged
        assert base["model"]["lr"] == 0.001

    def test_override_not_mutated(self):
        """Test that override dict is not mutated."""
        base = {"model": {"lr": 0.001}}
        override = {"model": {"dropout": 0.1}}
        result = apply_operators(base, override)

        # Modify result
        result["model"]["dropout"] = 0.5

        # Override should be unchanged
        assert override["model"]["dropout"] == 0.1

    def test_result_is_independent(self):
        """Test that result is independent of base and override."""
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = apply_operators(base, override)

        # Modify result
        result["items"].append(6)

        # Base and override should be unchanged
        assert base["items"] == [1, 2, 3]
        assert override["items"] == [4, 5]
        assert result["items"] == [1, 2, 3, 4, 5, 6]
