from sparkwheel.check import CheckResult, check_config, format_check_result, format_config_ids, list_config_ids


class TestCheckResult:
    """Test CheckResult dataclass."""

    def test_is_valid_no_errors(self):
        """Test is_valid with no errors."""
        result = CheckResult(is_valid=True, errors=[], warnings=[])
        assert result.is_valid is True

    def test_is_valid_with_errors(self):
        """Test is_valid with errors."""
        result = CheckResult(is_valid=False, errors=["error1"], warnings=[])
        assert result.is_valid is False

    def test_summary_passed(self):
        """Test summary when check passed."""
        result = CheckResult(is_valid=True)
        assert result.summary() == "Check passed!"

    def test_summary_errors_only(self):
        """Test summary with only errors."""
        result = CheckResult(is_valid=False, errors=["e1", "e2"])
        assert "2 errors" in result.summary()

    def test_summary_warnings_only(self):
        """Test summary with only warnings."""
        result = CheckResult(is_valid=False, warnings=["w1"])
        assert "1 warning" in result.summary()

    def test_summary_errors_and_warnings(self):
        """Test summary with both errors and warnings."""
        result = CheckResult(is_valid=False, errors=["e1", "e2"], warnings=["w1"])
        summary = result.summary()
        assert "2 errors" in summary
        assert "1 warning" in summary


class TestCheckConfig:
    """Test check_config function."""

    def test_check_valid_config_dict(self):
        """Test checking a valid config dict."""
        config = {"model": {"lr": 0.001, "hidden_size": 512}}
        result = check_config(config)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_check_valid_config_file(self, tmp_path):
        """Test checking a valid config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("model:\n  lr: 0.001\n  hidden_size: 512")

        result = check_config(str(config_file))

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_check_invalid_yaml(self, tmp_path):
        """Test checking invalid YAML syntax."""
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("model:\n  lr: [unclosed")

        result = check_config(str(config_file))

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("syntax" in e.lower() for e in result.errors)

    def test_check_missing_reference(self):
        """Test checking config with missing reference."""
        config = {"model": {"lr": "@missing_ref"}}
        result = check_config(config)

        assert result.is_valid is False
        assert any("reference" in e.lower() for e in result.errors)

    def test_check_valid_reference(self):
        """Test checking config with valid reference."""
        config = {"base_lr": 0.001, "model": {"lr": "@base_lr"}}
        result = check_config(config)

        assert result.is_valid is True

    def test_check_circular_reference(self):
        """Test checking config with circular reference."""
        config = {"a": "@b", "b": "@c", "c": "@a"}
        result = check_config(config, strict=False)

        # Should have warning but not error
        assert len(result.warnings) > 0 or len(result.errors) > 0

    def test_check_circular_reference_strict(self):
        """Test checking config with circular reference in strict mode."""
        config = {"a": "@b", "b": "@c", "c": "@a"}
        result = check_config(config, strict=True)

        # In strict mode, warnings become errors
        assert result.is_valid is False

    def test_check_valid_expression(self):
        """Test checking config with valid expression."""
        config = {"model": {"size": "$256 * 2"}}
        result = check_config(config)

        assert result.is_valid is True
        assert result.num_expressions > 0

    def test_check_invalid_expression(self):
        """Test checking config with invalid expression."""
        config = {"model": {"size": "$undefined_variable"}}  # Undefined variable
        result = check_config(config)

        # Should have at least one error (might be syntax error, eval error, etc.)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_check_count_references(self):
        """Test that check_config counts references correctly."""
        config = {"a": 1, "b": "@a", "c": "@a", "d": "@b"}
        result = check_config(config)

        assert result.num_references >= 3

    def test_check_count_expressions(self):
        """Test that check_config counts expressions correctly."""
        config = {"a": "$1 + 1", "b": "$2 + 2", "c": 3}
        result = check_config(config)

        assert result.num_expressions >= 2

    def test_check_count_components(self):
        """Test that check_config counts components correctly."""
        config = {
            "model": {"_target_": "dict", "size": 512},
            "optimizer": {"_target_": "dict", "lr": 0.001},
            "plain": {"value": 42},
        }
        result = check_config(config)

        assert result.num_components >= 2

    def test_check_specific_path(self):
        """Test checking specific path within config."""
        config = {
            "model": {"lr": 0.001},
            "broken": {"ref": "@nonexistent"},
        }

        # Check only model path - should pass
        result = check_config(config, check_path="model")
        assert result.is_valid is True

        # Check entire config - should fail
        result_full = check_config(config)
        assert result_full.is_valid is False

    def test_check_populates_config_ids(self):
        """Test that check_config populates config_ids."""
        config = {"model": {"lr": 0.001, "size": 512}, "training": {"epochs": 100}}
        result = check_config(config)

        assert len(result.config_ids) > 0
        assert any("model" in id_str for id_str in result.config_ids)


class TestListConfigIds:
    """Test list_config_ids function."""

    def test_list_ids_grouped(self):
        """Test listing IDs grouped by section."""
        config = {"model": {"lr": 0.001, "size": 512}, "training": {"epochs": 100}}
        ids = list_config_ids(config, group_by_section=True)

        assert isinstance(ids, dict)
        assert "model" in ids
        assert "training" in ids

    def test_list_ids_flat(self):
        """Test listing IDs as flat list."""
        config = {"model": {"lr": 0.001}, "training": {"epochs": 100}}
        ids = list_config_ids(config, group_by_section=False)

        assert isinstance(ids, list)
        assert any("model" in id_str for id_str in ids)
        assert any("training" in id_str for id_str in ids)

    def test_list_ids_from_file(self, tmp_path):
        """Test listing IDs from file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("model:\n  lr: 0.001\n  size: 512")

        ids = list_config_ids(str(config_file))

        assert isinstance(ids, dict)
        assert "model" in ids

    def test_list_ids_nested(self):
        """Test listing IDs with nested config."""
        config = {
            "model": {"optimizer": {"lr": 0.001, "momentum": 0.9}, "layers": 3},
        }
        ids = list_config_ids(config, group_by_section=False)

        assert isinstance(ids, list)
        # Should have nested IDs
        assert any("optimizer::lr" in id_str for id_str in ids)


