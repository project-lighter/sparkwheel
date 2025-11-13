import pytest

from sparkwheel import Config
from sparkwheel.errors import (
    enable_colors,
    format_available_keys,
    format_resolution_chain,
    format_suggestions,
    get_suggestions,
    levenshtein_distance,
)
from sparkwheel.errors.context import _format_value_repr
from sparkwheel.utils.exceptions import ConfigKeyError


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

    def test_format_empty_config(self):
        """Test formatting empty config."""
        assert format_available_keys({}) == ""

    def test_format_limits_keys(self):
        """Test that max_keys limit is respected."""
        config = {f"key{i}": i for i in range(20)}
        formatted = format_available_keys(config, max_keys=5)

        assert "and 15 more" in formatted or "and 14 more" in formatted  # Depends on sorting

    def test_format_with_empty_dict_value(self):
        """Test formatting config with empty dict value."""
        config = {"model": {}, "optimizer": "adam"}
        formatted = format_available_keys(config)

        assert "model: {}" in formatted

    def test_format_with_empty_list_value(self):
        """Test formatting config with empty list value."""
        config = {"layers": [], "dropout": 0.5}
        formatted = format_available_keys(config)

        assert "layers: []" in formatted

    def test_format_with_large_dict_value(self):
        """Test formatting config with large dict (>3 items)."""
        config = {"model": {f"param{i}": i for i in range(10)}, "optimizer": "adam"}
        formatted = format_available_keys(config)

        # Should show "{...} (N keys)" for large dicts
        assert "model:" in formatted
        assert "keys)" in formatted

    def test_format_with_large_list_value(self):
        """Test formatting config with large list (>3 items)."""
        config = {"layers": [1, 2, 3, 4, 5, 6, 7, 8], "dropout": 0.5}
        formatted = format_available_keys(config)

        # Should show "[...] (N items)" for large lists
        assert "layers:" in formatted
        assert "items)" in formatted

    def test_format_with_long_value_truncation(self):
        """Test that very long values are truncated."""
        long_string = "x" * 100
        config = {"long_value": long_string}
        formatted = format_available_keys(config)

        # Should be truncated with "..."
        assert "..." in formatted
        assert long_string not in formatted  # Full string should not appear

    def test_format_with_non_dict_input(self):
        """Test formatting with non-dict input."""
        assert format_available_keys(None) == ""
        assert format_available_keys("not a dict") == ""
        assert format_available_keys([1, 2, 3]) == ""


class TestFormatValueRepr:
    """Test _format_value_repr function for value formatting."""

    def test_format_empty_dict(self):
        """Test formatting empty dict."""
        assert _format_value_repr({}) == "{}"

    def test_format_empty_list(self):
        """Test formatting empty list."""
        assert _format_value_repr([]) == "[]"

    def test_format_small_dict(self):
        """Test formatting small dict (<=3 items)."""
        result = _format_value_repr({"a": 1, "b": 2, "c": 3})
        assert "{" in result
        assert "}" in result
        assert "a:" in result

    def test_format_large_dict(self):
        """Test formatting large dict (>3 items)."""
        large_dict = {f"key{i}": i for i in range(10)}
        result = _format_value_repr(large_dict)
        assert "{...}" in result
        assert "10 keys" in result

    def test_format_small_list(self):
        """Test formatting small list (<=3 items)."""
        result = _format_value_repr([1, 2, 3])
        assert "[" in result
        assert "]" in result

    def test_format_large_list(self):
        """Test formatting large list (>3 items)."""
        large_list = list(range(10))
        result = _format_value_repr(large_list)
        assert "[...]" in result
        assert "10 items" in result

    def test_format_long_string_truncation(self):
        """Test that long strings are truncated."""
        long_string = "x" * 100
        result = _format_value_repr(long_string, max_length=20)
        assert len(result) <= 20
        assert "..." in result

    def test_format_string(self):
        """Test formatting regular string."""
        assert _format_value_repr("hello") == '"hello"'

    def test_format_int(self):
        """Test formatting integer."""
        assert _format_value_repr(42) == "42"

    def test_format_float(self):
        """Test formatting float."""
        assert _format_value_repr(3.14) == "3.14"

    def test_format_bool(self):
        """Test formatting boolean."""
        assert _format_value_repr(True) == "True"
        assert _format_value_repr(False) == "False"

    def test_format_none(self):
        """Test formatting None."""
        assert _format_value_repr(None) == "None"

    def test_format_custom_object(self):
        """Test formatting custom object (should show type name)."""

        class CustomClass:
            pass

        obj = CustomClass()
        result = _format_value_repr(obj)
        assert "CustomClass" in result


