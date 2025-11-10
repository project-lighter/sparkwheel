import json

from sparkwheel.diff import ConfigDiff, diff_configs, format_diff_json, format_diff_tree, format_diff_unified


class TestConfigDiff:
    """Test ConfigDiff dataclass."""

    def test_has_changes_true(self):
        """Test has_changes returns True when there are changes."""
        diff = ConfigDiff(
            added={"key": 1},
            removed={},
            changed={},
            unchanged={},
        )
        assert diff.has_changes() is True

    def test_has_changes_false(self):
        """Test has_changes returns False when there are no changes."""
        diff = ConfigDiff(
            added={},
            removed={},
            changed={},
            unchanged={"key": 1},
        )
        assert diff.has_changes() is False

    def test_summary_no_changes(self):
        """Test summary with no changes."""
        diff = ConfigDiff(
            added={},
            removed={},
            changed={},
            unchanged={"a": 1},
        )
        assert diff.summary() == "no changes"

    def test_summary_all_types(self):
        """Test summary with all change types."""
        diff = ConfigDiff(
            added={"a": 1, "b": 2},
            removed={"c": 3},
            changed={"d": (4, 5), "e": (6, 7), "f": (8, 9)},
            unchanged={},
        )
        summary = diff.summary()
        assert "3 changed" in summary
        assert "2 added" in summary
        assert "1 removed" in summary

    def test_summary_only_added(self):
        """Test summary with only added keys."""
        diff = ConfigDiff(
            added={"a": 1, "b": 2},
            removed={},
            changed={},
            unchanged={},
        )
        assert diff.summary() == "2 added"

    def test_summary_only_changed(self):
        """Test summary with only changed keys."""
        diff = ConfigDiff(
            added={},
            removed={},
            changed={"a": (1, 2)},
            unchanged={},
        )
        assert diff.summary() == "1 changed"


class TestDiffConfigs:
    """Test diff_configs function."""

    def test_diff_identical_dicts(self):
        """Test diff of identical dicts."""
        config1 = {"a": 1, "b": 2}
        config2 = {"a": 1, "b": 2}

        diff = diff_configs(config1, config2)

        assert not diff.has_changes()
        assert len(diff.unchanged) == 2

    def test_diff_added_keys(self):
        """Test detecting added keys."""
        config1 = {"a": 1}
        config2 = {"a": 1, "b": 2, "c": 3}

        diff = diff_configs(config1, config2)

        assert diff.added == {"b": 2, "c": 3}
        assert diff.removed == {}
        assert diff.changed == {}

    def test_diff_removed_keys(self):
        """Test detecting removed keys."""
        config1 = {"a": 1, "b": 2, "c": 3}
        config2 = {"a": 1}

        diff = diff_configs(config1, config2)

        assert diff.added == {}
        assert diff.removed == {"b": 2, "c": 3}
        assert diff.changed == {}

    def test_diff_changed_keys(self):
        """Test detecting changed values."""
        config1 = {"a": 1, "b": 2}
        config2 = {"a": 10, "b": 2}

        diff = diff_configs(config1, config2)

        assert diff.added == {}
        assert diff.removed == {}
        assert diff.changed == {"a": (1, 10)}
        assert diff.unchanged == {"b": 2}

    def test_diff_nested_configs(self):
        """Test diff with nested configs."""
        config1 = {"model": {"lr": 0.001, "hidden_size": 512}}
        config2 = {"model": {"lr": 0.01, "hidden_size": 512, "dropout": 0.1}}

        diff = diff_configs(config1, config2)

        assert diff.changed == {"model::lr": (0.001, 0.01)}
        assert diff.added == {"model::dropout": 0.1}
        assert diff.unchanged == {"model::hidden_size": 512}

    def test_diff_with_ignore_keys(self):
        """Test diff with ignore_keys."""
        config1 = {"a": 1, "b": 2, "timestamp": 123}
        config2 = {"a": 1, "b": 3, "timestamp": 456}

        diff = diff_configs(config1, config2, ignore_keys=["timestamp"])

        assert diff.changed == {"b": (2, 3)}
        assert "timestamp" not in diff.changed

    def test_diff_files(self, tmp_path):
        """Test diff with actual files."""
        file1 = tmp_path / "config1.yaml"
        file1.write_text("a: 1\nb: 2")

        file2 = tmp_path / "config2.yaml"
        file2.write_text("a: 10\nb: 2\nc: 3")

        diff = diff_configs(str(file1), str(file2))

        assert diff.changed == {"a": (1, 10)}
        assert diff.added == {"c": 3}
        assert diff.unchanged == {"b": 2}

    def test_diff_with_resolve(self, tmp_path):
        """Test semantic diff with --resolve flag."""
        # Config 1: Uses reference
        file1 = tmp_path / "config1.yaml"
        file1.write_text("base_lr: 0.001\nmodel:\n  lr: '@base_lr'")

        # Config 2: Direct value
        file2 = tmp_path / "config2.yaml"
        file2.write_text("model:\n  lr: 0.001")

        # Without resolve: Should show difference
        diff_no_resolve = diff_configs(str(file1), str(file2), resolve=False)
        assert diff_no_resolve.has_changes()  # Syntactic difference

        # With resolve: Should be identical (semantic equivalence)
        diff_resolved = diff_configs(str(file1), str(file2), resolve=True)
        # After resolution, both should have lr: 0.001
        assert diff_resolved.unchanged.get("model::lr") == 0.001

    def test_diff_with_expressions(self, tmp_path):
        """Test semantic diff with expressions."""
        # Config 1: Uses expression
        file1 = tmp_path / "config1.yaml"
        file1.write_text("model:\n  size: '$256 * 2'")

        # Config 2: Direct value
        file2 = tmp_path / "config2.yaml"
        file2.write_text("model:\n  size: 512")

        # With resolve: Should be identical after evaluation
        diff = diff_configs(str(file1), str(file2), resolve=True)
        assert diff.unchanged.get("model::size") == 512


