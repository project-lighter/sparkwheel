"""Tests for the preprocessor module."""

import pytest

from sparkwheel.loader import Loader
from sparkwheel.preprocessor import Preprocessor


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
        config, _ = loader.load_file(str(config_file))

        with pytest.raises(ValueError, match="Circular raw reference detected"):
            preprocessor.process(config, config)

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
