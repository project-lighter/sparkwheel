import pytest

from sparkwheel import ConfigParser
from sparkwheel.errors import (
    enable_colors,
    format_available_keys,
    format_suggestions,
    get_suggestions,
    levenshtein_distance,
)
from sparkwheel.exceptions import ConfigKeyError


class TestLevenshteinDistance:
    """Test Levenshtein distance calculation."""

    def test_identical_strings(self):
        """Test distance between identical strings."""
        assert levenshtein_distance("hello", "hello") == 0

    def test_single_substitution(self):
        """Test distance with single character substitution."""
        assert levenshtein_distance("hello", "hallo") == 1

    def test_single_insertion(self):
        """Test distance with single character insertion."""
        assert levenshtein_distance("hello", "helo") == 1

    def test_single_deletion(self):
        """Test distance with single character deletion."""
        assert levenshtein_distance("hello", "helloo") == 1

    def test_multiple_operations(self):
        """Test distance with multiple operations."""
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_empty_strings(self):
        """Test distance with empty strings."""
        assert levenshtein_distance("", "") == 0
        assert levenshtein_distance("hello", "") == 5
        assert levenshtein_distance("", "world") == 5


class TestGetSuggestions:
    """Test smart suggestion generation."""

    def test_close_match(self):
        """Test finding close matches."""
        available = ["parameters", "param_groups", "learning_rate"]
        suggestions = get_suggestions("paramters", available)

        # Should suggest "parameters" with high similarity
        assert len(suggestions) > 0
        assert suggestions[0][0] == "parameters"
        assert suggestions[0][1] > 0.8

    def test_multiple_suggestions(self):
        """Test getting multiple ranked suggestions."""
        available = ["optimizer", "optimiser", "optimize"]
        suggestions = get_suggestions("optimzer", available, max_suggestions=3)

        # Should return suggestions sorted by similarity
        assert len(suggestions) <= 3
        # First should have highest similarity
        if len(suggestions) > 1:
            assert suggestions[0][1] >= suggestions[1][1]

    def test_no_matches_below_threshold(self):
        """Test that poor matches are filtered out."""
        available = ["apple", "banana", "cherry"]
        suggestions = get_suggestions("zebra", available, similarity_threshold=0.6)

        # "zebra" is too different from fruit names
        assert len(suggestions) == 0

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        available = ["Learning_Rate", "BATCH_SIZE"]
        suggestions = get_suggestions("learning_rate", available)

        assert len(suggestions) > 0
        assert suggestions[0][0] == "Learning_Rate"

    def test_empty_inputs(self):
        """Test with empty inputs."""
        assert get_suggestions("", ["a", "b"]) == []
        assert get_suggestions("test", []) == []


class TestFormatSuggestions:
    """Test suggestion formatting."""

    def test_format_with_high_similarity(self):
        """Test formatting suggestions with high similarity (checkmark)."""
        suggestions = [("parameters", 0.9)]
        formatted = format_suggestions(suggestions)

        assert "parameters" in formatted
        assert "✓" in formatted
        assert "90% match" in formatted
        assert "💡 Did you mean" in formatted

    def test_format_with_low_similarity(self):
        """Test formatting suggestions with lower similarity (no checkmark)."""
        suggestions = [("param_groups", 0.65)]
        formatted = format_suggestions(suggestions)

        assert "param_groups" in formatted
        assert "65% match" in formatted
        assert "✓" not in formatted  # No checkmark for <80%

    def test_format_multiple_suggestions(self):
        """Test formatting multiple suggestions."""
        suggestions = [("parameters", 0.9), ("param_groups", 0.65), ("parametrize", 0.55)]
        formatted = format_suggestions(suggestions)

        assert "parameters" in formatted
        assert "param_groups" in formatted
        assert "parametrize" in formatted

    def test_format_empty_suggestions(self):
        """Test formatting with no suggestions."""
        assert format_suggestions([]) == ""


