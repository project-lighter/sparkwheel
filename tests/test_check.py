"""Config.check(): find config mistakes without building anything."""

import pytest

from sparkwheel import Config, ValidationError


@pytest.fixture(autouse=True)
def _module(tmp_path, monkeypatch):
    (tmp_path / "checkmod.py").write_text(
        "BUILT = []\nclass Model:\n    def __init__(self, learning_rate, dim=2):\n        BUILT.append(self)\n"
    )
    (tmp_path / "brokenmod.py").write_text("import nonexistent_dependency_xyz\n")
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


def test_target_whose_module_fails_to_import_is_a_problem(tmp_path):
    with pytest.raises(ValidationError) as excinfo:
        _check(tmp_path, "model:\n  _target_: brokenmod.Model\nother: '@missing'\n")
    msg = str(excinfo.value)
    assert msg.startswith("Config check found 2 problems:")
    assert "config.yaml:2 → model::_target_: Cannot import 'brokenmod.Model': ModuleNotFoundError" in msg


def _problems(tmp_path, text, *overrides):
    with pytest.raises(ValidationError) as excinfo:
        _check(tmp_path, text, *overrides)
    return str(excinfo.value).replace(f"{tmp_path / 'config.yaml'}:", "config.yaml:")


def test_every_unknown_argument_is_listed(tmp_path):
    msg = _problems(tmp_path, "model:\n  _target_: checkmod.Model\n  learning_rate: 1\n  a: 1\n  b: 2\n")
    assert msg.startswith("Config check found 2 problems:")
    assert "config.yaml:4 → model::a: 'checkmod.Model' got an unexpected argument 'a'" in msg
    assert "config.yaml:5 → model::b: 'checkmod.Model' got an unexpected argument 'b'" in msg


def test_a_missing_argument_is_a_problem_unless_the_component_is_callable(tmp_path):
    msg = _problems(tmp_path, "model:\n  _target_: checkmod.Model\n  dim: 3\n")
    assert "config.yaml:1 → model: 'checkmod.Model' missing a required argument: 'learning_rate'" in msg
    _check(tmp_path, "model:\n  _target_: checkmod.Model\n  _mode_: callable\n  dim: 3\n")
    _check(tmp_path, "args: [1]\nmodel:\n  _target_: checkmod.Model\n  _args_: '@args'\n")


def test_a_misspelled_argument_is_not_also_reported_missing(tmp_path):
    msg = _problems(tmp_path, "model:\n  _target_: checkmod.Model\n  learnin_rate: 1\n")
    assert msg.startswith("Config check found 1 problem:")
    assert "Did you mean 'learning_rate'?" in msg


def test_an_unknown_mode_is_a_problem(tmp_path):
    msg = _problems(tmp_path, "opt:\n  _target_: checkmod.Model\n  _mode_: calable\n")
    assert "config.yaml:3 → opt::_mode_: Unknown _mode_ 'calable'" in msg
    assert "Did you mean 'callable'?" in msg


def test_a_failed_import_is_a_problem(tmp_path):
    msg = _problems(tmp_path, "_imports_:\n  np: numpyy\n  P: pathlib.Path\nx: 1\n")
    assert msg.startswith("Config check found 1 problem:")
    assert "config.yaml:2 → _imports_::np: Cannot import 'numpyy'" in msg


@pytest.mark.parametrize(
    "text, problem",
    [
        ("a:\n  b: '@::::::x'\n", "config.yaml:2 → a::b: Relative reference '@::::::' in '@::::::x' attempts"),
        ("a: '%nope'\n", "Error resolving raw reference '%nope'"),
    ],
)
def test_a_reference_that_cannot_be_expanded_is_a_problem(tmp_path, text, problem):
    msg = _problems(tmp_path, text)
    assert msg.startswith("Config check found 1 problem:")
    assert problem in msg


def test_a_component_disabled_by_a_reference_to_a_plain_value(tmp_path):
    component = "  _target_: checkmod.Model\n  _disabled_: '@flag'\n  oops: 1\n"
    _check(tmp_path, f"flag: true\nmodel:\n{component}")
    assert "got an unexpected argument 'oops'" in _problems(tmp_path, f"flag: false\nmodel:\n{component}")


def test_a_disabled_component_is_none_without_instantiating(tmp_path):
    config = Config().update({"model": {"_target_": "checkmod.Model", "_disabled_": True, "x": "@missing"}})
    assert config.resolve("model", instantiate=False) is None