class TestFormatCheckResult:
    """Test format_check_result function."""

    def test_format_success(self):
        """Test formatting successful check result."""
        result = CheckResult(
            is_valid=True,
            num_references=5,
            num_expressions=2,
            num_components=3,
        )

        output = format_check_result(result, filepath="config.yaml")

        assert "✓" in output or "Checking config.yaml" in output
        assert "YAML syntax valid" in output
        assert "Check passed!" in output

    def test_format_with_errors(self):
        """Test formatting check result with errors."""
        result = CheckResult(
            is_valid=False,
            errors=["Reference resolution failed: missing key"],
            num_references=5,
        )

        output = format_check_result(result, filepath="config.yaml")

        assert "✗" in output or "failed" in output.lower()
        assert "Reference resolution failed" in output

    def test_format_verbose(self):
        """Test formatting with verbose flag."""
        result = CheckResult(
            is_valid=True,
            num_references=5,
            num_expressions=2,
            num_components=3,
        )

        output = format_check_result(result, verbose=True)

        # Verbose should show counts
        assert "5 references" in output or "2 expressions" in output or "3 components" in output

    def test_format_with_warnings(self):
        """Test formatting check result with warnings."""
        result = CheckResult(
            is_valid=True,
            warnings=["Circular dependency detected"],
        )

        output = format_check_result(result)

        assert "Circular dependency" in output


class TestFormatConfigIds:
    """Test format_config_ids function."""

    def test_format_grouped_ids(self):
        """Test formatting grouped IDs."""
        ids = {
            "model": ["model", "model::lr", "model::size"],
            "training": ["training", "training::epochs"],
        }

        output = format_config_ids(ids, filepath="config.yaml")

        assert "Configuration IDs in config.yaml" in output
        assert "model" in output
        assert "training" in output
        assert "Total:" in output

    def test_format_flat_ids(self):
        """Test formatting flat ID list."""
        ids = ["model", "model::lr", "training", "training::epochs"]

        output = format_config_ids(ids)

        assert "Configuration IDs" in output
        assert "model" in output
        assert "Total:" in output


class TestCheckIntegration:
    """Integration tests for check functionality."""

    def test_full_check_workflow(self, tmp_path):
        """Test complete check workflow."""
        # Create config with various features
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
base_lr: 0.001

model:
  _target_: dict
  hidden_size: 512
  lr: '@base_lr'
  size: '$512 * 2'

training:
  epochs: 100
  device: cuda
""")

        # Run check
        result = check_config(str(config_file))

        # Should pass all checks
        assert result.is_valid is True
        assert result.num_references > 0
        assert result.num_expressions > 0
        assert result.num_components > 0

        # Test formatting
        output = format_check_result(result, filepath=str(config_file), verbose=True)
        assert "Check passed!" in output

        # Test listing IDs
        ids = list_config_ids(str(config_file))
        assert "model" in ids
        assert "training" in ids

    def test_check_with_multiple_errors(self, tmp_path):
        """Test check with multiple types of errors."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
model:
  lr: '@nonexistent'
  size: '$invalid syntax here'

training:
  ref: '@missing'
""")

        result = check_config(str(config_file))

        # Should fail with multiple errors
        assert result.is_valid is False
        assert len(result.errors) >= 2

        # Format output
        output = format_check_result(result, filepath=str(config_file))
        assert "Check failed" in output

    def test_check_empty_config(self):
        """Test checking empty config."""
        result = check_config({})

        # Empty config should be valid
        assert result.is_valid is True
        assert len(result.config_ids) == 0
