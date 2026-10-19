"""Tests for the YAML loader module."""

import pytest

from sparkwheel.loader import Loader
from sparkwheel.locations import LocationRegistry
from sparkwheel.utils.exceptions import Location


class TestLoaderBasic:
    """Test basic Loader functionality."""

    def test_load_file_basic(self, tmp_path):
        """Test loading a basic YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\nnumber: 42")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config == {"key": "value", "number": 42}
        assert isinstance(metadata, LocationRegistry)

    def test_load_file_empty_filepath(self):
        """Test loading with empty filepath returns empty config."""
        loader = Loader()
        config, metadata = loader.load_file("")

        assert config == {}
        assert isinstance(metadata, LocationRegistry)

    def test_load_file_none_filepath(self):
        """Test loading with None filepath returns empty config."""
        loader = Loader()
        config, metadata = loader.load_file(None)

        assert config == {}
        assert isinstance(metadata, LocationRegistry)

    def test_load_file_non_yaml_extension(self, tmp_path):
        """Test loading non-YAML file raises ValueError."""
        config_file = tmp_path / "config.txt"
        config_file.write_text("key: value")

        loader = Loader()
        with pytest.raises(ValueError, match="must be a YAML file"):
            loader.load_file(str(config_file))

    def test_load_file_with_parent_directory(self, tmp_path, recwarn):
        """A path with '..' loads like any other path, without warnings."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value")

        loader = Loader()
        config, metadata = loader.load_file(str(tmp_path / ".." / tmp_path.name / "config.yaml"))

        assert config == {"key": "value"}
        assert not recwarn.list

    def test_load_file_with_yml_extension(self, tmp_path):
        """Test loading .yml file works."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("key: value")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config == {"key": "value"}


class TestLoaderMetadataTracking:
    """Test metadata tracking during YAML loading."""

    def test_metadata_tracks_source_location(self, tmp_path):
        """Test that source locations are tracked."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("model:\n  lr: 0.001")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        # Check that metadata was registered for top-level keys
        location = metadata.get("")
        assert location is not None
        assert location.filepath == str(config_file.resolve())

    def test_metadata_with_nested_config(self, tmp_path):
        """Test metadata tracking for nested config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("model:\n  optimizer:\n    lr: 0.001")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config == {"model": {"optimizer": {"lr": 0.001}}}

    def test_metadata_with_list_config(self, tmp_path):
        """Test metadata tracking for list config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("items:\n  - item1\n  - item2\n  - item3")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config == {"items": ["item1", "item2", "item3"]}
        # Metadata should be tracked for the list
        location = metadata.get("items")
        assert location is not None


