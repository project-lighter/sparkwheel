"""Executable controls for the quick reference's real expression/CLI examples."""

import re
import shlex
from pathlib import Path

import yaml

from sparkwheel import Config

PAGE = Path(__file__).resolve().parents[1] / "docs/user-guide/quick-reference.md"


def test_expression_table_uses_supported_python():
    table = PAGE.read_text().split('=== "Expressions"', 1)[1].split('=== "Operators"', 1)[0]
    expressions = re.findall(r"`(\$[^`]+)`", table)
    source = {
        "a": 2,
        "b": 3,
        "lr": 1,
        "name": "sample",
        "model_name": "model",
        "debug": True,
        "is_training": False,
        "items": [7],
        "datasets": {"train": 8},
        "mode": "train",
        "layers": [1, 2],
    }
    results = [Config({**source, "result": expression}).resolve("result") for expression in expressions]
    assert results == [5, 0.1, "sample_v2", "model_trained", "dev", 0.0, 7, 8, 1, 2]


def test_cli_examples_preserve_nested_paths_and_shell_words():
    page = PAGE.read_text()
    commands = re.findall(r"^\s*python train\.py (.+)$", page, flags=re.MULTILINE)
    config = Config({"model": {"hidden_size": 1, "dropout": 0}, "optimizer": {"lr": 0}, "layers": []})
    for command in commands:
        for argument in shlex.split(command):
            config.update(argument)
    assert config.get("model") == {"hidden_size": 1024}
    assert config.get("optimizer::lr") == 0.001
    assert config.get("layers") == [128, 256, 512]
    assert not any("." in key for key in config.get())


def test_delete_example_uses_valid_null_value():
    page = PAGE.read_text()
    deletion = re.search(r"`(~debug: [^`]+)`", page).group(1)
    config = Config({"debug": True}).update(yaml.safe_load(deletion))
    assert config.get() == {}
