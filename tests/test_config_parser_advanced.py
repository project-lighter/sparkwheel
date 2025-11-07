import tempfile
from pathlib import Path

import pytest
import yaml

from sparkwheel import ConfigParser


class TestConfigParserFileOperations:
    """Test ConfigParser file loading and exporting."""

    def test_load_config_file_yaml(self):
        """Test load_config_file with YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"key": "value", "number": 42}, f)
            filepath = f.name

        try:
            result = ConfigParser.load_config_file(filepath)
            assert result == {"key": "value", "number": 42}
        finally:
            Path(filepath).unlink()

    def test_load_config_file_yml(self):
        """Test load_config_file with .yml extension."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.safe_dump({"test": True}, f)
            filepath = f.name

        try:
            result = ConfigParser.load_config_file(filepath)
            assert result == {"test": True}
        finally:
            Path(filepath).unlink()

    def test_load_config_file_empty_path(self):
        """Test load_config_file with empty path."""
        result = ConfigParser.load_config_file("")
        assert result == {}

    def test_load_config_file_invalid_extension(self):
        """Test load_config_file with invalid extension."""
        with pytest.raises(ValueError, match="unknown file input"):
            ConfigParser.load_config_file("file.txt")

    def test_load_config_files_single_file(self):
        """Test load_config_files with single file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"a": 1}, f)
            filepath = f.name

        try:
            result = ConfigParser.load_config_files(filepath)
            assert result == {"a": 1}
        finally:
            Path(filepath).unlink()

    def test_load_config_files_multiple_files(self):
        """Test load_config_files with multiple files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f1:
            yaml.safe_dump({"a": 1, "b": 2}, f1)
            filepath1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f2:
            yaml.safe_dump({"b": 3, "c": 4}, f2)
            filepath2 = f2.name

        try:
            result = ConfigParser.load_config_files([filepath1, filepath2])
            # Second file should override 'b'
            assert result == {"a": 1, "b": 3, "c": 4}
        finally:
            Path(filepath1).unlink()
            Path(filepath2).unlink()

    def test_load_config_files_comma_separated(self):
        """Test load_config_files with comma-separated string."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f1:
            yaml.safe_dump({"x": 1}, f1)
            filepath1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f2:
            yaml.safe_dump({"y": 2}, f2)
            filepath2 = f2.name

        try:
            result = ConfigParser.load_config_files(f"{filepath1},{filepath2}")
            assert result == {"x": 1, "y": 2}
        finally:
            Path(filepath1).unlink()
            Path(filepath2).unlink()

    def test_load_config_files_dict(self):
        """Test load_config_files with dict returns dict directly."""
        config = {"direct": True}
        result = ConfigParser.load_config_files(config)
        assert result is config

    def test_load_config_files_nested_keys(self):
        """Test load_config_files with nested keys using ::."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"parent": {"child": "value"}}, f)
            filepath = f.name

        try:
            result = ConfigParser.load_config_files(filepath)
            assert result["parent"]["child"] == "value"
        finally:
            Path(filepath).unlink()

    def test_export_config_file(self):
        """Test export_config_file."""
        config = {"key": "value", "number": 42, "nested": {"a": 1}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            filepath = f.name

        try:
            ConfigParser.export_config_file(config, filepath)
            # Read it back
            loaded = ConfigParser.load_config_file(filepath)
            assert loaded == config
        finally:
            Path(filepath).unlink()

    def test_read_config(self):
        """Test read_config method."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"config_key": "config_value"}, f)
            filepath = f.name

        try:
            parser = ConfigParser()
            parser.read_config(filepath)
            assert parser["config_key"] == "config_value"
        finally:
            Path(filepath).unlink()

    def test_read_config_preserves_meta(self):
        """Test read_config preserves _meta_ field."""
        parser = ConfigParser()
        parser["_meta_"] = {"existing": "meta"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"new_key": "new_value"}, f)
            filepath = f.name

        try:
            parser.read_config(filepath)
            assert parser["_meta_"] == {"existing": "meta"}
            assert parser["new_key"] == "new_value"
        finally:
            Path(filepath).unlink()

    def test_read_meta(self):
        """Test read_meta method."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"meta_key": "meta_value"}, f)
            filepath = f.name

        try:
            parser = ConfigParser()
            parser.read_meta(filepath)
            assert parser["_meta_"]["meta_key"] == "meta_value"
        finally:
            Path(filepath).unlink()

    def test_read_meta_with_dict(self):
        """Test read_meta with direct dict."""
        parser = ConfigParser()
        meta_dict = {"direct": "meta"}
        parser.read_meta(meta_dict)
        assert parser["_meta_"] == meta_dict

    def test_split_path_id_with_path(self):
        """Test split_path_id with file path and id."""
        path, ids = ConfigParser.split_path_id("/path/to/config.yaml::key::subkey")
        assert path == "/path/to/config.yaml"
        assert ids == "key::subkey"

    def test_split_path_id_with_path_no_id(self):
        """Test split_path_id with file path but no id."""
        path, ids = ConfigParser.split_path_id("/path/to/config.yml")
        assert path == "/path/to/config.yml"
        assert ids == ""

    def test_split_path_id_no_path(self):
        """Test split_path_id with only id."""
        path, ids = ConfigParser.split_path_id("key::subkey")
        assert path == ""
        assert ids == "key::subkey"

    def test_split_path_id_hash_separator(self):
        """Test split_path_id normalizes hash separator."""
        path, ids = ConfigParser.split_path_id("/path/to/config.yaml#key#subkey")
        assert path == "/path/to/config.yaml"
        assert ids == "key::subkey"


class TestConfigParserAdvanced:
    """Advanced ConfigParser tests."""

    def test_repr(self):
        """Test ConfigParser __repr__."""
        parser = ConfigParser({"key": "value"})
        repr_str = repr(parser)
        assert "key" in repr_str

    def test_getattr(self):
        """Test ConfigParser __getattr__."""
        config = {"value": 10, "ref": "@value"}
        parser = ConfigParser(config)
        parser.parse()
        # __getattr__ should call get_parsed_content
        result = parser.ref
        assert result == 10

    def test_get_with_default(self):
        """Test get method with default."""
        parser = ConfigParser({"existing": "value"})
        assert parser.get("existing") == "value"
        assert parser.get("missing", "default") == "default"

    def test_get_invalid_key_default(self):
        """Test get returns default for invalid key."""
        parser = ConfigParser({"a": {"b": 1}})
        # Try to access non-dict as dict
        assert parser.get("a::b::c", "default") == "default"

    def test_set_recursive_creates_nested(self):
        """Test set with recursive=True creates nested structure."""
        parser = ConfigParser({})
        parser.set(42, "level1::level2::level3", recursive=True)
        assert parser["level1"]["level2"]["level3"] == 42

    def test_set_recursive_false(self):
        """Test set with recursive=False."""
        parser = ConfigParser({"level1": {"level2": {}}})
        parser.set(42, "level1::level2::level3", recursive=False)
        assert parser["level1"]["level2"]["level3"] == 42

    def test_set_empty_id(self):
        """Test set with empty id replaces entire config."""
        parser = ConfigParser({"old": "config"})
        parser.set({"new": "config"}, "")
        assert parser.get() == {"new": "config"}

    def test_setitem_empty_id(self):
        """Test __setitem__ with empty id."""
        parser = ConfigParser({"old": "config"})
        parser[""] = {"new": "config"}
        assert parser.get() == {"new": "config"}

    def test_update(self):
        """Test update method."""
        parser = ConfigParser({"a": 1, "b": {"c": 2}})
        parser.update({"a": 10, "b::c": 20, "d": 30})
        assert parser["a"] == 10
        assert parser["b::c"] == 20
        assert parser["d"] == 30

    def test_getitem_invalid_config_type(self):
        """Test __getitem__ raises error for invalid config type."""
        parser = ConfigParser({"scalar": 42})
        with pytest.raises(ValueError, match="config must be dict or list"):
            _ = parser["scalar::invalid"]

    def test_getitem_list_indexing(self):
        """Test __getitem__ with list indexing."""
        parser = ConfigParser({"items": [10, 20, 30]})
        assert parser["items::0"] == 10
        assert parser["items::1"] == 20
        assert parser["items::2"] == 30

    def test_setitem_list_indexing(self):
        """Test __setitem__ with list indexing."""
        parser = ConfigParser({"items": [10, 20, 30]})
        parser["items::1"] = 99
        assert parser["items::1"] == 99

    def test_resolve_relative_ids(self):
        """Test resolve_relative_ids method."""
        # @#value means value in same level
        result = ConfigParser.resolve_relative_ids("parent::child", "@#sibling")
        assert result == "@parent::sibling"

    def test_resolve_relative_ids_double_hash(self):
        """Test resolve_relative_ids with ##."""
        # @##value means going up one level from current position
        result = ConfigParser.resolve_relative_ids("parent::child", "@##value")
        assert result == "@value"  # Goes up from "child", removing "parent" entirely

    def test_resolve_relative_ids_triple_hash(self):
        """Test resolve_relative_ids with ###."""
        # ### goes up 2 levels from current (removes b and c, keeps a)
        result = ConfigParser.resolve_relative_ids("a::b::c", "@###value")
        assert result == "@value"  # Goes to root level

    def test_resolve_relative_ids_equal_levels(self):
        """Test resolve_relative_ids when going up equals depth."""
        # With id "a::b" (depth 2), ## means 1 level up from the last part
        result = ConfigParser.resolve_relative_ids("a::b", "@##value")
        assert result == "@value"  # Goes to root

    def test_resolve_relative_ids_out_of_range(self):
        """Test resolve_relative_ids raises error when out of range."""
        with pytest.raises(ValueError, match="out of the range"):
            ConfigParser.resolve_relative_ids("a", "@##value")

    def test_resolve_relative_ids_macro(self):
        """Test resolve_relative_ids with macro %."""
        result = ConfigParser.resolve_relative_ids("parent::child", "%#sibling")
        assert result == "%parent::sibling"

    def test_resolve_relative_ids_in_list(self):
        """Test resolve_relative_ids in list context."""
        result = ConfigParser.resolve_relative_ids("parent::items::1", "@#0")
        assert result == "@parent::items::0"

    def test_do_resolve_macro_from_config(self):
        """Test _do_resolve with macro referencing same config."""
        parser = ConfigParser({"template": {"a": 1, "b": 2}, "copy": "%template"})
        parser.resolve_macro_and_relative_ids()
        assert parser["copy"] == {"a": 1, "b": 2}
        # Ensure it's a deep copy
        parser["copy"]["a"] = 99
        assert parser["template"]["a"] == 1

    def test_do_resolve_macro_from_file(self):
        """Test _do_resolve with macro from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"external": {"value": 42}}, f)
            filepath = f.name

        try:
            parser = ConfigParser({"local": f"%{filepath}::external"})
            parser.resolve_macro_and_relative_ids()
            assert parser["local"] == {"value": 42}
        finally:
            Path(filepath).unlink()

    def test_parse_reset_true(self):
        """Test parse with reset=True."""
        parser = ConfigParser({"value": 10, "expr": "$@value * 2"})
        parser.parse(reset=True)
        # After parse, items should be added to resolver
        assert len(parser.ref_resolver.items) > 0
        # Parse again with reset - should reset and re-add items
        parser.parse(reset=True)
        # Items should still be present
        assert len(parser.ref_resolver.items) > 0

    def test_parse_reset_false(self):
        """Test parse with reset=False."""
        parser = ConfigParser({"value": 10})
        parser.parse(reset=True)
        first_resolved = dict(parser.ref_resolver.resolved_content)
        parser.parse(reset=False)
        # Should keep existing resolved content
        assert parser.ref_resolver.resolved_content == first_resolved

    def test_get_parsed_content_auto_parse(self):
        """Test get_parsed_content auto-parses if not parsed."""
        parser = ConfigParser({"value": 10, "ref": "@value"})
        # Don't call parse() manually
        result = parser.get_parsed_content("ref")
        assert result == 10

    def test_get_parsed_content_lazy_false(self):
        """Test get_parsed_content with lazy=False."""
        parser = ConfigParser({"value": 10})
        parser.parse()
        # Modify config after parsing
        parser["value"] = 20
        # With lazy=False, should re-parse
        result = parser.get_parsed_content("value", lazy=False)
        assert result == 20

    def test_get_parsed_content_with_default(self):
        """Test get_parsed_content with default."""
        parser = ConfigParser({})
        parser.parse()
        from sparkwheel import ConfigItem

        default = ConfigItem({"default": True}, id="default")
        result = parser.get_parsed_content("missing", default=default)
        assert result == {"default": True}

    def test_do_parse_nested(self):
        """Test _do_parse with nested structures."""
        config = {"comp": {"_target_": "dict", "a": 1}, "expr": "$1 + 1", "plain": "value"}
        parser = ConfigParser(config)
        parser.parse()
        assert "comp" in parser.ref_resolver.items
        assert "expr" in parser.ref_resolver.items
        assert "plain" in parser.ref_resolver.items

    def test_contains_nested(self):
        """Test __contains__ with nested path."""
        parser = ConfigParser({"a": {"b": {"c": 1}}})
        assert "a" in parser
        assert "a::b" in parser
        assert "a::b::c" in parser
        assert "a::b::d" not in parser

    def test_init_with_none(self):
        """Test ConfigParser init with None."""
        parser = ConfigParser(None)
        assert "_meta_" in parser.config
        assert isinstance(parser.config, dict)

    def test_init_with_globals_dict(self):
        """Test ConfigParser init with globals dict."""
        parser = ConfigParser({}, globals={"pd": "pandas"})
        assert "pd" in parser.globals

    def test_init_with_globals_callable(self):
        """Test ConfigParser init with globals containing callables."""
        from collections import Counter

        parser = ConfigParser({}, globals={"Counter": Counter})
        assert parser.globals["Counter"] is Counter

    def test_complex_nested_reference(self):
        """Test complex nested reference resolution."""
        config = {"data": {"values": [1, 2, 3], "metadata": {"count": "$len(@data::values)"}}, "ref": "@data::metadata::count"}
        parser = ConfigParser(config)
        parser.parse()
        result = parser.get_parsed_content("ref")
        assert result == 3

    def test_disabled_component_in_dict(self):
        """Test disabled component doesn't appear in parent dict."""
        config = {
            "components": {"enabled": {"_target_": "dict", "a": 1}, "disabled": {"_target_": "dict", "_disabled_": True}}
        }
        parser = ConfigParser(config)
        parser.parse()
        result = parser.get_parsed_content("components")
        assert "enabled" in result
        assert "disabled" not in result

    def test_expression_with_reference_to_component(self):
        """Test expression referencing an instantiated component."""
        config = {"mydict": {"_target_": "dict", "a": 1, "b": 2}, "value": "$@mydict['a']"}
        parser = ConfigParser(config)
        parser.parse()
        result = parser.get_parsed_content("value")
        assert result == 1


def test_set_with_none_config():
    """Test set() when config is None."""
    parser = ConfigParser({"a": 1})
    parser.config = None
    parser.set(42, "key", recursive=True)
    assert parser.config is not None


def test_load_uppercase_yaml():
    """Test loading .YML file."""
    import tempfile
    from pathlib import Path

    import yaml

    with tempfile.NamedTemporaryFile(mode="w", suffix=".YML", delete=False) as f:
        yaml.safe_dump({"test": 1}, f)
        filepath = f.name

    try:
        result = ConfigParser.load_config_file(filepath)
        assert result == {"test": 1}
    finally:
        Path(filepath).unlink()


def test_get_parsed_content_with_lazy_false_forces_reparse():
    """Test get_parsed_content with lazy=False forces re-parse."""
    parser = ConfigParser({"value": 10, "ref": "@value"})
    parser.parse()
    # Get first result (not used, but establishes baseline)
    parser.get_parsed_content("ref")
    # Change the value
    parser["value"] = 20
    # With lazy=False, should re-parse
    result2 = parser.get_parsed_content("ref", lazy=False)
    assert result2 == 20


@pytest.mark.parametrize("ext", [".yaml", ".YAML", ".Yaml", ".yml", ".YML", ".Yml"])
def test_load_config_file_with_case_insensitive_extension(ext):
    """Test that .Yaml, .YAML, .yml, .YML all work."""
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False) as f:
        yaml.safe_dump({"ext": ext}, f)
        filepath = f.name

    try:
        result = ConfigParser.load_config_file(filepath)
        assert result == {"ext": ext}
    finally:
        Path(filepath).unlink(missing_ok=True)
