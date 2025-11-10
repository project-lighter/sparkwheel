from sparkwheel import ConfigParser, parse_args


class TestParseValue:
    """Test the _parse_value helper function."""

    def test_parse_int(self):
        """Test parsing integers."""
        from sparkwheel.cli import _parse_value

        assert _parse_value("123") == 123
        assert _parse_value("0") == 0
        assert _parse_value("-42") == -42

    def test_parse_float(self):
        """Test parsing floats."""
        from sparkwheel.cli import _parse_value

        assert _parse_value("3.14") == 3.14
        assert _parse_value("0.001") == 0.001
        assert _parse_value("-2.5") == -2.5

    def test_parse_bool(self):
        """Test parsing booleans."""
        from sparkwheel.cli import _parse_value

        assert _parse_value("true") is True
        assert _parse_value("false") is False

    def test_parse_null(self):
        """Test parsing null."""
        from sparkwheel.cli import _parse_value

        assert _parse_value("null") is None

    def test_parse_list(self):
        """Test parsing lists."""
        from sparkwheel.cli import _parse_value

        assert _parse_value("[1,2,3]") == [1, 2, 3]
        assert _parse_value('["a","b","c"]') == ["a", "b", "c"]
        assert _parse_value("[]") == []

    def test_parse_dict_quoted_keys(self):
        """Test parsing dicts with quoted keys."""
        from sparkwheel.cli import _parse_value

        assert _parse_value('{"a":1,"b":2}') == {"a": 1, "b": 2}
        assert _parse_value('{"key":"value"}') == {"key": "value"}

    def test_parse_dict_unquoted_keys(self):
        """Test parsing dicts with unquoted keys (CLI-friendly)."""
        from sparkwheel.cli import _parse_value

        assert _parse_value("{a:1,b:2}") == {"a": 1, "b": 2}
        assert _parse_value("{key:value}") == {"key": "value"}
        assert _parse_value("{type:relu}") == {"type": "relu"}

    def test_parse_nested_dict(self):
        """Test parsing nested dicts."""
        from sparkwheel.cli import _parse_value

        result = _parse_value("{third:{type:relu,size:256}}")
        assert result == {"third": {"type": "relu", "size": 256}}

    def test_parse_string_fallback(self):
        """Test strings that can't be parsed as JSON."""
        from sparkwheel.cli import _parse_value

        assert _parse_value("hello") == "hello"
        assert _parse_value("Experiment 1") == "Experiment 1"
        assert _parse_value("model_v2") == "model_v2"

    def test_parse_quoted_string(self):
        """Test quoted strings."""
        from sparkwheel.cli import _parse_value

        assert _parse_value('"hello world"') == "hello world"
        assert _parse_value('"123"') == "123"  # Quoted number stays as string


class TestParseArgs:
    """Test the parse_args function."""

    def test_simple_scalar_args(self):
        """Test parsing simple scalar arguments."""
        result = parse_args(["model::lr=0.001", "training::epochs=100"])
        assert result == {"model::lr": 0.001, "training::epochs": 100}

    def test_mixed_types(self):
        """Test parsing mixed types."""
        result = parse_args([
            "count=42",
            "rate=0.5",
            "enabled=true",
            "name=experiment",
            "values=[1,2,3]",
        ])
        assert result == {
            "count": 42,
            "rate": 0.5,
            "enabled": True,
            "name": "experiment",
            "values": [1, 2, 3],
        }

    def test_merge_directive(self):
        """Test + merge directive."""
        result = parse_args(["+model::layers={third:{type:relu}}"])
        assert result == {"+model::layers": {"third": {"type": "relu"}}}

    def test_delete_directive(self):
        """Test ~ delete directive."""
        result = parse_args(["~model::old_param"])
        assert result == {"~model::old_param": None}

    def test_combined_directives(self):
        """Test combining normal, merge, and delete."""
        result = parse_args([
            "model::lr=0.001",
            "+model::layers={new:layer}",
            "~old::param",
        ])
        assert result == {
            "model::lr": 0.001,
            "+model::layers": {"new": "layer"},
            "~old::param": None,
        }

    def test_empty_args(self):
        """Test with empty arguments list."""
        result = parse_args([])
        assert result == {}

    def test_string_with_spaces(self):
        """Test parsing strings with spaces."""
        # In shell, user would quote: python app.py name="My Experiment"
        result = parse_args(["name=My Experiment"])
        # Without quotes, "My Experiment" becomes two separate values
        # The function takes the part after first =
        assert result["name"] == "My Experiment"

    def test_complex_nested_dict(self):
        """Test complex nested dictionary."""
        result = parse_args(["+model::optimizer={type:adam,lr:0.001,betas:[0.9,0.999]}"])
        assert result == {
            "+model::optimizer": {
                "type": "adam",
                "lr": 0.001,
                "betas": [0.9, 0.999],
            }
        }


