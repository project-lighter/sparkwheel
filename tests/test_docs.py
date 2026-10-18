"""The documentation's examples run, and their stated results (`# → value`) and error messages are real."""

import importlib.util
import re
import shlex
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from sparkwheel import Config

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "user-guide"
FENCE = re.compile(r"^( *)```(\w+)([^\n]*)\n(.*?)^\1```", re.MULTILINE | re.DOTALL)
ARROW = re.compile(r"^[=~]?([A-Za-z_]\w*):.*#[^→\n]*→ (.+)$", re.MULTILINE)

# Stands in for torch when it is not installed, so the instantiation examples still run
FAKE_TORCH = {
    "torch/__init__.py": "from . import nn, optim\n",
    "torch/nn.py": (
        "class Module:\n    def parameters(self):\n        return []\n"
        "class Linear(Module):\n    def __init__(self, in_features, out_features, bias=True):\n        pass\n"
        "class ReLU(Module):\n    def __init__(self, inplace=False):\n        pass\n"
        "class Sequential(Module):\n    def __init__(self, *args):\n        self.layers = list(args)\n"
    ),
    "torch/optim.py": "class Adam:\n    def __init__(self, params, lr=0.001, weight_decay=0):\n        self.params = params\n",
}


def _sections(page: Path) -> dict[str, str]:
    """`## Heading` -> its text."""
    parts = re.split(r"^## (.+)$", page.read_text(), flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def _fences(text: str) -> list[tuple[str, str, str]]:
    """(language, title, code) of each code block, in order."""
    blocks = []
    for indent, language, info, code in FENCE.findall(text):
        title = re.search(r'title="([^"]+)"', info)
        blocks.append((language, title.group(1) if title else "", textwrap.dedent(code) if indent else code))
    return blocks


def _build(inputs: list[str]) -> Config:
    """What `python train.py <inputs>` does with the inputs: update, check, then resolve everything."""
    config = Config()
    for item in inputs:
        config.update(item)
    config.check()
    config.resolve()
    return config


def _assert_arrows(config: Config, code: str) -> None:
    for key, expected in ARROW.findall(code):
        value = yaml.safe_load(expected)
        assert config.resolve(key) == (pytest.approx(value) if isinstance(value, float) else value), key


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    if importlib.util.find_spec("torch") is None:
        for name, source in FAKE_TORCH.items():
            (tmp_path / name).parent.mkdir(exist_ok=True)
            (tmp_path / name).write_text(source)
    imported = set(sys.modules)
    yield tmp_path
    for name in set(sys.modules) - imported:  # the examples' own modules, imported from this directory
        if name.split(".")[0] in ("model", "torch"):
            del sys.modules[name]


@pytest.mark.parametrize("heading", list(_sections(GUIDE / "quick-reference.md")))
def test_quick_reference(heading, workdir):
    titled: list[str] = []
    for language, title, code in _fences(_sections(GUIDE / "quick-reference.md")[heading]):
        if language == "yaml":
            (workdir / (title or "snippet.yaml")).write_text(code)
            titled += [title] if title else []
            _assert_arrows(_build(titled if title else ["snippet.yaml"]), code)  # titled files compose in order
        elif language == "python":
            exec(compile(code, f"quick-reference.md ({heading})", "exec"), {})
        elif language == "bash":
            for line in code.splitlines():
                command, _, expected = line.partition("  # → ")
                inputs = shlex.split(command)[2:]  # after `python train.py`
                config = _build(inputs)
                if expected:
                    key = inputs[-1].lstrip("=~").split("=")[0]
                    assert config.resolve(key) == yaml.safe_load(expected), line


def _troubleshooting():
    page = GUIDE / "troubleshooting.md"
    model = next(code for language, title, code in _fences(page.read_text()) if title == "model.py")
    for heading, text in list(_sections(page).items()):
        blocks = {language: code for language, _, code in _fences(text)}
        yield pytest.param(model, blocks, id=heading)


@pytest.mark.parametrize("model,blocks", _troubleshooting())
def test_troubleshooting_messages_are_real(model, blocks, workdir):
    (workdir / "model.py").write_text(model)
    (workdir / "config.yaml").write_text(blocks["yaml"])
    inputs = shlex.split(blocks["bash"])[2:] if "bash" in blocks else ["config.yaml"]
    with pytest.raises(Exception) as excinfo:
        config = Config()
        for item in inputs:
            config.update(item)
        config.check() if blocks["text"].startswith("Config check found") else config.resolve()
    assert str(excinfo.value).replace(f"{workdir.resolve()}/", "").strip() == blocks["text"].strip()


def test_expression_examples_pass_check(workdir, monkeypatch):
    """Every example on the expressions page passes `check()`, except the mistakes it shows."""
    from sparkwheel.resolver import Resolver

    monkeypatch.setattr(Resolver, "allow_missing_reference", True)  # the examples are excerpts
    for language, _, code in _fences((GUIDE / "expressions.md").read_text()):
        if language == "yaml" and "# Bad" not in code and "Error" not in code:
            (workdir / "snippet.yaml").write_text(code)
            Config().update("snippet.yaml").check()
