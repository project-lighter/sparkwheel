"""Tests for the preprocessor module."""

import pytest

from sparkwheel.loader import Loader
from sparkwheel.preprocessor import Preprocessor
from sparkwheel.utils.exceptions import CircularReferenceError, ConfigKeyError


class TestPreprocessor:
    """Test Preprocessor functionality."""

    def test_circular_raw_reference(self, tmp_path):
        """Test detection of circular raw references."""
        config_file = tmp_path / "config.yaml"
        # Use quotes to prevent YAML from interpreting % as alias
        config_file.write_text('a: "%b"\nb: "%a"')

        loader = Loader()
        preprocessor = Preprocessor(loader)

        # Load the config and try to process it
        config, locations = loader.load_file(str(config_file))

        with pytest.raises(CircularReferenceError, match="Circular raw reference detected"):
            preprocessor.process_raw_refs(config, config, locations=locations)

    def test_raw_ref_missing_key_with_location(self, tmp_path):
        """Test raw reference error includes source location."""
        # Create a config file with a raw reference to a missing key
        config_file = tmp_path / "config.yaml"
        config_file.write_text('value: "%missing::key"')

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config, locations = loader.load_file(str(config_file))

        with pytest.raises(ConfigKeyError) as exc_info:
            preprocessor.process_raw_refs(config, config, locations=locations)

        error = exc_info.value
        assert error.source_location is not None
        assert error.source_location.filepath == str(config_file)
        assert error.source_location.line == 1
        assert "Error resolving raw reference" in error._original_message
        assert "Key 'missing' not found" in error._original_message

    def test_raw_ref_external_file_missing_key(self, tmp_path):
        """Test raw reference to external file with missing key."""
        # Create external file
        external_file = tmp_path / "external.yaml"
        external_file.write_text("foo: 1\nbar: 2")

        # Create main config that references missing key in external file
        config_file = tmp_path / "config.yaml"
        config_file.write_text(f'value: "%{external_file}::missing"')

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config, locations = loader.load_file(str(config_file))

        with pytest.raises(ConfigKeyError) as exc_info:
            preprocessor.process_raw_refs(config, config, locations=locations)

        error = exc_info.value
        assert error.source_location is not None
        assert error.source_location.filepath == str(config_file)
        assert f"from '{external_file}'" in error._original_message
        assert "Key 'missing' not found" in error._original_message

    def test_raw_ref_nested_missing_key(self, tmp_path):
        """Test raw reference with nested path where middle key is missing."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text('data:\n  foo: 1\nvalue: "%data::missing::key"')

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config, locations = loader.load_file(str(config_file))

        with pytest.raises(ConfigKeyError) as exc_info:
            preprocessor.process_raw_refs(config, config, locations=locations)

        error = exc_info.value
        assert "Key 'missing' not found in 'data'" in error._original_message

    def test_circular_reference_with_location(self, tmp_path):
        """Test circular reference error includes source location."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text('a: "%b"\nb: "%a"')

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config, locations = loader.load_file(str(config_file))

        with pytest.raises(CircularReferenceError) as exc_info:
            preprocessor.process_raw_refs(config, config, locations=locations)

        error = exc_info.value
        assert error.source_location is not None
        assert error.source_location.filepath == str(config_file)
        assert "Reference chain:" in error._original_message

    def test_raw_ref_expansion_success(self, tmp_path):
        """Test successful raw reference expansion."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text('base_lr: 0.001\nmodel:\n  lr: "%base_lr"')

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config, locations = loader.load_file(str(config_file))
        result = preprocessor.process_raw_refs(config, config, locations=locations)

        assert result["model"]["lr"] == 0.001

    def test_raw_ref_nested_expansion(self, tmp_path):
        """Test nested raw reference expansion."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text('a:\n  b:\n    c: 42\nvalue: "%a::b::c"')

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config, locations = loader.load_file(str(config_file))
        result = preprocessor.process_raw_refs(config, config, locations=locations)

        assert result["value"] == 42

    def test_raw_ref_external_file_success(self, tmp_path):
        """Test successful raw reference from external file."""
        external_file = tmp_path / "base.yaml"
        external_file.write_text("learning_rate: 0.001")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(f'lr: "%{external_file}::learning_rate"')

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config, locations = loader.load_file(str(config_file))
        result = preprocessor.process_raw_refs(config, config, locations=locations)

        assert result["lr"] == 0.001
