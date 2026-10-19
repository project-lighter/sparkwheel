import pytest

from sparkwheel import Config
from sparkwheel.errors import (
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
        assert formatted.startswith("Did you mean")  # BaseError adds the 💡 marker

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

        parser = Config().update(str(config_file))

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

        parser = Config().update(str(config_file))

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

        parser = Config().update(str(config_file))

        with pytest.raises(ConfigKeyError) as exc_info:
            _ = parser.resolve("model::optimizer")

        error_msg = str(exc_info.value)
        # Should show available keys in model
        assert "lr" in error_msg or "💡" in error_msg


class TestExceptionEdgeCases:
    """Test edge cases in exception handling."""

    def test_source_location_without_id(self):
        """Test Location string formatting without ID."""
        from sparkwheel.utils.exceptions import Location

        loc = Location(filepath="test.yaml", line=10)
        assert str(loc) == "test.yaml:10"

    def test_base_error_without_source_location_id(self):
        """Test BaseError formatting when source_location has no ID."""
        from sparkwheel.utils.exceptions import BaseError, Location

        loc = Location(filepath="test.yaml", line=5)
        error = BaseError("Test error", source_location=loc)
        msg = str(error)
        assert "[test.yaml:5]" in msg
        assert "Test error" in msg

    def test_base_error_snippet_file_read_error(self, tmp_path):
        """Test BaseError snippet handling when file can't be read."""
        from sparkwheel.utils.exceptions import BaseError, Location

        # Create a source location pointing to non-existent file
        loc = Location(filepath="/nonexistent/file.yaml", line=5)
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


class TestSelfContainedErrors:
    """Each error message alone tells the user what failed, where, and what to do."""

    @staticmethod
    def _error(tmp_path, text, id, error=Exception):
        path = tmp_path / "config.yaml"
        path.write_text(text)
        with pytest.raises(error) as excinfo:
            Config().update(str(path)).resolve(id)
        return str(excinfo.value), str(path)

    def test_expression_error_shows_python_error_and_written_expression(self, tmp_path):
        from sparkwheel import EvaluationError

        msg, path = self._error(tmp_path, 'a: 3\nmodel:\n  size: "$@a.bit_lenght()"\n', "model::size", EvaluationError)
        assert msg.splitlines()[0] == (
            "Failed to evaluate expression '$@a.bit_lenght()': AttributeError: 'int' object has no attribute 'bit_lenght'"
        )
        assert f"{path}:3" in msg
        assert "__ref_" not in msg

    @pytest.mark.parametrize("expression", ["$1 +", "$@a +", "$(@a"])
    def test_syntax_error_has_location(self, tmp_path, expression):
        from sparkwheel import EvaluationError

        msg, path = self._error(tmp_path, f'a: 3\nx: "{expression}"\n', "x", EvaluationError)
        assert f"'{expression}': SyntaxError" in msg
        assert f"{path}:2" in msg

    def test_name_error_suggests_imports(self, tmp_path):
        msg, _ = self._error(tmp_path, 'x: "$torch.zeros(3)"\n', "x")
        assert "NameError: name 'torch' is not defined" in msg
        assert "`_imports_: {torch: torch}`" in msg

    def test_word_import_inside_expression_is_not_an_import_statement(self):
        config = Config().update({"a": {"import": 1}, "b": "$@a['import']"})
        assert config.resolve("b") == 1

    def test_unevaluated_expression_keeps_written_text(self):
        config = Config().update({"a": 1, "x": "$@a + 1"})
        assert config.resolve("x", eval_expr=False).get_config() == "$@a + 1"

    def test_missing_top_level_id_has_no_unrelated_location(self, tmp_path):
        msg, path = self._error(tmp_path, "a: 3\nmodel:\n  size: 1\n", "modle", ConfigKeyError)
        assert path not in msg
        assert "model" in msg

    def test_missing_nested_id_points_at_nearest_existing_parent(self, tmp_path):
        msg, path = self._error(tmp_path, "a: 3\nmodel:\n  size: 1\n", "model::sise", ConfigKeyError)
        assert f"{path}:2" in msg
        assert "size" in msg

    def test_missing_reference_points_at_the_key_that_holds_it(self, tmp_path):
        text = (
            "num_classes: 3\nmodel:\n  _target_: builtins.dict\n  head:\n    _target_: builtins.dict\n    n: '@num_clases'\n"
        )
        msg, path = self._error(tmp_path, text, "model", ConfigKeyError)
        assert f"{path}:6 → model::head::n" in msg
        assert "num_classes" in msg

    def test_single_suggestion_marker(self, tmp_path):
        msg, _ = self._error(tmp_path, "value: 1\nref: '@valeu'\n", "ref", ConfigKeyError)
        assert "💡 💡" not in msg
        assert msg.count("💡") == 1

    def test_unknown_target_module_names_the_part_that_cannot_be_imported(self):
        from sparkwheel import TargetNotFoundError

        with pytest.raises(TargetNotFoundError, match="'collectionz' cannot be imported"):
            Config().update({"x": {"_target_": "collectionz.abc.Counter"}}).resolve("x")


class TestOverrideProvenance:
    """Errors caused by a CLI override point at the override, not at the YAML line it replaced."""

    @staticmethod
    def _config(tmp_path):
        (tmp_path / "overridemod.py").write_text(
            "class Model:\n    def __init__(self, learning_rate, dim=2):\n        self.lr, self.dim = learning_rate, dim\n"
        )
        path = tmp_path / "config.yaml"
        path.write_text("model:\n  _target_: overridemod.Model\n  learning_rate: 0.1\n  dim: 4\n")
        return Config().update(str(path))

    @pytest.fixture(autouse=True)
    def _importable(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(str(tmp_path))

    def test_bad_reference_in_override(self, tmp_path):
        config = self._config(tmp_path).update("model::dim=$@missing + 1")
        with pytest.raises(ConfigKeyError) as excinfo:
            config.resolve("model")
        msg = str(excinfo.value)
        assert "[override → model::dim]:\n  → model::dim=$@missing + 1" in msg
        assert "config.yaml" not in msg

    def test_bad_target_in_override(self, tmp_path):
        from sparkwheel import TargetNotFoundError

        config = self._config(tmp_path).update("model::_target_=overridemod.Modl")
        with pytest.raises(TargetNotFoundError) as excinfo:
            config.resolve("model")
        msg = str(excinfo.value)
        assert "→ model::_target_=overridemod.Modl" in msg
        assert "overridemod.Model" in msg  # did-you-mean

    def test_bad_target_in_file_points_at_target_line(self, tmp_path):
        from sparkwheel import TargetNotFoundError

        path = tmp_path / "config.yaml"
        path.write_text("model:\n  learning_rate: 0.1\n  _target_: overridemod.Modl\n")
        with pytest.raises(TargetNotFoundError) as excinfo:
            Config().update(str(path)).resolve("model")
        assert f"[{path}:3 → model::_target_]" in str(excinfo.value)

    def test_new_subtree_from_override(self, tmp_path):
        config = self._config(tmp_path).update("model={_target_: overridemod.Model, learning_rate: '@nope'}")
        with pytest.raises(ConfigKeyError) as excinfo:
            config.resolve("model")
        assert "→ model={_target_: overridemod.Model, learning_rate: '@nope'}" in str(excinfo.value)
        assert config.locations.get("model::learning_rate").override.startswith("model=")
        assert config.locations.get("model::dim") is None  # the file's `dim` was replaced

    def test_merging_override_keeps_file_locations_of_untouched_keys(self, tmp_path):
        config = self._config(tmp_path).update("+model={dim: 8}")
        assert config.locations.get("model").override == ""
        assert config.locations.get("model::learning_rate").line == 3
        assert config.locations.get("model::dim").override == "+model={dim: 8}"

    def test_appended_items_point_at_the_override(self, tmp_path):
        path = tmp_path / "base.yaml"
        path.write_text("xs:\n  - {a: 1}\n  - {a: 2}\n")
        config = Config().update(str(path)).update("+xs=[{a: 3}]")
        assert config.get("xs::2") == {"a": 3}
        assert config.locations.get("xs::1::a").line == 3
        assert config.locations.get("xs::2::a").override == "+xs=[{a: 3}]"

    def test_appended_items_point_at_the_file(self, tmp_path):
        (tmp_path / "base.yaml").write_text("xs:\n  - {a: 0}\n")
        (tmp_path / "more.yaml").write_text("# more\n+xs:\n  - {a: 1}\n")
        config = Config().update(str(tmp_path / "base.yaml")).update(str(tmp_path / "more.yaml"))
        assert config.locations.get("xs::0::a").filepath.endswith("base.yaml")
        assert config.locations.get("xs::1::a").filepath.endswith("more.yaml")
        assert config.locations.get("xs::1::a").line == 3

    def test_a_set_list_replaces_the_list(self):
        config = Config().update({"xs": [1, 2], "m": {"xs": [1]}}).update("xs=[3]").update("m={xs: [4]}")
        assert config.get("xs") == [3] and config.get("m::xs") == [4]
        assert config.locations.get("xs::0").override == "xs=[3]"

    def test_location_str(self):
        from sparkwheel import Location

        assert str(Location("", 0, id="a", override="a=1")) == "override `a=1`"
        with pytest.raises(ValueError):
            Location("f.yaml", 0)


class TestArgumentErrors:
    """A wrong argument name is reported with did-you-mean and the line (or override) that set it."""

    @pytest.fixture(autouse=True)
    def _module(self, tmp_path, monkeypatch):
        (tmp_path / "argmod.py").write_text(
            "class Model:\n"
            "    def __init__(self, learning_rate, dim=2):\n"
            "        self.lr, self.dim = learning_rate, dim\n"
            "\n"
            "class Broken:\n"
            "    def __init__(self, n=1):\n"
            "        len(n)\n"
            "\n"
            "import functools\n"
            "def injects(f):\n"
            "    @functools.wraps(f)\n"
            "    def wrapper(*args, injected=0, **kwargs):\n"
            "        return f(*args, **kwargs) + injected\n"
            "    return wrapper\n"
            "\n"
            "@injects\n"
            "def wrapped(a):\n"
            "    return a\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        self.path = tmp_path / "config.yaml"

    def _error(self, text, *overrides):
        from sparkwheel import InstantiationError

        self.path.write_text(text)
        config = Config().update(str(self.path))
        for override in overrides:
            config.update(override)
        with pytest.raises(InstantiationError) as excinfo:
            config.resolve("model")
        return excinfo.value

    def test_typo_in_yaml(self):
        error = self._error("model:\n  _target_: argmod.Model\n  learnin_rate: 0.1\n")
        msg = str(error)
        assert msg.startswith("'argmod.Model' got an unexpected argument 'learnin_rate'")
        assert f"[{self.path}:3 → model::learnin_rate]" in msg
        assert "Did you mean 'learning_rate'?" in msg and "Accepted arguments: learning_rate, dim" in msg

    def test_typo_in_override(self):
        msg = str(self._error("model:\n  _target_: argmod.Model\n  learning_rate: 0.1\n", "model::dimm=3"))
        assert "unexpected argument 'dimm'" in msg and "→ model::dimm=3" in msg and "Did you mean 'dim'?" in msg

    def test_missing_argument(self):
        msg = str(self._error("model:\n  _target_: argmod.Model\n  dim: 3\n"))
        assert "missing a required argument: 'learning_rate'" in msg and f"{self.path}:1 → model" in msg

    def test_type_error_inside_user_code_is_not_reinterpreted(self):
        error = self._error("model:\n  _target_: argmod.Broken\n")
        assert "object of type 'int' has no len()" in str(error)
        assert isinstance(error.__cause__, TypeError)

    def test_callable_mode_checks_arguments_when_the_partial_is_made(self):
        msg = str(self._error("model:\n  _target_: argmod.Model\n  _mode_: callable\n  lerning_rate: 0.1\n"))
        assert "unexpected argument 'lerning_rate'" in msg and f"{self.path}:4" in msg

    def test_callable_mode_allows_missing_arguments(self):
        self.path.write_text("model:\n  _target_: argmod.Model\n  _mode_: callable\n  dim: 3\n")
        assert Config().update(str(self.path)).resolve("model")(learning_rate=1).dim == 3

    def test_decorator_wrapper_arguments_are_accepted(self):
        config = Config().update({"f": {"_target_": "argmod.wrapped", "_mode_": "callable", "injected": 2}})
        config.check()
        assert config.resolve("f")(a=1) == 3

    def test_targets_without_signature_are_called_as_before(self):
        assert Config().update({"x": {"_target_": "builtins.dict", "a": 1}}).resolve("x") == {"a": 1}
