"""Tests for the YAML loader module."""

import pytest

from sparkwheel.loader import Loader
from sparkwheel.metadata import MetadataRegistry
from sparkwheel.utils.exceptions import SourceLocation


class TestLoaderBasic:
    """Test basic Loader functionality."""

    def test_load_file_basic(self, tmp_path):
        """Test loading a basic YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\nnumber: 42")

        loader = Loader()
        config, metadata = loader.load_file(str(config_file))

        assert config == {"key": "value", "number": 42}
        assert isinstance(metadata, MetadataRegistry)

    def test_load_file_empty_filepath(self):
        """Test loading with empty filepath returns empty config."""
        loader = Loader()
        config, metadata = loader.load_file("")

        assert config == {}
        assert isinstance(metadata, MetadataRegistry)

    def test_load_file_none_filepath(self):
        """Test loading with None filepath returns empty config."""
        loader = Loader()
        config, metadata = loader.load_file(None)

        assert config == {}
        assert isinstance(metadata, MetadataRegistry)

    def test_load_file_non_yaml_extension(self, tmp_path):
        """Test loading non-YAML file raises ValueError."""
        config_file = tmp_path / "config.txt"
        config_file.write_text("key: value")

        loader = Loader()
        with pytest.raises(ValueError, match="must be a YAML file"):
            loader.load_file(str(config_file))

    def test_load_file_with_path_traversal(self, tmp_path):
        """Test loading file with path traversal shows warning."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value")

        loader = Loader()
        # Use a path with ".." to trigger path traversal warning
        path_with_traversal = str(tmp_path / ".." / tmp_path.name / "config.yaml")

        with pytest.warns(UserWarning, match="path contains '..'"):
            config, metadata = loader.load_file(path_with_traversal)

        assert config == {"key": "value"}

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


class TestLoaderMultipleFiles:
    """Test loading multiple YAML files."""

    def test_load_files_basic(self, tmp_path):
        """Test loading multiple files."""
        file1 = tmp_path / "config1.yaml"
        file1.write_text("key1: value1\nshared: from_file1")

        file2 = tmp_path / "config2.yaml"
        file2.write_text("key2: value2\nshared: from_file2")

        loader = Loader()
        config, metadata = loader.load_files([str(file1), str(file2)])

        # Later files should override earlier files
        assert config["key1"] == "value1"
        assert config["key2"] == "value2"
        assert config["shared"] == "from_file2"

    def test_load_files_empty_list(self):
        """Test loading empty file list."""
        loader = Loader()
        config, metadata = loader.load_files([])

        assert config == {}
        assert isinstance(metadata, MetadataRegistry)

    def test_load_files_single_file(self, tmp_path):
        """Test loading single file via load_files."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value")

        loader = Loader()
        config, metadata = loader.load_files([str(config_file)])

        assert config == {"key": "value"}

    def test_load_files_metadata_merged(self, tmp_path):
        """Test that metadata is merged from multiple files."""
        file1 = tmp_path / "config1.yaml"
        file1.write_text("key1: value1")

        file2 = tmp_path / "config2.yaml"
        file2.write_text("key2: value2")

        loader = Loader()
        config, metadata = loader.load_files([str(file1), str(file2)])

        # Both files should have metadata tracked
        assert metadata.get("") is not None


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


class TestMetadataRegistry:
    """Test MetadataRegistry functionality."""

    def test_create_registry(self):
        """Test creating empty registry."""
        registry = MetadataRegistry()
        assert len(registry) == 0

    def test_register_and_get(self):
        """Test registering and getting source locations."""
        registry = MetadataRegistry()
        location = SourceLocation(filepath="config.yaml", line=10, column=5, id="model::lr")

        registry.register("model::lr", location)

        retrieved = registry.get("model::lr")
        assert retrieved == location
        assert retrieved.line == 10

    def test_get_nonexistent_returns_none(self):
        """Test getting nonexistent location returns None."""
        registry = MetadataRegistry()
        assert registry.get("nonexistent") is None

    def test_len(self):
        """Test registry length."""
        registry = MetadataRegistry()
        location = SourceLocation(filepath="config.yaml", line=10, column=5, id="key")

        assert len(registry) == 0

        registry.register("key1", location)
        assert len(registry) == 1

        registry.register("key2", location)
        assert len(registry) == 2

    def test_contains(self):
        """Test __contains__ operator."""
        registry = MetadataRegistry()
        location = SourceLocation(filepath="config.yaml", line=10, column=5, id="key")

        assert "key" not in registry

        registry.register("key", location)
        assert "key" in registry

    def test_merge(self):
        """Test merging registries."""
        registry1 = MetadataRegistry()
        registry2 = MetadataRegistry()

        location1 = SourceLocation(filepath="file1.yaml", line=5, column=2, id="key1")
        location2 = SourceLocation(filepath="file2.yaml", line=10, column=3, id="key2")

        registry1.register("key1", location1)
        registry2.register("key2", location2)

        registry1.merge(registry2)

        assert "key1" in registry1
        assert "key2" in registry1
        assert registry1.get("key2") == location2

    def test_copy(self):
        """Test copying registry."""
        registry = MetadataRegistry()
        location = SourceLocation(filepath="config.yaml", line=10, column=5, id="key")

        registry.register("key", location)

        copied = registry.copy()

        assert len(copied) == len(registry)
        assert copied.get("key") == location

        # Ensure it's a real copy, not a reference
        location2 = SourceLocation(filepath="other.yaml", line=20, column=1, id="other")
        copied.register("other", location2)

        assert "other" in copied
        assert "other" not in registry
