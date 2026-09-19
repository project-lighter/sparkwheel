"""Execute current documentation examples with independent expected results."""

import re
import shlex
from pathlib import Path

import yaml

from sparkwheel import Config

GUIDES = Path(__file__).resolve().parents[1] / "docs/user-guide"


def _section(page, heading):
    matches = re.findall(rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", page.read_text(), re.MULTILINE | re.DOTALL)
    assert len(matches) == 1, f"{page}: expected exactly one section {heading!r}, found {len(matches)}"
    return matches[0]


def _fence(section, language, location):
    matches = re.findall(rf"^```{language}\s*\n(.*?)^```\s*$", section, re.MULTILINE | re.DOTALL)
    assert len(matches) == 1, f"{location}: expected exactly one {language} fence, found {len(matches)}"
    return matches[0]


def _table_inputs(section, count, location):
    inputs = re.findall(r"^\|\s*`([^`]+)`\s*\|", section, re.MULTILINE)
    assert len(inputs) == count, f"{location}: expected {count} input rows, found {len(inputs)}"
    return inputs


def test_documented_basic_expressions():
    page = GUIDES / "expressions.md"
    code = _fence(_section(page, "Basic Expressions"), "python", page)
    namespace = {}
    exec(compile(code, str(page), "exec"), namespace)
    assert "config" in namespace, f"{page}: basic example must expose its configuration"
    config = namespace["config"]
    for name, expected in (("total", 3), ("double", 6)):
        result = config.resolve(name)
        assert result == expected
        assert type(result) is int


def test_quick_reference_cli_arguments_preserve_types_and_shell_words():
    page = GUIDES / "quick-reference.md"
    arguments = _table_inputs(_section(page, "CLI Overrides"), 5, page)
    expected_states = [
        ({"words": ["red"], "limit": 3}, "limit", int),
        ({"words": ["red"], "enabled": True}, "enabled", bool),
        ({"words": ["red"], "label": "true"}, "label", str),
        ({"words": ["blue"]}, "words", list),
        ({"words": []}, "words", list),
    ]
    for argument, (expected, key, expected_type) in zip(arguments, expected_states, strict=True):
        tokens = shlex.split(argument)
        assert len(tokens) == 1, f"{page}: override must remain one shell word: {argument!r}"
        config = Config({"words": ["red"]}).update(tokens[0])
        assert config.get() == expected
        assert type(config.get(key)) is expected_type


def test_cli_guide_preserves_nested_paths():
    page = GUIDES / "cli.md"
    arguments = _table_inputs(_section(page, "Override Syntax"), 6, page)
    config = Config({"report": {"title": "Before", "limit": 3}}).update(arguments[0])
    assert config.get() == {"report": {"title": "Example", "limit": 3}}
    assert config.get("report::title") == "Example"


def test_cli_commands_append_and_replace_independently():
    page = GUIDES / "cli.md"
    commands = _fence(_section(page, "Override Syntax"), "bash", page).strip().splitlines()
    assert len(commands) == 2, f"{page}: expected both append and replacement commands"
    expected_words = [["red", "blue", "red", "green"], ["green", "green"]]
    for command, expected in zip(commands, expected_words, strict=True):
        tokens = shlex.split(command)
        assert tokens[:2] == ["python", "run.py"], f"{page}: unexpected example command {command!r}"
        assert len(tokens) == 3, f"{page}: override must remain one shell word: {command!r}"
        config = Config({"words": ["red", "blue", "red"]}).update(tokens[2])
        assert config.get() == {"words": expected}


def test_delete_example_uses_valid_null_value():
    page = GUIDES / "quick-reference.md"
    section = _section(page, "Composition")
    matches = re.findall(r"^\|\s*`(~key: [^`]+)`\s*\|", section, re.MULTILINE)
    assert len(matches) == 1, f"{page}: expected exactly one whole-key deletion example"
    deletion = yaml.safe_load(matches[0])
    assert deletion == {"~key": None}
    config = Config({"key": True, "keep": "sentinel"}).update(deletion)
    assert config.get() == {"keep": "sentinel"}
