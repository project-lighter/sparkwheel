"""Config.check(): find config mistakes without building anything."""

import pytest

from sparkwheel import Config, ValidationError


@pytest.fixture(autouse=True)
def _module(tmp_path, monkeypatch):
    (tmp_path / "checkmod.py").write_text(
        "BUILT = []\nclass Model:\n    def __init__(self, learning_rate, dim=2):\n        BUILT.append(self)\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))


def _check(tmp_path, text, *overrides):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    config = Config().update(str(path))
    for override in overrides:
        config.update(override)
    config.check()
    return config


def test_valid_config_passes_without_building(tmp_path):
    import checkmod

    config = _check(
        tmp_path,
        "_imports_:\n  m: math\n"
        "n: 3\n"
        "model:\n  _target_: checkmod.Model\n  learning_rate: '$m.sqrt(@n)'\n"
        "opt:\n  _target_: checkmod.Model\n  _mode_: callable\n  dim: '@n'\n",
    )
    assert checkmod.BUILT == []
    assert config.resolve("model").__class__.__name__ == "Model"


def test_all_problems_are_listed_with_locations(tmp_path):
    text = (
        "num_classes: 3\n"
        "model:\n"
        "  _target_: checkmod.Model\n"
        "  learnin_rate: 0.1\n"
        "head:\n"
        "  _target_: checkmod.Modl\n"
        "out: '@num_clases'\n"
        "expr: '$(@num_classes'\n"
    )
    with pytest.raises(ValidationError) as excinfo:
        _check(tmp_path, text, "model::dim=@missing")
    msg = str(excinfo.value)
    path = tmp_path / "config.yaml"
    assert msg.startswith("Config check found 5 problems:")
    assert f"{path}:4 → model::learnin_rate: 'checkmod.Model' got an unexpected argument 'learnin_rate'" in msg
    assert "Did you mean 'learning_rate'?" in msg
    assert f"{path}:6 → head::_target_: Cannot locate class or function: 'checkmod.Modl'" in msg
    assert f"{path}:7 → out: Reference '@num_clases' not found" in msg
    assert f"{path}:8 → expr: Failed to evaluate expression '$(@num_classes'" in msg
    assert "override `model::dim=@missing` → model::dim: Reference '@missing' not found" in msg


def test_disabled_components_are_skipped(tmp_path):
    _check(
        tmp_path,
        "flag: true\n"
        "a:\n  _target_: checkmod.Nope\n  _disabled_: true\n  x: '@missing'\n"
        "b:\n  _target_: checkmod.Nope\n  _disabled_: '$@flag'\n",
    )


def test_import_statements_and_targets_given_as_references_are_accepted(tmp_path):
    _check(tmp_path, "os: '$import os'\ncls: '$dict'\nx:\n  _target_: '@cls'\n  a: 1\n")


def test_check_after_resolve_keeps_built_objects(tmp_path):
    config = _check(tmp_path, "model:\n  _target_: checkmod.Model\n  learning_rate: 1\n")
    model = config.resolve("model")
    config.check()
    assert config.resolve("model") is model
