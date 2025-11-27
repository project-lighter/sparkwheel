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

    def test_get_by_id_empty_id(self):
        """Test _get_by_id with empty ID returns whole config."""
        config = {"key": "value", "nested": {"item": 123}}
        result = Preprocessor._get_by_id(config, "")

        assert result == config

    def test_get_by_id_list_indexing(self):
        """Test _get_by_id with list indexing."""
        config = {"items": [10, 20, 30]}
        result = Preprocessor._get_by_id(config, "items::1")

        assert result == 20

    def test_get_by_id_nested_list(self):
        """Test _get_by_id with nested structures including lists."""
        config = {"data": {"values": [{"x": 1}, {"x": 2}, {"x": 3}]}}
        result = Preprocessor._get_by_id(config, "data::values::2::x")

        assert result == 3

    def test_get_by_id_type_error_on_primitive(self):
        """Test _get_by_id raises TypeError when trying to index a primitive value."""
        config = {"value": 42}

        with pytest.raises(TypeError, match="Cannot index int"):
            Preprocessor._get_by_id(config, "value::subkey")

    def test_get_by_id_missing_key_first_level(self):
        """Test _get_by_id with missing key at first level shows non-redundant error."""
        config = {"foo": 1, "bar": 2}

        with pytest.raises(KeyError) as exc_info:
            Preprocessor._get_by_id(config, "missing")

        error_msg = str(exc_info.value)
        assert "Key 'missing' not found" in error_msg
        assert "Available keys:" in error_msg
        assert "'foo'" in error_msg
        assert "'bar'" in error_msg
        # Should NOT say "at path 'missing'" for first level
        assert "at path" not in error_msg

    def test_get_by_id_missing_key_nested(self):
        """Test _get_by_id with missing nested key shows parent path."""
        config = {"data": {"train": {"lr": 0.001, "epochs": 10}}}

        with pytest.raises(KeyError) as exc_info:
            Preprocessor._get_by_id(config, "data::train::missing")

        error_msg = str(exc_info.value)
        assert "Key 'missing' not found in 'data::train'" in error_msg
        assert "Available keys:" in error_msg
        assert "'lr'" in error_msg
        assert "'epochs'" in error_msg

    def test_get_by_id_invalid_list_index(self):
        """Test _get_by_id with invalid list index."""
        config = {"items": [1, 2, 3]}

        with pytest.raises(KeyError) as exc_info:
            Preprocessor._get_by_id(config, "items::10")

        error_msg = str(exc_info.value)
        assert "Invalid list index '10' in 'items'" in error_msg

    def test_get_by_id_invalid_list_index_first_level(self):
        """Test _get_by_id with invalid list index at first level."""
        config = [1, 2, 3]

        with pytest.raises(KeyError) as exc_info:
            Preprocessor._get_by_id(config, "10")

        error_msg = str(exc_info.value)
        assert "Invalid list index '10'" in error_msg
        # Should not mention parent path for first level
        assert "in '" not in error_msg or "in '10'" not in error_msg

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

    def test_type_error_first_level(self):
        """Test type error at first level shows clean message."""
        config = "string_value"

        with pytest.raises(TypeError) as exc_info:
            Preprocessor._get_by_id(config, "foo")

        error_msg = str(exc_info.value)
        assert "Cannot index str with key 'foo'" in error_msg
        # Should not mention parent path for first level
        assert "(in " not in error_msg

    def test_type_error_nested(self):
        """Test type error in nested path shows parent."""
        config = {"data": {"value": 42}}

        with pytest.raises(TypeError) as exc_info:
            Preprocessor._get_by_id(config, "data::value::foo")

        error_msg = str(exc_info.value)
        assert "Cannot index int with key 'foo'" in error_msg
        assert "(in 'data::value')" in error_msg

    def test_available_keys_truncated(self):
        """Test that available keys list is truncated when > 10 keys."""
        config = {f"key_{i}": i for i in range(20)}

        with pytest.raises(KeyError) as exc_info:
            Preprocessor._get_by_id(config, "missing")

        error_msg = str(exc_info.value)
        assert "Available keys:" in error_msg
        assert "..." in error_msg  # Should be truncated

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