class TestFormatDiffTree:
    """Test tree format output."""

    def test_format_no_changes(self):
        """Test formatting diff with no changes."""
        diff = ConfigDiff(added={}, removed={}, changed={}, unchanged={"a": 1})

        output = format_diff_tree(diff)

        assert "No differences found" in output

    def test_format_with_changes(self):
        """Test formatting diff with changes."""
        diff = ConfigDiff(
            added={"model::dropout": 0.1},
            removed={"old::param": 123},
            changed={"model::lr": (0.001, 0.01)},
            unchanged={},
        )

        output = format_diff_tree(diff)

        assert "model" in output
        assert "lr" in output
        assert "0.001" in output
        assert "0.01" in output
        assert "dropout" in output
        assert "Summary:" in output

    def test_format_shows_unchanged(self):
        """Test formatting with show_unchanged=True."""
        diff = ConfigDiff(
            added={},
            removed={},
            changed={},
            unchanged={"model::lr": 0.001},
        )

        output = format_diff_tree(diff, show_unchanged=True)

        assert "lr" in output
        assert "unchanged" in output


class TestFormatDiffUnified:
    """Test unified format output."""

    def test_format_unified_no_changes(self):
        """Test unified format with no changes."""
        diff = ConfigDiff(added={}, removed={}, changed={}, unchanged={"a": 1})

        output = format_diff_unified(diff)

        assert "---" in output
        assert "+++" in output
        assert "No differences" in output

    def test_format_unified_with_changes(self):
        """Test unified format with changes."""
        diff = ConfigDiff(
            added={"model::dropout": 0.1},
            removed={"model::old_param": 123},
            changed={"model::lr": (0.001, 0.01)},
            unchanged={},
        )

        output = format_diff_unified(diff)

        assert "@@ model @@" in output
        assert "- lr: 0.001" in output
        assert "+ lr: 0.01" in output
        assert "+ dropout: 0.1" in output
        assert "- old_param: 123" in output


class TestFormatDiffJson:
    """Test JSON format output."""

    def test_format_json(self):
        """Test JSON format output."""
        diff = ConfigDiff(
            added={"a": 1},
            removed={"b": 2},
            changed={"c": (3, 4)},
            unchanged={"d": 5},
        )

        output = format_diff_json(diff)
        parsed = json.loads(output)

        assert parsed["added"] == {"a": 1}
        assert parsed["removed"] == {"b": 2}
        assert parsed["changed"] == {"c": {"old": 3, "new": 4}}
        assert "summary" in parsed

    def test_format_json_structure(self):
        """Test JSON output is valid and has expected structure."""
        diff = ConfigDiff(added={}, removed={}, changed={}, unchanged={"a": 1})

        output = format_diff_json(diff)

        # Should be valid JSON
        parsed = json.loads(output)

        # Should have expected keys
        assert "added" in parsed
        assert "removed" in parsed
        assert "changed" in parsed
        assert "summary" in parsed


class TestDiffIntegration:
    """Integration tests for diff functionality."""

    def test_full_workflow(self, tmp_path):
        """Test complete diff workflow."""
        # Create two versions of a config
        v1 = tmp_path / "config_v1.yaml"
        v1.write_text("""
model:
  _target_: torch.nn.Linear
  hidden_size: 512
  activation: relu

optimizer:
  _target_: torch.optim.Adam
  lr: 0.001

training:
  epochs: 50
  old_param: 123
""")

        v2 = tmp_path / "config_v2.yaml"
        v2.write_text("""
model:
  _target_: torch.nn.Linear
  hidden_size: 1024
  activation: relu
  dropout: 0.1

optimizer:
  _target_: torch.optim.Adam
  lr: 0.0001
  weight_decay: 0.01

training:
  epochs: 50
  batch_size: 32
""")

        # Compute diff
        diff = diff_configs(str(v1), str(v2))

        # Verify changes
        assert diff.changed["model::hidden_size"] == (512, 1024)
        assert diff.changed["optimizer::lr"] == (0.001, 0.0001)
        assert diff.added["model::dropout"] == 0.1
        assert diff.added["optimizer::weight_decay"] == 0.01
        assert diff.added["training::batch_size"] == 32
        assert diff.removed["training::old_param"] == 123

        # Test all output formats
        tree_output = format_diff_tree(diff, name1="v1", name2="v2")
        assert "v1 → v2" in tree_output
        assert "Summary:" in tree_output

        unified_output = format_diff_unified(diff, name1="v1", name2="v2")
        assert "--- v1" in unified_output
        assert "+++ v2" in unified_output

        json_output = format_diff_json(diff)
        parsed = json.loads(json_output)
        assert len(parsed["changed"]) == 2
        assert len(parsed["added"]) == 3
        assert len(parsed["removed"]) == 1
