"""Authored duplicate YAML keys fail before committing a configuration update."""

import pytest
import yaml

from sparkwheel import Config
from sparkwheel.loader import Loader
from sparkwheel.utils import CheckKeyDuplicatesYamlLoader, check_key_duplicates


@pytest.mark.parametrize("strict", [None, "1"])
@pytest.mark.parametrize("body", ["n: 1\nn: 2\n", "group:\n  n: 1\n  n: 2\n", "items:\n  - n: 1\n    n: 2\n"])
def test_rejects_duplicates_at_every_depth(tmp_path, monkeypatch, body, strict):
    if strict is None:
        monkeypatch.delenv("SPARKWHEEL_STRICT_KEYS", raising=False)
    else:
        monkeypatch.setenv("SPARKWHEEL_STRICT_KEYS", strict)
    path = tmp_path / "duplicate.yaml"
    path.write_text(body)
    with pytest.raises(ValueError, match="Duplicate key") as caught:
        Loader().load_file(path)
    message = str(caught.value)
    assert str(path) in message
    assert "first defined" in message and "repeated" in message
    assert "line 2" in message or "line 3" in message


def test_permissive_compatibility_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("SPARKWHEEL_STRICT_KEYS", "0")
    path = tmp_path / "compat.yaml"
    path.write_text("n: 1\nn: 2\ngroup:\n  n: 3\n  n: 4\n")
    with pytest.warns(UserWarning, match="Duplicate key") as caught:
        result, _ = Loader().load_file(path)
    assert len(caught) == 2
    assert result == {"n": 2, "group": {"n": 4}}


def test_direct_loader_and_pairs_are_strict_by_default(monkeypatch):
    monkeypatch.delenv("SPARKWHEEL_STRICT_KEYS", raising=False)
    with pytest.raises(ValueError, match="Duplicate key"):
        yaml.load("n: 1\nn: 2", CheckKeyDuplicatesYamlLoader)
    with pytest.raises(ValueError, match="Duplicate key"):
        check_key_duplicates([("n", 1), ("n", 2)])


def test_yaml_merges_keep_native_precedence(tmp_path):
    path = tmp_path / "merge.yaml"
    path.write_text(
        "first: &first {n: 1, a: 10}\nsecond: &second {n: 2, b: 20}\nmerged:\n  <<: [*first, *second]\n  n: 3\ninherited:\n  <<: [*first, *second]\n"
    )
    result, locations = Loader().load_file(path)
    assert result["merged"] == {"n": 3, "a": 10, "b": 20}
    assert result["inherited"] == {"n": 1, "a": 10, "b": 20}
    assert locations.get("merged::n").line == 5


def test_duplicate_in_merged_definition_is_rejected(tmp_path):
    path = tmp_path / "merge.yaml"
    path.write_text("base: &base {n: 1}\nmerged:\n  <<: *base\n  n: 2\n  n: 3\n")
    with pytest.raises(ValueError, match="Duplicate key"):
        Loader().load_file(path)


@pytest.mark.parametrize("include", [False, True])
def test_duplicate_edit_rolls_back_source_and_runtime(tmp_path, include):
    config = Config({"n": 1, "object": {"_target_": "builtins.dict", "n": "@n"}})
    runtime = config.resolve("object")
    source = config.get()
    namespace = config._imports
    path = tmp_path / "duplicate.yaml"
    path.write_text("n: 2\nn: 3\n")
    edit = {"other": f"%{path}::n"} if include else path
    with pytest.raises(ValueError, match="Duplicate key"):
        config.update(edit)
    assert config.get() is source
    assert config._imports is namespace
    assert config.resolve("object") is runtime
    assert config.get("n") == 1


def test_separate_files_and_explicit_updates_can_override(tmp_path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    first.write_text("n: 1\n")
    second.write_text("n: 2\n")
    config = Config().update(first).update(second)
    assert config.get("n") == 2
    config.update({"n": 3})
    assert config.resolve("n") == 3


def test_nested_locations_are_kept(tmp_path):
    path = tmp_path / "nested.yaml"
    path.write_text("group:\n  items:\n    - n: 2\n")
    _, locations = Loader().load_file(path)
    assert locations.get("group::items::0::n").line == 3


@pytest.mark.parametrize("body", ['n: 1\n"n": 2\n', "true: one\n1: two\n", "0x10: one\n16: two\n"])
def test_equivalent_yaml_keys_are_duplicates(body):
    with pytest.raises(ValueError, match="Duplicate key"):
        yaml.load(body, CheckKeyDuplicatesYamlLoader)


def test_inline_merge_source_is_checked_before_flattening():
    with pytest.raises(ValueError, match="Duplicate key"):
        yaml.load("group: {<<: {n: 1, n: 2}}", CheckKeyDuplicatesYamlLoader)


def test_quoted_merge_key_is_ordinary_text():
    value = yaml.load('base: &base {n: 1}\ngroup: {<<: *base, "<<": literal}', CheckKeyDuplicatesYamlLoader)
    assert value["group"] == {"n": 1, "<<": "literal"}
