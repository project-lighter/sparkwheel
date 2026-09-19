# Sparkwheel

Compose configuration, then build ordinary Python objects.

Sparkwheel loads YAML or Python dictionaries, combines settings, and calls your
classes and functions. Your application keeps its normal Python code. `@` shares
a resolved object; `%` copies a definition for separate construction.

**Development version:** this checkout is `0.1.0.dev0`, an unpublished development
package. The documentation describes this source, not necessarily the version
available on PyPI. Python 3.10 or newer is required; the installation below uses
Python 3.11. Torch and Lightning are not required.

From the supplied source checkout matching this documentation:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

See [installation](docs/getting-started/installation.md) for Windows activation
and source-checkout instructions.

```python
from sparkwheel import Config

config = Config().update(
    {
        "words": ["red", "blue", "red"],
        "counts": {"_target_": "collections.Counter", "_args_": ["@words"]},
    }
)

print(dict(config.resolve("counts")))  # {'red': 2, 'blue': 1}
```

`get()` reads the authored configuration. `resolve()` can import modules, evaluate
expressions and construct objects. Use configuration from sources you trust.

| I want to… | Start here |
|---|---|
| Run a complete Python/YAML example | [Quick start](docs/getting-started/quickstart.md) |
| Understand source, objects and edits | [Configuration model](docs/user-guide/basics.md) |
| Share objects or copy definitions | [References](docs/user-guide/references.md) |
| Use my own classes and functions | [Python authoring](docs/user-guide/instantiation.md) |
| Combine files and command-line changes | [Composition](docs/user-guide/operators.md) · [CLI](docs/user-guide/cli.md) |
| Diagnose a configuration | [Troubleshooting](docs/user-guide/troubleshooting.md) |
| Look up syntax or APIs | [Quick reference](docs/user-guide/quick-reference.md) · [Documentation](https://project-lighter.github.io/sparkwheel/) |

Sparkwheel grew from MONAI Bundle's configuration system and now serves
standalone Python projects and [Lighter](https://github.com/project-lighter/lighter).
It is licensed under Apache 2.0. Report issues on
[GitHub](https://github.com/project-lighter/sparkwheel/issues).
