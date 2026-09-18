"""Transactions, container-aware paths, and frozen-source behavior."""

from dataclasses import dataclass

import pytest

from sparkwheel import Config, ConfigMergeError, ValidationError, validator


@dataclass
class Settings:
    n: int
    payload: dict


@pytest.mark.parametrize("edit", ["set", "update", "root"])
def test_rejected_schema_edit_preserves_source_namespace_and_runtime_identity(edit):
    config = Config(schema=Settings).update({"n": 2, "payload": {"_target_": "builtins.dict"}})
    runtime = config.resolve("payload")
    source = config.get()
    imports = config._imports
    resolver = config._resolver
    with pytest.raises(ValidationError):
        if edit == "set":
            config.set("n", "invalid")
        elif edit == "root":
            config.set("", {"n": "invalid", "payload": {}})
        else:
            config.update({"n": "invalid"})
    assert config.get() is source
    assert config.get("n") == 2
    assert config.resolve("payload") is runtime
    assert config._resolver is resolver
    assert config._imports is imports


def test_partial_path_patch_failure_does_not_publish_earlier_edits():
    config = Config(data={"n": 2, "payload": {"_target_": "builtins.dict"}})
    runtime = config.resolve("payload")
    source = config.get()
    with pytest.raises(ConfigMergeError):
        config.update({"n": 9, "~missing::child": None})
    assert config.get() is source
    assert config.get("n") == 2
    assert config.resolve("payload") is runtime


def test_rejected_file_edit_preserves_source_locations(tmp_path):
    good, bad = tmp_path / "good.yaml", tmp_path / "bad.yaml"
    good.write_text("n: 2\npayload: {}\n")
    bad.write_text("n: invalid\n")
    config = Config(schema=Settings).update(good)
    location = config.locations.get("n")
    with pytest.raises(ValidationError):
        config.update(bad)
    assert config.locations.get("n") is location
    assert location.filepath == str(good)


def test_list_index_set_preserves_other_elements_and_container_type():
    config = Config(data={"items": [{"n": 1}, {"n": 2}]})
    config.set("items::1::n", 7)
    assert config.get("items") == [{"n": 1}, {"n": 7}]
    config.update("=items::0={n: 9}")
    assert config.get("items") == [{"n": 9}, {"n": 7}]


@pytest.mark.parametrize("path", ["items::3", "items::nope", "scalar::child"])
def test_invalid_traversal_preserves_source_and_runtime(path):
    config = Config(data={"items": [1, 2], "scalar": 3, "object": {"_target_": "builtins.dict"}})
    runtime = config.resolve("object")
    source = config.get()
    with pytest.raises((KeyError, IndexError, TypeError, ValueError)):
        config.set(path, 8)
    assert config.get() is source
    assert config.resolve("object") is runtime


def test_path_deletion_and_structural_item_deletion_agree():
    first = Config(data={"group": {"items": [0, 1, 2], "options": {"a": 1, "b": 2}}})
    second = Config(data={"group": {"items": [0, 1, 2], "options": {"a": 1, "b": 2}}})
    first.update({"~group::items": [1], "~group::options": ["a"]})
    second.update({"group": {"~items": [1], "~options": ["a"]}})
    assert first.get() == second.get() == {"group": {"items": [0, 2], "options": {"b": 2}}}
    first.update("~group::items::0")
    assert first.get("group::items") == [2]


def test_failed_batch_item_removal_leaves_all_items():
    config = Config(data={"group": {"options": {"a": 1, "b": 2}}})
    with pytest.raises(ConfigMergeError):
        config.update({"~group::options": ["a", "missing"]})
    assert config.get() == {"group": {"options": {"a": 1, "b": 2}}}


def test_freeze_detaches_old_views_and_returns_defensive_containers():
    original = {"nested": {"values": [1, 2]}}
    config = Config(data=original)
    old_view = config.get("nested")
    cached = config.resolve("nested")
    config.freeze()
    old_view["values"].append(3)
    original["nested"]["values"].append(4)
    current_view = config.get("nested")
    current_view["values"].append(5)
    config["nested"]["values"].append(6)
    assert config.get("nested") == {"values": [1, 2]}
    assert config.resolve("nested") is cached
    assert cached == {"values": [1, 2]}
    config.unfreeze()
    config.set("nested::values::0", 7)
    assert config.get("nested::values") == [7, 2]


def test_updates_and_frozen_views_preserve_opaque_identity():
    import math

    marker = object()
    config = Config(data={"module": math, "marker": marker})
    config.update({"n": 2})
    config.freeze()
    assert config.get("module") is math
    assert config.get("marker") is marker


def test_batch_schema_validation_happens_after_all_fields_are_updated():
    config = Config(schema=Settings).update({"n": 1, "payload::value": 2})
    assert config.get() == {"n": 1, "payload": {"value": 2}}


def test_cross_field_validator_observes_atomic_batch_and_rejects_atomically():
    @dataclass
    class Bounds:
        start: int
        end: int

        @validator
        def check_order(self):
            if self.start >= self.end:
                raise ValueError("start must precede end")

    config = Config(schema=Bounds).update({"start": 0, "end": 1})
    config.update({"start": 2, "end": 3})
    before = config.get()
    with pytest.raises(ValidationError, match="start must precede end"):
        config.update({"start": 8, "end": 4})
    assert config.get() is before
    assert config.get() == {"start": 2, "end": 3}


def test_failed_external_include_update_preserves_cached_objects():
    config = Config(data={"n": 2, "object": {"_target_": "builtins.dict"}})
    runtime = config.resolve("object")
    before = config.get()
    with pytest.raises(FileNotFoundError):
        config.update({"n": 3, "include": "%definitely_missing_recipe_file.yaml"})
    assert config.get() is before
    assert config.resolve("object") is runtime