class TestFormatResolutionChain:
    """Test format_resolution_chain function."""

    def test_format_empty_chain(self):
        """Test formatting empty resolution chain."""
        assert format_resolution_chain([]) == ""

    def test_format_chain_all_successful(self):
        """Test formatting chain with all successful resolutions."""
        chain = [
            ("model::lr", "@base::lr", True),
            ("base::lr", "", True),
        ]
        result = format_resolution_chain(chain)

        assert "Resolution chain:" in result
        assert "model::lr" in result
        assert "base::lr" in result
        assert "✓" in result

    def test_format_chain_with_failure(self):
        """Test formatting chain with failed resolution."""
        chain = [
            ("training::optimizer", "@optimizer", True),
            ("optimizer::lr", "@base::learning_rate", True),
            ("base::learning_rate", "", False),
        ]
        result = format_resolution_chain(chain)

        assert "Resolution chain:" in result
        assert "❌ NOT FOUND" in result
        assert "💡" in result
        assert "failed at step 3" in result

    def test_format_chain_custom_title(self):
        """Test formatting chain with custom title."""
        chain = [("key", "", True)]
        result = format_resolution_chain(chain, title="Custom Title:")

        assert "Custom Title:" in result

    def test_format_chain_with_reference(self):
        """Test formatting chain entry with reference."""
        chain = [("model::lr", "@base::lr", True)]
        result = format_resolution_chain(chain)

        assert '"@base::lr"' in result
        assert "✓" in result

    def test_format_chain_without_reference(self):
        """Test formatting chain entry without reference (direct value)."""
        chain = [("value", "", True)]
        result = format_resolution_chain(chain)

        assert "value" in result
        assert "✓" in result


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

    def test_format_suggestion(self):
        """Test format_suggestion function."""
        from sparkwheel.errors.formatters import format_suggestion

        enable_colors(True)
        result = format_suggestion("suggestion text")
        assert "suggestion text" in result
        assert "\033[" in result  # Contains ANSI codes

        enable_colors(False)
        result = format_suggestion("suggestion text")
        assert result == "suggestion text"

    def test_format_success(self):
        """Test format_success function."""
        from sparkwheel.errors.formatters import format_success

        enable_colors(True)
        result = format_success("success text")
        assert "success text" in result
        assert "\033[" in result  # Contains ANSI codes

        enable_colors(False)
        result = format_success("success text")
        assert result == "success text"

    def test_format_code(self):
        """Test format_code function."""
        from sparkwheel.errors.formatters import format_code

        enable_colors(True)
        result = format_code("code text")
        assert "code text" in result
        assert "\033[" in result  # Contains ANSI codes

        enable_colors(False)
        result = format_code("code text")
        assert result == "code text"

    def test_format_context(self):
        """Test format_context function."""
        from sparkwheel.errors.formatters import format_context

        enable_colors(True)
        result = format_context("context text")
        assert "context text" in result
        assert "\033[" in result  # Contains ANSI codes

        enable_colors(False)
        result = format_context("context text")
        assert result == "context text"

    def test_format_bold(self):
        """Test format_bold function."""
        from sparkwheel.errors.formatters import format_bold

        enable_colors(True)
        result = format_bold("bold text")
        assert "bold text" in result
        assert "\033[" in result  # Contains ANSI codes

        enable_colors(False)
        result = format_bold("bold text")
        assert result == "bold text"

    def test_supports_color_with_no_color_env(self, monkeypatch):
        """Test that NO_COLOR environment variable disables colors."""
        from sparkwheel.errors.formatters import _supports_color

        monkeypatch.setenv("NO_COLOR", "1")
        assert _supports_color() is False

    def test_supports_color_with_sparkwheel_no_color_env(self, monkeypatch):
        """Test that SPARKWHEEL_NO_COLOR environment variable disables colors."""
        from sparkwheel.errors.formatters import _supports_color

        monkeypatch.setenv("SPARKWHEEL_NO_COLOR", "1")
        assert _supports_color() is False

    def test_get_colors_enabled_lazy_init(self):
        """Test that _get_colors_enabled initializes colors if needed."""
        from sparkwheel.errors import formatters

        # Reset global state
        formatters._COLORS_ENABLED = None

        # Should auto-detect when None
        result = formatters._get_colors_enabled()
        assert isinstance(result, bool)
        assert formatters._COLORS_ENABLED is not None

    def test_supports_color_with_force_color(self, monkeypatch):
        """Test that FORCE_COLOR enables colors even without TTY."""
        import sys

        from sparkwheel.errors.formatters import _supports_color

        # Clear other environment variables
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("SPARKWHEEL_NO_COLOR", raising=False)
        monkeypatch.setenv("FORCE_COLOR", "1")

        # Mock stdout without isatty
        class MockStdout:
            def isatty(self):
                return False

        original_stdout = sys.stdout
        try:
            sys.stdout = MockStdout()
            # FORCE_COLOR should enable colors even without TTY
            assert _supports_color() is True
        finally:
            sys.stdout = original_stdout

    def test_supports_color_no_isatty(self, monkeypatch):
        """Test color detection when stdout has no isatty method."""
        import sys

        from sparkwheel.errors.formatters import _supports_color

        # Clear environment variables that would override
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("SPARKWHEEL_NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.delenv("GITLAB_CI", raising=False)
        monkeypatch.delenv("CIRCLECI", raising=False)

        # Mock stdout without isatty
        class MockStdout:
            pass

        original_stdout = sys.stdout
        try:
            sys.stdout = MockStdout()
            assert _supports_color() is False
        finally:
            sys.stdout = original_stdout

    def test_supports_color_isatty_false(self, monkeypatch):
        """Test color detection when isatty returns False."""
        import sys

        from sparkwheel.errors.formatters import _supports_color

        # Clear environment variables
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("SPARKWHEEL_NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.delenv("GITLAB_CI", raising=False)
        monkeypatch.delenv("CIRCLECI", raising=False)

        # Mock stdout with isatty that returns False
        class MockStdout:
            def isatty(self):
                return False

        original_stdout = sys.stdout
        try:
            sys.stdout = MockStdout()
            assert _supports_color() is False
        finally:
            sys.stdout = original_stdout


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
        """Test that Config raises enhanced errors."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("model:\n  learning_rate: 0.001\n  batch_size: 32\nvalue: 10\nref: '@valu'")

        parser = Config.load(str(config_file))

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

        parser = Config.load(str(config_file))

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

        parser = Config.load(str(config_file))

        with pytest.raises(ConfigKeyError) as exc_info:
            _ = parser.resolve("model::optimizer")

        error_msg = str(exc_info.value)
        # Should show available keys in model
        assert "lr" in error_msg or "💡" in error_msg


class TestExceptionEdgeCases:
    """Test edge cases in exception handling."""

    def test_source_location_without_id(self):
        """Test SourceLocation string formatting without ID."""
        from sparkwheel.utils.exceptions import SourceLocation

        loc = SourceLocation(filepath="test.yaml", line=10)
        assert str(loc) == "test.yaml:10"

    def test_base_error_without_source_location_id(self):
        """Test BaseError formatting when source_location has no ID."""
        from sparkwheel.utils.exceptions import BaseError, SourceLocation

        loc = SourceLocation(filepath="test.yaml", line=5)
        error = BaseError("Test error", source_location=loc)
        msg = str(error)
        assert "[test.yaml:5]" in msg
        assert "Test error" in msg

    def test_base_error_snippet_file_read_error(self, tmp_path):
        """Test BaseError snippet handling when file can't be read."""
        from sparkwheel.utils.exceptions import BaseError, SourceLocation

        # Create a source location pointing to non-existent file
        loc = SourceLocation(filepath="/nonexistent/file.yaml", line=5)
        error = BaseError("Test error", source_location=loc)
        # Should not raise, just skip snippet
        msg = str(error)
        assert "Test error" in msg

    def test_config_key_error_no_suggestions(self):
        """Test ConfigKeyError when no suggestions can be generated."""
        from sparkwheel.utils.exceptions import ConfigKeyError

        # No available keys
        error = ConfigKeyError(
            "Key not found",
            missing_key="unknown",
            available_keys=[],
        )
        msg = str(error)
        assert "Key not found" in msg

    def test_config_key_error_with_many_keys(self):
        """Test ConfigKeyError when too many keys to display."""
        from sparkwheel.utils.exceptions import ConfigKeyError

        # More than 10 keys - should not display all
        many_keys = [f"key{i}" for i in range(15)]
        config = {k: "value" for k in many_keys}
        error = ConfigKeyError(
            "Key not found",
            missing_key="unknown",
            available_keys=many_keys,
            config_context=config,
        )
        msg = str(error)
        assert "Key not found" in msg

    def test_config_key_error_with_suggestions_and_keys(self):
        """Test ConfigKeyError with both suggestions and available keys."""
        from sparkwheel.utils.exceptions import ConfigKeyError

        error = ConfigKeyError(
            "Key not found",
            missing_key="vlue",
            available_keys=["value", "valid", "var"],
            config_context={"value": 1, "valid": 2},
        )
        msg = str(error)
        assert "Key not found" in msg
        # Should have suggestion for "vlue" -> "value"
        assert "💡" in msg
