"""
Comprehensive tests for Config.

This module contains all tests for the Config class, organized by functionality:
- Basic operations (get/set, contains, iteration)
- Reference resolution
- Expression evaluation
- Macro expansion
- Component instantiation
- File I/O operations
- Merging with composition-by-default and =/~ operators
- Advanced features (lazy parsing, relative IDs, etc.)
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from sparkwheel import Config, apply_operators
from sparkwheel.path_utils import resolve_relative_ids, split_file_and_id


class TestConfigBasics:
    """Test basic Config operations."""

    def test_basic_config(self):
        """Test basic configuration parsing."""
        config = {"key1": "value1", "key2": 42}
        config_obj = Config()
        config_obj._data = config
        parser = config_obj
        assert parser["key1"] == "value1"
        assert parser["key2"] == 42

    def test_set_and_get(self):
        """Test setting and getting config values."""
        config = {}
        config_obj = Config()
        config_obj._data = config
        parser = config_obj
        parser["new_key"] = "new_value"
        assert parser["new_key"] == "new_value"

    def test_nested_set(self):
        """Test setting nested config values."""
        config = {"level1": {}}
        config_obj = Config()
        config_obj._data = config
        parser = config_obj
        parser["level1::level2"] = "nested_value"
        assert parser["level1"]["level2"] == "nested_value"

    def test_nested_set_creates_paths(self):
        """Test that __setitem__ creates missing paths."""
        parser = Config().update({})
        parser["model::lr"] = 0.001
        assert parser["model"]["lr"] == 0.001

        parser["model::nested::deep::value"] = 42
        assert parser["model"]["nested"]["deep"]["value"] == 42

    def test_contains(self):
        """Test __contains__ method."""
        config = {"exists": True}
        config_obj = Config()
        config_obj._data = config
        parser = config_obj
        assert "exists" in parser
        assert "not_exists" not in parser

    def test_contains_nested(self):
        """Test __contains__ with nested path."""
        parser = Config({"a": {"b": {"c": 1}}})
        assert "a" in parser
        assert "a::b" in parser
        assert "a::b::c" in parser
        assert "a::b::d" not in parser

    def test_get_with_default(self):
        """Test get method with default."""
        parser = Config({"existing": "value"})
        assert parser.get("existing") == "value"
        assert parser.get("missing", "default") == "default"

    def test_get_invalid_key_default(self):
        """Test get returns default for invalid key."""
        parser = Config({"a": {"b": 1}})
        assert parser.get("a::b::c", "default") == "default"

    def test_setitem_empty_id(self):
        """Test __setitem__ with empty id."""
        parser = Config({"old": "config"})
        parser[""] = {"new": "config"}
        assert parser.get() == {"new": "config"}

    def test_merge_nested_paths(self):
        """Test merge method with nested paths."""
        parser = Config({"a": 1, "b": {"c": 2}})
        parser.update({"a": 10, "b::c": 20, "d": 30})
        assert parser["a"] == 10
        assert parser["b::c"] == 20
        assert parser["d"] == 30

    def test_getitem_invalid_config_type(self):
        """Test __getitem__ raises error for invalid config type."""
        parser = Config({"scalar": 42})
        with pytest.raises(ValueError, match="Config must be dict or list"):
            _ = parser["scalar::invalid"]

    def test_getitem_list_indexing(self):
        """Test __getitem__ with list indexing."""
        parser = Config({"items": [10, 20, 30]})
        assert parser["items::0"] == 10
        assert parser["items::1"] == 20
        assert parser["items::2"] == 30

    def test_setitem_list_indexing(self):
        """Test __setitem__ with list indexing."""
        parser = Config({"items": [10, 20, 30]})
        parser["items::1"] = 99
        assert parser["items::1"] == 99

    def test_repr(self):
        """Test Config __repr__."""
        parser = Config({"key": "value"})
        repr_str = repr(parser)
        assert "key" in repr_str

    def test_init_with_none(self):
        """Test Config init with None."""
        parser = Config(None)
        assert isinstance(parser._data, dict)
        assert parser._data == {}

    def test_init_with_globals_dict(self):
        """Test Config init with globals dict."""
        parser = Config({}, globals={"pd": "pandas"})
        assert "pd" in parser._globals

    def test_init_with_globals_callable(self):
        """Test Config init with globals containing callables."""
        from collections import Counter

        parser = Config({}, globals={"Counter": Counter})
        assert parser._globals["Counter"] is Counter


class TestConfigReferences:
    """Test reference resolution."""

    def test_simple_reference(self):
        """Test simple reference resolution."""
        config = {"value": 10, "reference": "@value"}
        parser = Config().update(config)
        result = parser.resolve("reference")
        assert result == 10

    def test_nested_reference(self):
        """Test nested reference with ::."""
        config = {"nested": {"value": 100}, "ref": "@nested::value"}
        parser = Config().update(config)
        result = parser.resolve("ref")
        assert result == 100

    def test_complex_nested_reference(self):
        """Test complex nested reference resolution."""
        config = {"data": {"values": [1, 2, 3], "metadata": {"count": "$len(@data::values)"}}, "ref": "@data::metadata::count"}
        config_obj = Config()
        config_obj._data = config
        parser = config_obj
        parser._parse()
        result = parser.resolve("ref")
        assert result == 3

    def test_multiple_references(self):
        """Test multiple references in one expression."""
        config = {"a": 10, "b": 20, "sum": "$@a + @b"}
        parser = Config().update(config)
        result = parser.resolve("sum")
        assert result == 30

    def test_resolve_relative_ids(self):
        """Test resolve_relative_ids method."""
        result = resolve_relative_ids("parent::child", "@::sibling")
        assert result == "@parent::sibling"

    def test_resolve_relative_ids_double_colon(self):
        """Test resolve_relative_ids with :: (up one level)."""
        result = resolve_relative_ids("parent::child", "@::::value")
        assert result == "@value"

    def test_resolve_relative_ids_triple_colon(self):
        """Test resolve_relative_ids with :::: (up two levels)."""
        result = resolve_relative_ids("a::b::c", "@::::::value")
        assert result == "@value"

    def test_resolve_relative_ids_equal_levels(self):
        """Test resolve_relative_ids when going up equals depth."""
        result = resolve_relative_ids("a::b", "@::::value")
        assert result == "@value"

    def test_resolve_relative_ids_out_of_range(self):
        """Test resolve_relative_ids raises error when out of range."""
        with pytest.raises(ValueError, match="attempts to go"):
            resolve_relative_ids("a", "@::::value")

    def test_resolve_relative_ids_macro(self):
        """Test resolve_relative_ids with macro %."""
        result = resolve_relative_ids("parent::child", "%::sibling")
        assert result == "%parent::sibling"

    def test_resolve_relative_ids_in_list(self):
        """Test resolve_relative_ids in list context."""
        result = resolve_relative_ids("parent::items::1", "@::0")
        assert result == "@parent::items::0"


class TestExpressions:
    """Test expression evaluation."""

    def test_simple_expression(self):
        """Test simple expression evaluation."""
        config = {"base": 5, "computed": "$@base * 2"}
        parser = Config().update(config)
        result = parser.resolve("computed")
        assert result == 10

    def test_expression_with_builtin(self):
        """Test expression using Python builtins."""
        config = {"items": [1, 2, 3, 4, 5], "count": "$len(@items)"}
        parser = Config().update(config)
        result = parser.resolve("count")
        assert result == 5

    def test_expression_with_reference_to_component(self):
        """Test expression referencing an instantiated component."""
        config = {"mydict": {"_target_": "dict", "a": 1, "b": 2}, "value": "$@mydict['a']"}
        config_obj = Config()
        config_obj._data = config
        parser = config_obj
        parser._parse()
        result = parser.resolve("value")
        assert result == 1


class TestConfigMacros:
    """Test macro expansion."""

    def test_basic_macro(self):
        """Test basic macro expansion with %."""
        config = {"original": {"a": 1, "b": 2}, "copy": "%original"}
        parser = Config().update(config)
        parser.resolve()
        assert parser["copy"] == {"a": 1, "b": 2}
        assert parser["copy"] is not parser["original"]

    def test_do_resolve_macro_from_config(self):
        """Test preprocessing with macro referencing same config."""
        parser = Config({"template": {"a": 1, "b": 2}, "copy": "%template"})
        parser._parse()
        assert parser["copy"] == {"a": 1, "b": 2}
        parser["copy"]["a"] = 99
        assert parser["template"]["a"] == 1

    def test_do_resolve_macro_load(self):
        """Test preprocessing with macro from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"external": {"value": 42}}, f)
            filepath = f.name

        try:
            parser = Config({"local": f"%{filepath}::external"})
            parser._parse()
            assert parser["local"] == {"value": 42}
        finally:
            Path(filepath).unlink()

    def test_eager_raw_reference_expansion(self):
        """Test that raw references are expanded during update(), not resolve()."""
        config = {"original": {"a": 1, "b": 2}, "copy": "%original"}
        parser = Config().update(config)

        # After update(), raw references should be expanded (not resolve() yet!)
        # The copy should be the actual value, not the "%original" string
        assert parser.get("copy") == {"a": 1, "b": 2}
        assert parser.get("copy") is not parser.get("original")  # Deep copy

        # Verify it's a real copy by modifying it
        parser.set("copy::c", 3)
        assert parser.get("copy::c") == 3
        assert "c" not in parser.get("original")

    def test_pruning_with_raw_references(self):
        """Test that pruning works with raw references (the Lighter use case)."""
        # This is the critical test: raw refs should be expanded before pruning
        config = {
            "system": {
                "dataloaders": {
                    "train": {"batch_size": 32},
                    "val": {"batch_size": 64},
                }
            },
            "train": {
                "dataloader": "%system::dataloaders::train"  # Raw reference
            },
        }

        parser = Config().update(config)

        # Raw reference should already be expanded
        assert parser.get("train::dataloader") == {"batch_size": 32}

        # Now prune the system section (delete it)
        parser.update("~system")

        # The raw reference was already expanded, so train::dataloader should still exist
        assert parser.get("train::dataloader") == {"batch_size": 32}
        assert "system" not in parser.get()  # system is deleted

        # Verify we can still resolve after pruning
        result = parser.resolve("train::dataloader")
        assert result == {"batch_size": 32}


