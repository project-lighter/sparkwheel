"""Update operators have the same meaning in existing and newly authored trees."""

import pytest

from sparkwheel import Config
from sparkwheel.utils.exceptions import ConfigMergeError


@pytest.mark.parametrize(
    "source",
    [
        {"group": {"=n": 1}},
        {"=group": {"=n": 1}},
        {"group": {"=n": 1}, "items::kept": 2},
        {"=group": {"=n": 1}, "items::kept": 2},
    ],
)
def test_new_subtree_operators_are_applied(source):
    config = Config({"items": {"kept": 1}}).update(source)
    assert config.get("group") == {"n": 1}
    assert config.resolve("group") == {"n": 1}
    assert source["group" if "group" in source else "=group"] == {"=n": 1}


@pytest.mark.parametrize("initial", [{}, {"group": 0}, {"group": {"n": 0}}])
def test_nested_operator_meaning_does_not_depend_on_existing_parent(initial):
    config = Config(initial).update({"group": {"=n": 1}})
    assert config.get("group") == {"n": 1}


@pytest.mark.parametrize(
    "patch",
    [
        {"values": [{"=n": 1}]},
        {"=values": [{"=n": 1}]},
        {"values": [{"=n": 1}], "other::n": 3},
    ],
)
def test_nested_operators_in_new_list_entries(patch):
    config = Config({"values": [{"kept": 2}], "other": {"n": 0}}).update(patch)
    assert config.get("values")[-1] == {"n": 1}
    if "=values" not in patch:
        assert config.get("values")[0] == {"kept": 2}


@pytest.mark.parametrize(
    "patch",
    [
        {"fresh": {"~missing": None}},
        {"=fresh": {"~missing": None}},
        {"fresh": [{"~missing": None}]},
        {"items::kept": 2, "fresh": {"~missing": None}},
    ],
)
def test_missing_removal_in_new_subtree_rolls_back(patch):
    config = Config({"items": {"kept": 1}, "object": {"_target_": "builtins.dict"}})
    instance = config.resolve("object")
    source = config.get()
    imports = config._imports
    with pytest.raises(ConfigMergeError, match="missing"):
        config.update(patch)
    assert config.get() is source
    assert config._imports is imports
    assert config.resolve("object") is instance
    assert config.get("items::kept") == 1


def test_direct_set_remains_exact_assignment():
    config = Config()
    config.set("payload", {"=literal": 1})
    assert config.get("payload") == {"=literal": 1}
    config.update({"other": 2})
    assert config.get("payload") == {"=literal": 1}


def test_nonstring_key_in_mixed_path_update_normalizes_its_value():
    config = Config({"other": {"n": 0}}).update({1: {"=n": 1}, "other::n": 2})
    assert config.get("1") == {"n": 1}
    assert config.get("other::n") == 2