class TestCLIIntegration:
    """Test integration of parse_args with ConfigParser."""

    def test_basic_override(self):
        """Test basic CLI override."""
        parser = ConfigParser.load({"model": {"lr": 0.001, "epochs": 50}})

        # Simulate CLI args: python app.py model::lr=0.01 model::epochs=100
        cli_args = parse_args(["model::lr=0.01", "model::epochs=100"])
        parser.update(cli_args)

        assert parser["model"]["lr"] == 0.01
        assert parser["model"]["epochs"] == 100

    def test_merge_via_cli(self):
        """Test merging dict via CLI."""
        parser = ConfigParser.load({"model": {"layers": {"first": 128, "second": 64}}})

        # Add third layer via CLI
        cli_args = parse_args(["+model::layers={third:32}"])
        parser.update(cli_args)

        assert parser["model"]["layers"]["first"] == 128  # Preserved
        assert parser["model"]["layers"]["second"] == 64  # Preserved
        assert parser["model"]["layers"]["third"] == 32  # Added

    def test_delete_via_cli(self):
        """Test deleting key via CLI."""
        parser = ConfigParser.load({"model": {"lr": 0.001, "deprecated": True}})

        # Delete deprecated param via CLI
        cli_args = parse_args(["~model::deprecated"])
        parser.update(cli_args)

        assert parser["model"]["lr"] == 0.001
        assert "deprecated" not in parser["model"]

    def test_full_training_workflow(self):
        """Test complete training script workflow."""
        # Base config
        parser = ConfigParser.load({
            "model": {"lr": 0.001, "hidden_size": 512},
            "training": {"epochs": 50, "batch_size": 32},
        })

        # CLI overrides: python train.py model::lr=0.01 training::epochs=100 training::device=cuda
        cli_args = parse_args([
            "model::lr=0.01",
            "training::epochs=100",
            "training::device=cuda",
        ])
        parser.update(cli_args)

        assert parser["model"]["lr"] == 0.01
        assert parser["model"]["hidden_size"] == 512  # Unchanged
        assert parser["training"]["epochs"] == 100
        assert parser["training"]["batch_size"] == 32  # Unchanged
        assert parser["training"]["device"] == "cuda"  # Added

    def test_with_argparse_simulation(self):
        """Test mixing with argparse-style workflow."""
        # Simulate argparse handling some args, passing rest to parse_args
        parser = ConfigParser.load({"model": {"lr": 0.001}})

        # Imagine argparse handled --config and --gpus
        # Unknown args go to parse_args: ["model::lr=0.01", "model::dropout=0.1"]
        unknown_args = ["model::lr=0.01", "model::dropout=0.1"]
        cli_args = parse_args(unknown_args)
        parser.update(cli_args)

        assert parser["model"]["lr"] == 0.01
        assert parser["model"]["dropout"] == 0.1

    def test_type_preservation(self):
        """Test that types are properly inferred."""
        parser = ConfigParser.load({})

        cli_args = parse_args([
            "int_val=123",
            "float_val=3.14",
            "bool_val=true",
            "null_val=null",
            "list_val=[1,2,3]",
            "dict_val={a:1}",
            "str_val=hello",
        ])
        parser.update(cli_args)

        assert isinstance(parser["int_val"], int)
        assert isinstance(parser["float_val"], float)
        assert isinstance(parser["bool_val"], bool)
        assert parser["null_val"] is None
        assert isinstance(parser["list_val"], list)
        assert isinstance(parser["dict_val"], dict)
        assert isinstance(parser["str_val"], str)
