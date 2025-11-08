"""
Tests for CLI utilities.

Tests the CLI parsing functions and Config.from_cli() method.
"""

import pytest

from sparkwheel import Config
from sparkwheel.cli import parse_override, parse_overrides


class TestParseOverride:
    """Test parse_override function."""

    def test_parse_int(self):
        """Test parsing integer value."""
        key, value = parse_override("trainer::max_epochs=100")
        assert key == "trainer::max_epochs"
        assert value == 100
        assert isinstance(value, int)

    def test_parse_float(self):
        """Test parsing float value."""
        key, value = parse_override("model::lr=0.001")
        assert key == "model::lr"
        assert value == 0.001
        assert isinstance(value, float)

    def test_parse_string(self):
        """Test parsing string value (no quotes needed on CLI)."""
        key, value = parse_override("model::name=resnet50")
        assert key == "model::name"
        assert value == "resnet50"
        assert isinstance(value, str)

    def test_parse_bool_true(self):
        """Test parsing True boolean."""
        key, value = parse_override("trainer::fast_dev_run=True")
        assert key == "trainer::fast_dev_run"
        assert value is True

    def test_parse_bool_false(self):
        """Test parsing False boolean."""
        key, value = parse_override("debug=False")
        assert key == "debug"
        assert value is False

    def test_parse_none(self):
        """Test parsing None value."""
        key, value = parse_override("model::scheduler=None")
        assert key == "model::scheduler"
        assert value is None

    def test_parse_list(self):
        """Test parsing list value."""
        key, value = parse_override("trainer::devices=[0,1,2]")
        assert key == "trainer::devices"
        assert value == [0, 1, 2]
        assert isinstance(value, list)

    def test_parse_nested_list(self):
        """Test parsing nested list."""
        key, value = parse_override("model::layers=[[64,128],[256,512]]")
        assert key == "model::layers"
        assert value == [[64, 128], [256, 512]]

    def test_parse_dict(self):
        """Test parsing dict value."""
        key, value = parse_override("model::config={'a':1,'b':2}")
        assert key == "model::config"
        assert value == {"a": 1, "b": 2}
        assert isinstance(value, dict)

    def test_parse_tuple(self):
        """Test parsing tuple value."""
        key, value = parse_override("model::shape=(224,224)")
        assert key == "model::shape"
        assert value == (224, 224)
        assert isinstance(value, tuple)

    def test_nested_path(self):
        """Test deeply nested path with multiple :: separators."""
        key, value = parse_override("system::model::optimizer::lr=0.001")
        assert key == "system::model::optimizer::lr"
        assert value == 0.001

    def test_simple_key(self):
        """Test simple key without nesting."""
        key, value = parse_override("debug=True")
        assert key == "debug"
        assert value is True

    def test_value_with_equals(self):
        """Test value containing equals sign."""
        key, value = parse_override("math::equation=x=y+1")
        assert key == "math::equation"
        assert value == "x=y+1"  # Everything after first = is the value

    def test_invalid_format_no_equals(self):
        """Test error on invalid format (no equals sign)."""
        with pytest.raises(ValueError, match="Invalid override format"):
            parse_override("model::lr")

    def test_invalid_format_empty(self):
        """Test error on empty string."""
        with pytest.raises(ValueError, match="Invalid override format"):
            parse_override("")

    def test_string_with_spaces(self):
        """Test string with spaces."""
        key, value = parse_override("model::name=ResNet 50")
        assert key == "model::name"
        assert value == "ResNet 50"


class TestParseOverrides:
    """Test parse_overrides function."""

    def test_parse_multiple(self):
        """Test parsing multiple overrides."""
        overrides = parse_overrides(["model::lr=0.001", "trainer::max_epochs=100", "trainer::devices=[0,1]"])

        assert overrides == {"model::lr": 0.001, "trainer::max_epochs": 100, "trainer::devices": [0, 1]}

    def test_parse_mixed_types(self):
        """Test parsing various types in one call."""
        overrides = parse_overrides(
            [
                "model::name=resnet50",
                "model::layers=[64,128,256]",
                "trainer::devices=[0,1]",
                "debug=True",
                "model::lr=0.001",
                "scheduler=None",
            ]
        )

        assert overrides == {
            "model::name": "resnet50",
            "model::layers": [64, 128, 256],
            "trainer::devices": [0, 1],
            "debug": True,
            "model::lr": 0.001,
            "scheduler": None,
        }

    def test_parse_empty_list(self):
        """Test parsing empty list of overrides."""
        overrides = parse_overrides([])
        assert overrides == {}

    def test_parse_single_override(self):
        """Test parsing single override in list."""
        overrides = parse_overrides(["model::lr=0.001"])
        assert overrides == {"model::lr": 0.001}

    def test_duplicate_keys_last_wins(self):
        """Test that last value wins for duplicate keys."""
        overrides = parse_overrides(
            [
                "model::lr=0.001",
                "model::lr=0.01",  # Overwrites previous
            ]
        )
        assert overrides == {"model::lr": 0.01}


