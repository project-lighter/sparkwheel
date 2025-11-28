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


class TestPreprocessorExternalOnly:
    """Test external_only parameter for two-phase raw reference expansion."""

    def test_external_only_expands_external_refs(self, tmp_path):
        """Test that external_only=True expands external file refs."""
        external_file = tmp_path / "external.yaml"
        external_file.write_text("value: 42")

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config = {"external_ref": f"%{external_file}::value", "local_ref": "%local_key", "local_key": 100}

        result = preprocessor.process_raw_refs(config, config, external_only=True)

        # External ref should be expanded
        assert result["external_ref"] == 42
        # Local ref should remain as string
        assert result["local_ref"] == "%local_key"
        # Local key unchanged
        assert result["local_key"] == 100

    def test_external_only_false_expands_all_refs(self, tmp_path):
        """Test that external_only=False expands all refs including local."""
        external_file = tmp_path / "external.yaml"
        external_file.write_text("value: 42")

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config = {"external_ref": f"%{external_file}::value", "local_ref": "%local_key", "local_key": 100}

        result = preprocessor.process_raw_refs(config, config, external_only=False)

        # Both should be expanded
        assert result["external_ref"] == 42
        assert result["local_ref"] == 100

    def test_two_phase_expansion_with_override(self, tmp_path):
        """Test that two-phase expansion allows overrides to affect local refs."""
        external_file = tmp_path / "external.yaml"
        external_file.write_text("external_value: 1")

        loader = Loader()
        preprocessor = Preprocessor(loader)

        # Initial config with both external and local refs
        config = {
            "external_ref": f"%{external_file}::external_value",
            "local_ref": "%vars::value",
            "vars": {"value": None},  # Will be overridden
        }

        # Phase 1: Expand only external refs
        config = preprocessor.process_raw_refs(config, config, external_only=True)
        assert config["external_ref"] == 1
        assert config["local_ref"] == "%vars::value"  # Still string

        # Simulate CLI override
        config["vars"]["value"] = "/data/features.npz"

        # Phase 2: Expand local refs (now sees override)
        config = preprocessor.process_raw_refs(config, config, external_only=False)
        assert config["local_ref"] == "/data/features.npz"

    def test_nested_local_refs_expanded_together(self, tmp_path):
        """Test that nested local refs are all expanded in phase 2."""
        loader = Loader()
        preprocessor = Preprocessor(loader)

        config = {"a": {"b": {"c": 42}}, "ref_to_b": "%a::b", "ref_to_c": "%a::b::c"}

        # Phase 1: Nothing to expand (no external refs)
        result = preprocessor.process_raw_refs(config, config, external_only=True)
        assert result["ref_to_b"] == "%a::b"
        assert result["ref_to_c"] == "%a::b::c"

        # Phase 2: Expand all local refs
        result = preprocessor.process_raw_refs(result, result, external_only=False)
        assert result["ref_to_b"] == {"c": 42}
        assert result["ref_to_c"] == 42

    def test_external_ref_within_local_ref_expanded_correctly(self, tmp_path):
        """Test that external refs within locally-referenced values are expanded."""
        external_file = tmp_path / "external.yaml"
        external_file.write_text("nested:\n  value: 99")

        loader = Loader()
        preprocessor = Preprocessor(loader)

        config = {
            "template": {"external": f"%{external_file}::nested"},
            "copy": "%template",
        }

        # Phase 1: Expand external ref inside template
        result = preprocessor.process_raw_refs(config, config, external_only=True)
        assert result["template"]["external"] == {"value": 99}
        assert result["copy"] == "%template"  # Local ref still string

        # Phase 2: Expand local ref - should get the already-expanded template
        result = preprocessor.process_raw_refs(result, result, external_only=False)
        assert result["copy"] == {"external": {"value": 99}}