class TestLoaderEdgeCases:
    """Test edge cases in loader."""

    def test_load_empty_yaml_file(self, tmp_path):
        """Test loading empty YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config == {}

    def test_load_yaml_with_null(self, tmp_path):
        """Test loading YAML file with null value."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: null")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config == {"key": None}

    def test_load_yaml_with_complex_nested_structure(self, tmp_path):
        """Test loading complex nested structure."""
        yaml_content = """
model:
  layers:
    - name: conv1
      params:
        filters: 32
    - name: conv2
      params:
        filters: 64
  optimizer:
    type: adam
    lr: 0.001
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config["model"]["layers"][0]["name"] == "conv1"
        assert config["model"]["layers"][1]["params"]["filters"] == 64
        assert config["model"]["optimizer"]["lr"] == 0.001

    def test_strip_metadata_from_nested_lists(self, tmp_path):
        """Test that metadata is stripped from nested lists."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("items:\n  - [1, 2, 3]\n  - [4, 5, 6]")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config == {"items": [[1, 2, 3], [4, 5, 6]]}
        # Ensure no __sparkwheel_metadata__ keys in the config
        assert "__sparkwheel_metadata__" not in str(config)

    def test_strip_metadata_from_dicts_in_lists(self, tmp_path):
        """Test stripping metadata from dicts inside lists."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("items:\n  - key: value1\n  - key: value2")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config == {"items": [{"key": "value1"}, {"key": "value2"}]}
        # Ensure no __sparkwheel_metadata__ keys
        assert "__sparkwheel_metadata__" not in str(config)


class TestLoaderYamlRules:
    """Duplicate keys, merge keys and YAML 1.2 floats."""

    @pytest.mark.parametrize(
        "text,key,first,again",
        [
            ("a: 1\nb: 2\na: 3\n", "a", 1, 3),
            ("model:\n  lr: 0.1\n  lr: 0.2\n", "lr", 2, 3),
            ("items:\n  - x: 1\n    x: 2\n", "x", 2, 3),
        ],
    )
    def test_duplicate_keys_raise_naming_both_lines(self, tmp_path, text, key, first, again):
        import yaml

        path = tmp_path / "dup.yaml"
        path.write_text(text)
        with pytest.raises(yaml.YAMLError) as excinfo:
            Loader().load_file(str(path))
        message = str(excinfo.value)
        assert f"duplicate key '{key}'" in message
        assert f"first defined on line {first}" in message
        assert f"line {again}" in message and str(path) in message

    def test_merge_keys(self, tmp_path):
        path = tmp_path / "merge.yaml"
        path.write_text("base: &b\n  x: 1\n  y: 2\nderived:\n  <<: *b\n  y: 3\n")
        config, locations = Loader().load_file(str(path))
        assert config == {"base": {"x": 1, "y": 2}, "derived": {"x": 1, "y": 3}}
        assert locations.get("derived::y").line == 6

    def test_values_under_an_alias_have_locations(self, tmp_path):
        path = tmp_path / "alias.yaml"
        path.write_text("base: &b\n  nested:\n    value: [1]\nderived:\n  <<: *b\ncopy: *b\n")
        _, locations = Loader().load_file(str(path))
        assert locations.get("derived::nested::value").line == 3
        assert locations.get("copy::nested::value::0").line == 3

    def test_merge_key_list(self, tmp_path):
        path = tmp_path / "merge.yaml"
        path.write_text("a: &a {x: 1}\nb: &b {x: 2, y: 2}\nc:\n  <<: [*a, *b]\n")
        config, _ = Loader().load_file(str(path))
        assert config["c"] == {"x": 1, "y": 2}

    @pytest.mark.parametrize(
        "text,value",
        [("1e-3", 1e-3), ("1E5", 1e5), ("-2.5e-4", -2.5e-4), ("+1e3", 1e3), ("1.0e3", 1e3), (".5e1", 5.0)],
    )
    def test_exponent_floats(self, tmp_path, text, value):
        path = tmp_path / "floats.yaml"
        path.write_text(f"lr: {text}\n")
        config, _ = Loader().load_file(str(path))
        assert config["lr"] == value and isinstance(config["lr"], float)

    @pytest.mark.parametrize("text", ["1e", "e5", "1e3x", "'1e-3'", "0x1e", "._e3"])
    def test_non_floats_stay_as_before(self, tmp_path, text):
        path = tmp_path / "floats.yaml"
        path.write_text(f"v: {text}\n")
        config, _ = Loader().load_file(str(path))
        assert not isinstance(config["v"], float)


class TestLocationRegistry:
    """Test LocationRegistry functionality."""

    def test_create_registry(self):
        """Test creating empty registry."""
        registry = LocationRegistry()
        assert len(registry) == 0

    def test_register_and_get(self):
        """Test registering and getting source locations."""
        registry = LocationRegistry()
        location = Location(filepath="config.yaml", line=10, column=5, id="model::lr")

        registry.register("model::lr", location)

        retrieved = registry.get("model::lr")
        assert retrieved == location
        assert retrieved.line == 10

    def test_get_nonexistent_returns_none(self):
        """Test getting nonexistent location returns None."""
        registry = LocationRegistry()
        assert registry.get("nonexistent") is None

    def test_len(self):
        """Test registry length."""
        registry = LocationRegistry()
        location = Location(filepath="config.yaml", line=10, column=5, id="key")

        assert len(registry) == 0

        registry.register("key1", location)
        assert len(registry) == 1

        registry.register("key2", location)
        assert len(registry) == 2

    def test_contains(self):
        """Test __contains__ operator."""
        registry = LocationRegistry()
        location = Location(filepath="config.yaml", line=10, column=5, id="key")

        assert "key" not in registry

        registry.register("key", location)
        assert "key" in registry

    def test_merge(self):
        """Test merging registries."""
        registry1 = LocationRegistry()
        registry2 = LocationRegistry()

        location1 = Location(filepath="file1.yaml", line=5, column=2, id="key1")
        location2 = Location(filepath="file2.yaml", line=10, column=3, id="key2")

        registry1.register("key1", location1)
        registry2.register("key2", location2)

        registry1.merge(registry2)

        assert "key1" in registry1
        assert "key2" in registry1
        assert registry1.get("key2") == location2

    def test_copy(self):
        """Test copying registry."""
        registry = LocationRegistry()
        location = Location(filepath="config.yaml", line=10, column=5, id="key")

        registry.register("key", location)

        copied = registry.copy()

        assert len(copied) == len(registry)
        assert copied.get("key") == location

        # Ensure it's a real copy, not a reference
        location2 = Location(filepath="other.yaml", line=20, column=1, id="other")
        copied.register("other", location2)

        assert "other" in copied
        assert "other" not in registry