class TestConfigFromCLI:
    """Test Config.from_cli() method."""

    def test_from_cli_basic(self):
        """Test basic loading with CLI overrides."""
        base_config = {"model": {"lr": 0.01, "hidden_size": 256}, "trainer": {"max_epochs": 10}}

        config = Config.from_cli(base_config, ["model::lr=0.001", "trainer::max_epochs=100"])

        assert config["model::lr"] == 0.001
        assert config["model::hidden_size"] == 256  # Unchanged
        assert config["trainer::max_epochs"] == 100

    def test_from_cli_no_overrides(self):
        """Test loading without overrides."""
        base_config = {"model": {"lr": 0.01}}

        config = Config.from_cli(base_config, [])

        assert config["model::lr"] == 0.01

    def test_from_cli_empty_overrides_list(self):
        """Test with empty overrides list."""
        config = Config.from_cli({"value": 42}, [])
        assert config["value"] == 42

    def test_from_cli_new_keys(self):
        """Test adding new keys via CLI overrides."""
        base_config = {"model": {"lr": 0.01}}

        config = Config.from_cli(base_config, ["model::dropout=0.1", "trainer::max_epochs=100"])

        assert config["model::lr"] == 0.01
        assert config["model::dropout"] == 0.1
        assert config["trainer::max_epochs"] == 100

    def test_from_cli_complex_types(self):
        """Test CLI overrides with complex types."""
        config = Config.from_cli(
            {"model": {}},
            ["model::layers=[128,256,512]", "model::config={'dropout':0.1,'activation':'relu'}", "trainer::devices=[0,1,2,3]"],
        )

        assert config["model::layers"] == [128, 256, 512]
        assert config["model::config"] == {"dropout": 0.1, "activation": "relu"}
        assert config["trainer::devices"] == [0, 1, 2, 3]

    def test_from_cli_with_schema(self):
        """Test loading with schema validation."""
        from dataclasses import dataclass

        @dataclass
        class SimpleSchema:
            value: int

        config = Config.from_cli({"value": 42}, ["value=100"], schema=SimpleSchema)

        assert config["value"] == 100

    def test_from_cli_schema_validation_fails(self):
        """Test that invalid override fails schema validation."""
        from dataclasses import dataclass

        from sparkwheel import ValidationError

        @dataclass
        class SimpleSchema:
            value: int

        with pytest.raises(ValidationError):
            Config.from_cli(
                {"value": 42},
                ["value=not_an_int"],  # Type error!
                schema=SimpleSchema,
            )

    def test_from_cli_multiple_files(self):
        """Test loading from multiple files with overrides."""
        # Create temp config files
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            base_file = os.path.join(tmpdir, "base.yaml")
            override_file = os.path.join(tmpdir, "override.yaml")

            with open(base_file, "w") as f:
                f.write("model:\n  lr: 0.01\n  hidden_size: 256\n")

            with open(override_file, "w") as f:
                f.write("+model:\n  lr: 0.001\n")

            config = Config.from_cli([base_file, override_file], ["model::dropout=0.1"])

            assert config["model::lr"] == 0.001  # From override file
            assert config["model::hidden_size"] == 256  # From base
            assert config["model::dropout"] == 0.1  # From CLI

    def test_from_cli_with_references(self):
        """Test that references work with CLI overrides."""
        base_config = {"base_lr": 0.01, "model": {"lr": "@base_lr", "dropout": 0.1}}

        config = Config.from_cli(base_config, ["base_lr=0.001", "model::dropout=0.2"])

        # Test raw values
        assert config.get("base_lr") == 0.001
        assert config.get("model::dropout") == 0.2

        # Test resolved values
        resolved = config.resolve()
        assert resolved["model"]["lr"] == 0.001  # Resolved reference
        assert resolved["model"]["dropout"] == 0.2

    def test_from_cli_preserves_globals(self):
        """Test that globals are preserved."""
        config = Config.from_cli(
            {"expr": "$len([1,2,3])"},
            [],
            globals={},  # Empty but should still work
        )

        resolved = config.resolve()
        assert resolved["expr"] == 3


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def test_realistic_ml_config(self):
        """Test realistic machine learning configuration."""
        base_config = {
            "model": {"name": "resnet50", "pretrained": True, "num_classes": 1000},
            "training": {"batch_size": 32, "epochs": 100, "lr": 0.001, "optimizer": "adam"},
            "data": {"train_path": "/data/train", "val_path": "/data/val"},
        }

        config = Config.from_cli(
            base_config,
            [
                "model::name=resnet101",
                "model::num_classes=10",
                "training::batch_size=64",
                "training::lr=0.0001",
                "training::epochs=50",
            ],
        )

        # Check overrides applied
        assert config["model::name"] == "resnet101"
        assert config["model::num_classes"] == 10
        assert config["training::batch_size"] == 64
        assert config["training::lr"] == 0.0001
        assert config["training::epochs"] == 50

        # Check unchanged values
        assert config["model::pretrained"] is True
        assert config["data::train_path"] == "/data/train"

    def test_override_with_expressions(self):
        """Test CLI overrides with expressions."""
        config = Config.from_cli(
            {"batch_size": 32, "num_batches": 100, "total_samples": "$@batch_size * @num_batches"}, ["batch_size=64"]
        )

        resolved = config.resolve()
        assert resolved["total_samples"] == 6400  # 64 * 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