class TestFormatAvailableKeys:
    """Test available keys formatting."""

    def test_format_simple_config(self):
        """Test formatting simple config."""
        config = {"_target_": "torch.nn.Linear", "in_features": 784, "out_features": 10}
        formatted = format_available_keys(config)

        assert "Available keys:" in formatted
        assert "_target_" in formatted
        assert "in_features" in formatted
        assert "out_features" in formatted

    def test_format_nested_config(self):
        """Test formatting config with nested values."""
        config = {"model": {"layers": 3}, "optimizer": "adam"}
        formatted = format_available_keys(config)

        assert "model:" in formatted
        assert "optimizer:" in formatted

    def test_format_excludes_metadata(self):
        """Test that _meta_ keys are excluded."""
        config = {"_meta_": {"source": "file.yaml"}, "real_key": 42}
        formatted = format_available_keys(config)

        assert "_meta_" not in formatted
        assert "real_key" in formatted

    def test_format_empty_config(self):
        """Test formatting empty config."""
        assert format_available_keys({}) == ""

    def test_format_limits_keys(self):
        """Test that max_keys limit is respected."""
        config = {f"key{i}": i for i in range(20)}
        formatted = format_available_keys(config, max_keys=5)

        assert "and 15 more" in formatted or "and 14 more" in formatted  # Depends on sorting


class TestColorFormatting:
    """Test color formatting with auto-detection."""

    def test_enable_colors_explicit(self):
        """Test explicitly enabling colors."""
        assert enable_colors(True) is True
        assert enable_colors(False) is False

    def test_enable_colors_auto_detect(self):
        """Test auto-detection."""
        result = enable_colors(None)
        # Should return a boolean
        assert isinstance(result, bool)

    def test_colors_disabled_in_tests(self):
        """Test that colors can be disabled."""
        from sparkwheel.errors.formatters import format_error

        enable_colors(False)
        formatted = format_error("error message")

        # Should not contain ANSI codes when disabled
        assert "\033[" not in formatted
        assert formatted == "error message"

    def test_colors_enabled(self):
        """Test that colors work when enabled."""
        from sparkwheel.errors.formatters import format_error

        enable_colors(True)
        formatted = format_error("error message")

        # Should contain ANSI codes when enabled
        assert "\033[" in formatted
        assert "error message" in formatted


class TestConfigKeyErrorEnhanced:
    """Test enhanced ConfigKeyError with suggestions."""

    def test_error_with_suggestions(self):
        """Test ConfigKeyError generates smart suggestions."""
        available = ["learning_rate", "batch_size", "epochs"]
        error = ConfigKeyError(
            "Key 'learing_rate' not found",
            missing_key="learing_rate",
            available_keys=available,
        )

        error_str = str(error)
        # Should contain suggestion
        assert "learning_rate" in error_str
        assert "💡" in error_str

    def test_error_with_available_keys(self):
        """Test ConfigKeyError shows available keys."""
        config = {"lr": 0.001, "epochs": 100}
        error = ConfigKeyError(
            "Key 'invalid' not found",
            missing_key="invalid",
            available_keys=list(config.keys()),
            config_context=config,
        )

        error_str = str(error)
        # Should show available keys
        assert "Available keys:" in error_str
        assert "lr:" in error_str
        assert "epochs:" in error_str

    def test_error_integration_with_parser(self, tmp_path):
        """Test that ConfigParser raises enhanced errors."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("model:\n  learning_rate: 0.001\n  batch_size: 32\nvalue: 10\nref: '@valu'")

        parser = ConfigParser.load(str(config_file))

        # Try to access reference with typo - should get suggestion
        with pytest.raises(ConfigKeyError) as exc_info:
            parser.resolve("ref")

        error_msg = str(exc_info.value)
        # Should suggest "value"
        assert "💡" in error_msg or "value" in error_msg


class TestErrorMessagesIntegration:
    """Integration tests for error messages in real scenarios."""

    def test_typo_in_reference(self, tmp_path):
        """Test error message when reference has typo."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("value: 10\nref: '@vlue'")

        parser = ConfigParser.load(str(config_file))

        with pytest.raises(ConfigKeyError) as exc_info:
            parser.resolve("ref")

        error_msg = str(exc_info.value)
        # Should suggest "value"
        assert "value" in error_msg
        assert "💡" in error_msg

    def test_missing_nested_key(self, tmp_path):
        """Test error for missing nested key."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("model:\n  lr: 0.001")

        parser = ConfigParser.load(str(config_file))

        with pytest.raises(ConfigKeyError) as exc_info:
            _ = parser.resolve("model::optimizer")

        error_msg = str(exc_info.value)
        # Should show available keys in model
        assert "lr" in error_msg or "💡" in error_msg