class TestComponents:
    """Test component instantiation and handling."""

    def test_disabled_component(self):
        """Test that disabled components return None."""
        config = {
            "component": {
                "_target_": "dict",
                "_disabled_": True,
            }
        }
        parser = Config().update(config)
        result = parser.resolve("component", instantiate=True)
        assert result is None

    def test_disabled_component_in_dict(self):
        """Test disabled component doesn't appear in parent dict."""
        config = {
            "components": {"enabled": {"_target_": "dict", "a": 1}, "disabled": {"_target_": "dict", "_disabled_": True}}
        }
        config_obj = Config()
        config_obj._data = config
        parser = config_obj
        parser._parse()
        result = parser.resolve("components")
        assert "enabled" in result
        assert "disabled" not in result


class TestConfigFileOperations:
    """Test file loading and exporting."""

    def test_load_from_dict(self):
        """Test loading from dict."""
        config = {"key": "value", "num": 42}
        parser = Config().update(config)
        assert parser["key"] == "value"
        assert parser["num"] == 42

    def test_load_from_single_file(self, tmp_path):
        """Test loading from single YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\nnum: 42")

        parser = Config().update(str(config_file))
        assert parser["key"] == "value"
        assert parser["num"] == 42

    def test_load_from_multiple_files(self, tmp_path):
        """Test loading from multiple YAML files with merging (composition-by-default)."""
        base_file = tmp_path / "base.yaml"
        base_file.write_text("a: 1\nb:\n  x: 1\n  y: 2")

        override_file = tmp_path / "override.yaml"
        override_file.write_text("b:\n  z: 3")  # Merges by default now!

        # Chain multiple update() calls
        parser = Config().update(str(base_file)).update(str(override_file))
        assert parser["a"] == 1
        assert parser["b"]["x"] == 1  # Preserved
        assert parser["b"]["y"] == 2  # Preserved
        assert parser["b"]["z"] == 3  # Added

    def test_load_uppercase_yaml(self):
        """Test loading .YML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".YML", delete=False) as f:
            yaml.safe_dump({"test": 1}, f)
            filepath = f.name

        try:
            parser = Config().update(filepath)
            assert parser["test"] == 1
        finally:
            Path(filepath).unlink()

    def test_export_config_file(self):
        """Test export_config_file."""
        config = {"key": "value", "number": 42, "nested": {"a": 1}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            filepath = f.name

        try:
            Config.export_config_file(config, filepath)
            loaded_parser = Config().update(filepath)
            assert loaded_parser._data == config
        finally:
            Path(filepath).unlink()

    def test_split_path_id_with_path(self):
        """Test split_path_id with file path and id."""
        path, ids = split_file_and_id("/path/to/config.yaml::key::subkey")
        assert path == "/path/to/config.yaml"
        assert ids == "key::subkey"

    def test_split_path_id_with_path_no_id(self):
        """Test split_path_id with file path but no id."""
        path, ids = split_file_and_id("/path/to/config.yml")
        assert path == "/path/to/config.yml"
        assert ids == ""

    def test_split_path_id_no_path(self):
        """Test split_path_id with only id."""
        path, ids = split_file_and_id("key::subkey")
        assert path == ""
        assert ids == "key::subkey"


class TestConfigMerging:
    """Test merging configurations with composition-by-default and =/~ operators."""

    def test_basic_merge_default(self):
        """Test default composition (merge) behavior."""
        base = {"a": 1, "b": {"x": 1, "y": 2}}
        override = {"b": {"z": 3}}
        result = apply_operators(base, override)
        # NEW: Default is merge, not replace!
        assert result == {"a": 1, "b": {"x": 1, "y": 2, "z": 3}}

    def test_replace_operator(self):
        """Test = replace operator."""
        base = {"a": 1, "b": {"x": 1, "y": 2}}
        override = {"=b": {"z": 3}}
        result = apply_operators(base, override)
        # = operator replaces entirely
        assert result == {"a": 1, "b": {"z": 3}}

    def test_delete_directive(self):
        """Test ~ remove operator."""
        base = {"a": 1, "b": 2, "c": 3}
        override = {"~b": None}
        result = apply_operators(base, override)
        assert result == {"a": 1, "c": 3}

    def test_nested_merge_default(self):
        """Test nested merge with composition-by-default."""
        base = {"model": {"lr": 0.001, "hidden_size": 512, "optimizer": {"type": "adam", "nested": {"a": 1}}}}
        # NEW: No operators needed for merge!
        override = {"model": {"dropout": 0.1, "optimizer": {"nested": {"b": 2}, "~type": None}}}
        result = apply_operators(base, override)

        assert result["model"]["lr"] == 0.001  # Preserved
        assert result["model"]["hidden_size"] == 512  # Preserved
        assert result["model"]["dropout"] == 0.1  # Added
        assert result["model"]["optimizer"]["nested"] == {"a": 1, "b": 2}  # Merged
        assert "type" not in result["model"]["optimizer"]  # Deleted

    def test_explicit_replace_operator(self):
        """Test that = operator explicitly replaces sections."""
        base = {"training": {"epochs": 50, "batch_size": 16, "lr": 0.001}}
        override = {"=training": {"epochs": 100}}
        result = apply_operators(base, override)
        # With = operator, replaces entirely
        assert result == {"training": {"epochs": 100}}

    def test_merge_dict(self):
        """Test merging a dict (merges by default)."""
        parser = Config().update({"a": 1, "b": {"x": 1, "y": 2}})
        parser.update({"b": {"z": 3}})

        assert parser["a"] == 1
        assert parser["b"]["x"] == 1  # Preserved
        assert parser["b"]["y"] == 2  # Preserved
        assert parser["b"]["z"] == 3  # Added

    def test_merge_file(self, tmp_path):
        """Test merging from file (composition-by-default)."""
        parser = Config().update({"a": 1, "b": {"x": 1, "y": 2}})

        override_file = tmp_path / "override.yaml"
        override_file.write_text("b:\n  z: 3")  # Merges by default!

        parser.update(str(override_file))
        assert parser["b"]["x"] == 1
        assert parser["b"]["y"] == 2
        assert parser["b"]["z"] == 3

    def test_merge_config_instance(self):
        """Test merging another Config instance (merges by default now!)."""
        config1 = Config().update({"a": 1, "b": {"x": 1, "y": 2}})
        config2 = Config().update({"b": {"z": 3}, "c": 4})

        config1.update(config2)

        assert config1["a"] == 1
        # NEW: b is merged by default!
        assert config1["b"]["x"] == 1  # Preserved
        assert config1["b"]["y"] == 2  # Preserved
        assert config1["b"]["z"] == 3  # Added
        assert config1["c"] == 4

    def test_merge_config_instance_with_replace(self):
        """Test merging Config instance with = replace operator."""
        config1 = Config().update({"a": 1, "b": {"x": 1, "y": 2}})

        # Apply replace operator at merge time, not creation time
        config1.update({"=b": {"z": 3}, "c": 4})

        assert config1["a"] == 1
        # = operator replaces b entirely
        assert config1["b"] == {"z": 3}
        assert config1["c"] == 4

    def test_merge_config_from_cli(self):
        """Test merging a Config with CLI overrides applied."""
        import ast

        base_config = Config().update({"model": {"lr": 0.01, "hidden_size": 256}})

        # Create config with CLI overrides using manual parsing
        cli_config = Config().update({"trainer": {"max_epochs": 100}})

        # Parse CLI override manually (simple pattern from docs)
        override = "trainer::max_epochs=50"
        key, value = override.split("=", 1)
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            pass
        cli_config.set(key, value)

        base_config.update(cli_config)

        assert base_config["model"]["lr"] == 0.01
        assert base_config["model"]["hidden_size"] == 256
        assert base_config["trainer"]["max_epochs"] == 50

    def test_merge_config_with_references(self):
        """Test merging Config instances with references."""
        config1 = Config().update({"base_lr": 0.01, "model": {"lr": "@base_lr"}})
        config2 = Config().update({"optimizer": {"lr": "@base_lr"}})

        config1.update(config2)

        # References should be preserved before resolution
        assert config1["model"]["lr"] == "@base_lr"
        assert config1["optimizer"]["lr"] == "@base_lr"

        # Resolve and check values
        resolved = config1.resolve()
        assert resolved["model"]["lr"] == 0.01
        assert resolved["optimizer"]["lr"] == 0.01

    def test_merge_normal_set(self):
        """Test normal set behavior with merge."""
        parser = Config().update({"a": 1, "b": 2})
        parser.update({"a": 10, "c": 3})
        assert parser["a"] == 10
        assert parser["b"] == 2
        assert parser["c"] == 3

    def test_merge_with_delete_directive(self):
        """Test ~ remove operator."""
        parser = Config().update({"a": 1, "b": 2, "c": 3})
        parser.update({"~b": None})
        assert "b" not in parser
        assert parser["a"] == 1
        assert parser["c"] == 3

    def test_merge_nested_delete(self):
        """Test ~ remove operator for nested keys (works without parent operator now!)."""
        parser = Config().update({"model": {"lr": 0.001, "dropout": 0.1}})
        parser.update({"~model::dropout": None})
        assert parser["model"]["lr"] == 0.001
        assert "dropout" not in parser["model"]

    def test_merge_delete_directive_with_non_null_value_raises_error(self):
        """Test that Config.update() with ~key raises error when value is not null, empty, or list."""
        from sparkwheel.utils.exceptions import ConfigMergeError

        parser = Config().update({"a": 1, "b": 2})

        # Test with non-null value
        with pytest.raises(ConfigMergeError, match="Remove operator '~b' must have null, empty, or list value"):
            parser.update({"~b": {"nested": "value"}})

        # Test with nested path and non-null value
        parser = Config().update({"model": {"lr": 0.001, "dropout": 0.1}})
        with pytest.raises(ConfigMergeError, match="Remove operator '~model::dropout' must have null, empty, or list value"):
            parser.update({"~model::dropout": 42})

        # But null and empty should work
        parser = Config().update({"a": 1, "b": 2})
        parser.update({"~b": None})
        assert "b" not in parser

        parser = Config().update({"a": 1, "b": 2})
        parser.update({"~b": ""})
        assert "b" not in parser

    def test_merge_combined_operators(self):
        """Test combining composition, =, ~, and normal updates."""
        parser = Config().update({"a": 1, "b": {"x": 1, "y": 2}, "c": 3, "d": {"old": "value"}})
        parser.update(
            {
                "a": 10,  # Replace scalar
                "b": {"z": 3},  # Merge dict (default!)
                "~c": None,  # Delete
                "=d": {"new": 4},  # Replace dict explicitly
            }
        )
        assert parser["a"] == 10
        assert parser["b"] == {"x": 1, "y": 2, "z": 3}  # Merged!
        assert "c" not in parser
        assert parser["d"] == {"new": 4}  # Replaced

    def test_delete_on_nonexistent_key_idempotent(self):
        """Test that ~key is idempotent (no error when key doesn't exist)."""
        base = {"a": 1}
        override = {"~b": None}

        # NEW: No error! Idempotent delete
        result = apply_operators(base, override)
        assert result == {"a": 1}

    def test_delete_directive_with_invalid_value_raises_error(self):
        """Test that ~key raises error when value is not null, empty, or list."""
        from sparkwheel.utils.exceptions import ConfigMergeError

        base = {"a": 1, "b": 2}

        # Test with dict value
        override = {"~b": {"nested": "value"}}
        with pytest.raises(ConfigMergeError, match="Remove operator '~b' must have null, empty, or list value"):
            apply_operators(base, override)

        # Test with string value
        override = {"~b": "value"}
        with pytest.raises(ConfigMergeError, match="Remove operator '~b' must have null, empty, or list value"):
            apply_operators(base, override)

        # Test with number value
        override = {"~b": 42}
        with pytest.raises(ConfigMergeError, match="Remove operator '~b' must have null, empty, or list value"):
            apply_operators(base, override)

        # Test with boolean value
        override = {"~b": False}
        with pytest.raises(ConfigMergeError, match="Remove operator '~b' must have null, empty, or list value"):
            apply_operators(base, override)

        # But null, empty, and list should work
        override = {"~b": None}
        result = apply_operators(base, override)
        assert result == {"a": 1}

        base = {"a": 1, "b": 2}
        override = {"~b": ""}
        result = apply_operators(base, override)
        assert result == {"a": 1}

    def test_merge_into_empty_dict(self):
        """Test that merging into an empty dict works."""
        base = {"model": {}}
        override = {"model": {"hidden_size": 512}}
        result = apply_operators(base, override)

        assert result == {"model": {"hidden_size": 512}}

    def test_delete_list_items_by_index(self):
        """Test deleting items from list by index."""
        base = {"plugins": ["logger", "metrics", "cache", "auth", "debug"]}
        override = {"~plugins": [0, 2, 4]}
        result = apply_operators(base, override)

        # Indices 0, 2, 4 deleted -> "logger", "cache", "debug" removed
        assert result == {"plugins": ["metrics", "auth"]}

    def test_delete_list_items_single_index(self):
        """Test deleting single item from list."""
        base = {"items": ["a", "b", "c"]}
        override = {"~items": [1]}
        result = apply_operators(base, override)

        assert result == {"items": ["a", "c"]}

    def test_delete_list_items_negative_index(self):
        """Test deleting list items with negative indices."""
        base = {"items": ["a", "b", "c", "d", "e"]}
        override = {"~items": [-1, -2]}
        result = apply_operators(base, override)

        # -1 is "e", -2 is "d"
        assert result == {"items": ["a", "b", "c"]}

    def test_delete_list_items_mixed_indices(self):
        """Test deleting list items with mixed positive and negative indices."""
        base = {"items": ["a", "b", "c", "d", "e"]}
        override = {"~items": [0, -1]}
        result = apply_operators(base, override)

        # 0 is "a", -1 is "e"
        assert result == {"items": ["b", "c", "d"]}

    def test_delete_list_items_duplicate_indices(self):
        """Test that duplicate indices are handled correctly."""
        base = {"items": ["a", "b", "c"]}
        override = {"~items": [1, 1, 1]}
        result = apply_operators(base, override)

        # Should only delete index 1 once
        assert result == {"items": ["a", "c"]}

    def test_delete_list_items_out_of_bounds_error(self):
        """Test that out of bounds index raises error."""
        from sparkwheel.utils.exceptions import ConfigMergeError

        base = {"items": ["a", "b", "c"]}
        override = {"~items": [5]}

        with pytest.raises(ConfigMergeError, match="index 5 out of range"):
            apply_operators(base, override)

        # Test negative out of bounds
        override = {"~items": [-10]}
        with pytest.raises(ConfigMergeError, match="index -10 out of range"):
            apply_operators(base, override)

    def test_delete_list_items_non_integer_error(self):
        """Test that non-integer index raises error."""
        from sparkwheel.utils.exceptions import ConfigMergeError

        base = {"items": ["a", "b", "c"]}
        override = {"~items": ["a"]}

        with pytest.raises(ConfigMergeError, match="index must be integer"):
            apply_operators(base, override)

    def test_delete_list_items_empty_list_error(self):
        """Test that empty list raises error."""
        from sparkwheel.utils.exceptions import ConfigMergeError

        base = {"items": ["a", "b", "c"]}
        override = {"~items": []}

        with pytest.raises(ConfigMergeError, match="cannot be empty"):
            apply_operators(base, override)

    def test_delete_dict_keys(self):
        """Test deleting keys from dict."""
        base = {"dataloaders": {"train": {"batch_size": 32}, "val": {"batch_size": 16}, "test": {"batch_size": 8}}}
        override = {"~dataloaders": ["train", "test"]}
        result = apply_operators(base, override)

        assert result == {"dataloaders": {"val": {"batch_size": 16}}}

    def test_delete_dict_keys_single(self):
        """Test deleting single key from dict."""
        base = {"model": {"dropout": 0.1, "lr": 0.001}}
        override = {"~model": ["dropout"]}
        result = apply_operators(base, override)

        assert result == {"model": {"lr": 0.001}}

    def test_delete_dict_keys_nonexistent_error(self):
        """Test that deleting non-existent key raises error."""
        from sparkwheel.utils.exceptions import ConfigMergeError

        base = {"model": {"lr": 0.001}}
        override = {"~model": ["dropout"]}

        with pytest.raises(ConfigMergeError, match="Cannot remove non-existent key 'dropout' from 'model'"):
            apply_operators(base, override)

    def test_delete_items_from_non_collection_error(self):
        """Test that deleting items from non-list/dict raises error."""
        from sparkwheel.utils.exceptions import ConfigMergeError

        base = {"value": 42}
        override = {"~value": [0]}

        with pytest.raises(ConfigMergeError, match="expected list or dict"):
            apply_operators(base, override)

    def test_delete_list_items_via_config_update(self):
        """Test deleting list items via Config.update()."""
        config = Config().update({"plugins": ["logger", "metrics", "cache", "auth"]})
        config.update({"~plugins": [0, 2]})

        assert config["plugins"] == ["metrics", "auth"]

    def test_delete_dict_keys_via_config_update(self):
        """Test deleting dict keys via Config.update()."""
        config = Config().update({"dataloaders": {"train": {}, "val": {}, "test": {}}})
        config.update({"~dataloaders": ["train", "test"]})

        assert config["dataloaders"] == {"val": {}}

    def test_delete_list_items_batch_vs_individual(self):
        """Test that batch deletion is the only way to delete list items.

        Path notation like ~plugins::0 doesn't work for lists - you MUST use
        the batch syntax ~plugins: [0, 2] to delete list items.
        """
        # Batch deletion - the correct way
        config1 = Config().update({"plugins": ["a", "b", "c", "d", "e"]})
        config1.update({"~plugins": [0, 2]})
        assert config1["plugins"] == ["b", "d", "e"]  # Removed "a" and "c"

        # Batch deletion with multiple operations - indices relative to current state
        config2 = Config().update({"plugins": ["a", "b", "c", "d", "e"]})
        config2.update({"~plugins": [0]})  # Removes "a" -> ["b", "c", "d", "e"]
        config2.update({"~plugins": [1]})  # Removes "c" (index 1 in current list)
        assert config2["plugins"] == ["b", "d", "e"]

        # This demonstrates that separate batch operations evaluate indices
        # against the current state, not the original state

    def test_merge_lists_extends(self):
        """Test that lists extend by default (composition)."""
        base = {"plugins": ["logger", "metrics"]}
        override = {"plugins": ["cache", "auth"]}
        result = apply_operators(base, override)

        # NEW: Lists extend by default!
        assert result == {"plugins": ["logger", "metrics", "cache", "auth"]}

    def test_merge_lists_keeps_duplicates(self):
        """Test that list extension keeps duplicates."""
        base = {"items": ["a", "b", "c"]}
        override = {"items": ["b", "d"]}
        result = apply_operators(base, override)

        assert result == {"items": ["a", "b", "c", "b", "d"]}

    def test_merge_lists_with_nested_dicts(self):
        """Test that list extension with dicts just appends."""
        base = {"items": [{"id": 1, "name": "foo"}]}
        override = {"items": [{"id": 2, "name": "bar"}]}
        result = apply_operators(base, override)

        assert result == {"items": [{"id": 1, "name": "foo"}, {"id": 2, "name": "bar"}]}

    def test_replace_list_with_equals(self):
        """Test that =key replaces list entirely."""
        base = {"items": ["a", "b", "c"]}
        override = {"=items": ["x", "y"]}
        result = apply_operators(base, override)

        assert result == {"items": ["x", "y"]}

    def test_merge_lists_of_lists(self):
        """Test that list extension works with nested lists."""
        base = {"matrix": [[1, 2], [3, 4]]}
        override = {"matrix": [[5, 6]]}
        result = apply_operators(base, override)

        assert result == {"matrix": [[1, 2], [3, 4], [5, 6]]}

    def test_merge_empty_list(self):
        """Test that merging into an empty list works."""
        base = {"items": []}
        override = {"items": ["a", "b"]}
        result = apply_operators(base, override)

        assert result == {"items": ["a", "b"]}

    def test_merge_with_empty_list(self):
        """Test that extending with empty list works."""
        base = {"items": ["a", "b"]}
        override = {"items": []}
        result = apply_operators(base, override)

        assert result == {"items": ["a", "b"]}


class TestConfigAdvanced:
    """Test advanced Config features."""

    def test_resolve_direct_access(self):
        """Test Config resolve() for direct access."""
        config = {"value": 10, "ref": "@value"}
        parser = Config().update(config)
        result = parser.resolve("ref")
        assert result == 10

    def test_parse_reset_true(self):
        """Test parse with reset=True."""
        parser = Config({"value": 10, "expr": "$@value * 2"})
        parser._parse(reset=True)
        assert len(parser._resolver._items) > 0
        parser._parse(reset=True)
        assert len(parser._resolver._items) > 0

    def test_parse_reset_false(self):
        """Test parse with reset=False."""
        parser = Config({"value": 10})
        parser._parse(reset=True)
        first_resolved = dict(parser._resolver._resolved)
        parser._parse(reset=False)
        assert parser._resolver._resolved == first_resolved

    def test_get_parsed_content_auto_parse(self):
        """Test get_parsed_content auto-parses if not parsed."""
        parser = Config({"value": 10, "ref": "@value"})
        result = parser.resolve("ref")
        assert result == 10

    def test_get_parsed_content_lazy_false(self):
        """Test get_parsed_content with lazy=False."""
        parser = Config({"value": 10})
        parser._parse()
        parser["value"] = 20
        result = parser.resolve("value", lazy=False)
        assert result == 20

    def test_get_parsed_content_lazy_false_forces_reparse(self):
        """Test get_parsed_content with lazy=False forces re-parse."""
        parser = Config({"value": 10, "ref": "@value"})
        parser._parse()
        parser.resolve("ref")
        parser["value"] = 20
        result2 = parser.resolve("ref", lazy=False)
        assert result2 == 20

    def test_get_parsed_content_with_default(self):
        """Test get_parsed_content with default."""
        parser = Config({})
        parser._parse()
        from sparkwheel import Item

        default = Item({"default": True}, id="default")
        result = parser.resolve("missing", default=default)
        assert result == {"default": True}

    def test_do_parse_nested(self):
        """Test _do_parse with nested structures."""
        config = {"comp": {"_target_": "dict", "a": 1}, "expr": "$1 + 1", "plain": "value"}
        config_obj = Config()
        config_obj._data = config
        parser = config_obj
        parser._parse()
        assert "comp" in parser._resolver._items
        assert "expr" in parser._resolver._items
        assert "plain" in parser._resolver._items


class TestConfigEdgeCases:
    """Test edge cases in Config."""

    def test_set_with_non_dict_root(self):
        """Test setting value when root is not a dict."""
        parser = Config("not a dict")
        parser.set("new_key", "value")
        # Should convert root to dict
        assert parser["new_key"] == "value"

    def test_update_with_non_string_keys(self):
        """Test update with non-string keys."""
        parser = Config({})
        parser.update({123: "numeric_key", 456: "another"})
        # Non-string keys are converted to strings during update
        assert 123 in parser._data or "123" in parser._data

    def test_compose_operator_path_based_both_dicts(self):
        """Test composition in path-based update when both values are dicts."""
        parser = Config({"value": {"old": "data"}})
        # Use _apply_path_updates directly - merges by default!
        parser._apply_path_updates({"value": {"new": "dict"}})
        # Should merge the dicts
        assert parser["value"]["old"] == "data"
        assert parser["value"]["new"] == "dict"

    def test_compose_operator_path_based_both_lists(self):
        """Test composition in path-based update when both values are lists."""
        parser = Config({"items": ["a", "b"]})
        # Use _apply_path_updates directly - extends by default!
        parser._apply_path_updates({"items": ["c", "d"]})
        # Should extend the lists
        assert parser["items"] == ["a", "b", "c", "d"]

    def test_replace_operator_path_based(self):
        """Test = replace operator in path-based update."""
        parser = Config({"value": {"old": "data"}})
        # Use _apply_path_updates directly with = operator
        parser._apply_path_updates({"=value": {"new": "dict"}})
        # Should replace
        assert parser["value"] == {"new": "dict"}

    def test_delete_nested_key_parent_not_dict(self):
        """Test delete with nested key when parent is not a dict."""
        parser = Config({"parent": "not a dict"})
        # Attempting to delete nested key when parent is not dict
        # Should not raise error, just no-op
        parser._delete_nested_key("parent::child")

    def test_delete_top_level_key_non_dict_root(self):
        """Test delete when root is not a dict."""
        parser = Config("not a dict")
        # Should not raise error
        parser._delete_nested_key("key")

    def test_resolve_with_item_default(self):
        """Test resolve with Item instance as default."""
        from sparkwheel import Item

        parser = Config({"existing": "value"})

        item_default = Item({"default_key": "default_value"}, id="default")
        result = parser.resolve("missing_key", default=item_default)
        # Should return the config from the Item
        assert result == {"default_key": "default_value"}


class TestConfigUpdateAutoDetection:
    """Test auto-detection of files vs overrides in Config.update()."""

    def test_update_auto_detect_file(self, tmp_path):
        """Test that strings without '=' are treated as files."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\nnum: 42")

        config = Config()
        config.update(str(config_file))

        assert config["key"] == "value"
        assert config["num"] == 42

    def test_update_auto_detect_override(self):
        """Test that strings with '=' are treated as overrides."""
        config = Config().update({"model": {"lr": 0.01}})
        config.update("model::lr=0.001")

        assert config["model"]["lr"] == 0.001

    def test_update_auto_detect_replace_operator(self):
        """Test auto-detection of =key=value (replace operator)."""
        config = Config().update({"model": {"lr": 0.01, "hidden_size": 256}})
        config.update("=model={'_target_': 'ResNet'}")

        assert config["model"] == {"_target_": "ResNet"}
        assert "hidden_size" not in config["model"]

    def test_update_auto_detect_delete_operator(self):
        """Test auto-detection of ~key (delete operator)."""
        config = Config().update({"a": 1, "b": 2, "c": 3})
        config.update("~b")

        assert "b" not in config
        assert config["a"] == 1
        assert config["c"] == 3

    def test_update_mixed_files_and_overrides(self, tmp_path):
        """Test chaining files and overrides using auto-detection."""
        base_file = tmp_path / "base.yaml"
        base_file.write_text("model:\n  lr: 0.01\n  hidden_size: 256")

        override_file = tmp_path / "override.yaml"
        override_file.write_text("trainer:\n  epochs: 100")

        config = (
            Config()
            .update(str(base_file))
            .update(str(override_file))
            .update("model::dropout=0.1")
            .update("trainer::epochs=50")
        )

        assert config["model"]["lr"] == 0.01
        assert config["model"]["hidden_size"] == 256
        assert config["model"]["dropout"] == 0.1
        assert config["trainer"]["epochs"] == 50

    def test_update_cli_pattern(self):
        """Test the CLI integration pattern (just loop!)."""
        cli_args = [
            "model::lr=0.001",
            "optimizer::type=adam",
            "=scheduler={'_target_': 'CosineScheduler'}",
            "~debug",
        ]

        config = Config().update({"debug": True, "model": {"lr": 0.01}})

        for arg in cli_args:
            config.update(arg)

        assert config["model"]["lr"] == 0.001
        assert config["optimizer"]["type"] == "adam"
        assert config["scheduler"] == {"_target_": "CosineScheduler"}
        assert "debug" not in config


class TestParseOverrides:
    """Test parse_overrides helper function."""

    def test_parse_keyvalue_style(self):
        """Test parsing key=value style."""
        from sparkwheel import parse_overrides

        args = ["model::lr=0.001", "trainer::epochs=100"]
        result = parse_overrides(args)
        assert result == {"model::lr": 0.001, "trainer::epochs": 100}

    def test_parse_replace_operator(self):
        """Test parsing =key=value (replace operator)."""
        from sparkwheel import parse_overrides

        args = ["=model={'_target_': 'ResNet'}", "=optimizer::lr=0.01"]
        result = parse_overrides(args)
        assert result == {"=model": {"_target_": "ResNet"}, "=optimizer::lr": 0.01}

    def test_parse_delete_operator(self):
        """Test parsing ~key (delete operator)."""
        from sparkwheel import parse_overrides

        args = ["~old_param", "~model::deprecated"]
        result = parse_overrides(args)
        assert result == {"~old_param": None, "~model::deprecated": None}

    def test_parse_type_inference(self):
        """Test automatic type inference."""
        from sparkwheel import parse_overrides

        args = [
            "lr=0.001",
            "epochs=100",
            "debug=True",
            "name=my_model",
            "devices=[0,1,2]",
            "config={'lr':0.001}",
        ]
        result = parse_overrides(args)
        assert result == {
            "lr": 0.001,
            "epochs": 100,
            "debug": True,
            "name": "my_model",
            "devices": [0, 1, 2],
            "config": {"lr": 0.001},
        }

    def test_parse_nested_paths(self):
        """Test parsing deeply nested paths."""
        from sparkwheel import parse_overrides

        args = ["model::optimizer::lr=0.001", "model::optimizer::betas=[0.9,0.999]"]
        result = parse_overrides(args)
        assert result == {
            "model::optimizer::lr": 0.001,
            "model::optimizer::betas": [0.9, 0.999],
        }

    def test_parse_operators_with_paths(self):
        """Test operators with nested paths."""
        from sparkwheel import parse_overrides

        args = ["=model::optimizer={'type':'sgd'}", "~model::old_param"]
        result = parse_overrides(args)
        assert result == {"=model::optimizer": {"type": "sgd"}, "~model::old_param": None}

    def test_parse_value_with_equals(self):
        """Test parsing values that contain equals sign."""
        from sparkwheel import parse_overrides

        args = ["equation=a=b+c"]
        result = parse_overrides(args)
        # Should split only on first =
        assert result == {"equation": "a=b+c"}

    def test_parse_empty_args(self):
        """Test parsing empty args list."""
        from sparkwheel import parse_overrides

        result = parse_overrides([])
        assert result == {}

    def test_parse_with_config_update(self):
        """Test using parse_overrides with Config.update()."""
        from sparkwheel import Config, parse_overrides

        config = Config().update({"model": {"lr": 0.01, "hidden_size": 256}})
        overrides = parse_overrides(["model::lr=0.001", "trainer::epochs=100"])
        config.update(overrides)

        assert config["model"]["lr"] == 0.001
        assert config["model"]["hidden_size"] == 256
        assert config["trainer"]["epochs"] == 100


class TestConfigFreeze:
    """Test config freeze/unfreeze functionality."""

    def test_freeze_prevents_modifications(self):
        """Test that freeze() prevents modifications."""
        from sparkwheel.utils.exceptions import FrozenConfigError

        config = Config().update({"key": "value"})
        config.freeze()

        with pytest.raises(FrozenConfigError, match="Cannot modify frozen config"):
            config["key"] = "new_value"

        with pytest.raises(FrozenConfigError, match="Cannot modify frozen config"):
            config["new_key"] = "value"

    def test_unfreeze_allows_modifications(self):
        """Test that unfreeze() allows modifications again."""
        config = Config().update({"key": "value"})
        config.freeze()
        config.unfreeze()

        # Should work now
        config["key"] = "new_value"
        assert config["key"] == "new_value"

        config["new_key"] = "another_value"
        assert config["new_key"] == "another_value"

    def test_is_frozen(self):
        """Test is_frozen() method."""
        config = Config()
        assert config.is_frozen() is False

        config.freeze()
        assert config.is_frozen() is True

        config.unfreeze()
        assert config.is_frozen() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
