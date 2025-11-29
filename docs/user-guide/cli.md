# CLI Overrides

Override configuration values from the command line with automatic file and override detection.

## Auto-Detection Pattern

!!! success "Dead Simple CLI Integration"
    **Just loop over CLI arguments** - `config.update()` automatically detects whether each string is a file path or an override!

    - Strings **with** `=` → Parsed as overrides (e.g., `key=value`, `=key=value`, `~key`)
    - Strings **without** `=` → Loaded as file paths
    - No manual separation needed!

## Quick Start

=== "argparse"

    ```python
    import argparse
    from sparkwheel import Config

    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    config = Config()
    for item in args.inputs:
        config.update(item)

    model = config.resolve("model")
    ```

    ```bash
    python train.py base.yaml exp.yaml optimizer::lr=0.01 model::dropout=0.1
    ```

=== "Click"

    ```python
    import click
    from sparkwheel import Config

    @click.command()
    @click.argument("inputs", nargs=-1, required=True)
    def train(inputs):
        config = Config()
        for item in inputs:
            config.update(item)

        model = config.resolve("model")

    if __name__ == "__main__":
        train()
    ```

    ```bash
    python train.py base.yaml exp.yaml optimizer::lr=0.01 model::dropout=0.1
    ```

=== "Typer"

    ```python
    import typer
    from sparkwheel import Config

    app = typer.Typer()

    @app.command()
    def train(inputs: list[str] = typer.Argument(None)):
        config = Config()
        for item in inputs or []:
            config.update(item)

        model = config.resolve("model")

    if __name__ == "__main__":
        app()
    ```

    ```bash
    python train.py base.yaml exp.yaml optimizer::lr=0.01 model::dropout=0.1
    ```

=== "Fire"

    ```python
    import fire
    from sparkwheel import Config

    class TrainCLI:
        def train(self, *inputs):
            config = Config()
            for item in inputs:
                config.update(item)

            model = config.resolve("model")

    if __name__ == "__main__":
        fire.Fire(TrainCLI)
    ```

    ```bash
    python train.py train base.yaml exp.yaml optimizer::lr=0.01 model::dropout=0.1
    ```

## Override Syntax

Three operators for fine-grained control:

| Operator | Syntax | Behavior | Example |
|----------|--------|----------|---------|
| **Compose** (default) | `key=value` | Merges dicts, extends lists | `model::lr=0.001` |
| **Replace** | `=key=value` | Completely replaces value | `=model={'_target_': 'ResNet'}` |
| **Delete** | `~key` | Removes key (errors if missing) | `~debug` |

!!! info "Type Inference"
    Values are automatically typed using `ast.literal_eval()`:

    - `lr=0.001` → `float`
    - `epochs=100` → `int`
    - `debug=True` → `bool`
    - `devices=[0,1,2]` → `list`
    - `config={'lr':0.001}` → `dict`
    - `name=resnet50` → `str` (fallback)

!!! note "The `=` Dual Purpose"
    - In `key=value` → Assignment operator (CLI syntax)
    - In `=key=value` → Replace operator prefix (config operator)

!!! tip "Adding Your Own Flags"
    The examples above show minimal integration. You can add your own flags (e.g., `--verbose`, `--device`) alongside the config inputs - Sparkwheel only cares about the arguments you pass to `config.update()`!

## Advanced: Manual Override Parsing

If you need to separate override parsing from application, use `parse_overrides()`:

```python
from sparkwheel import Config, parse_overrides

# Manually parse overrides
overrides = parse_overrides(["model::lr=0.001", "=optimizer={'type':'sgd'}", "~debug"])
# Result: {"model::lr": 0.001, "=optimizer": {"type": "sgd"}, "~debug": None}

config = Config()
config.update("base.yaml")
config.update(overrides)
```

!!! warning "parse_overrides() Syntax"
    `parse_overrides()` **only** supports `key=value` syntax (no `--key value` flag style).

## Schema Validation

Add continuous validation with dataclasses:

```python
import argparse
from dataclasses import dataclass
from sparkwheel import Config

@dataclass
class TrainingConfig:
    model: dict
    optimizer: dict
    trainer: dict

parser = argparse.ArgumentParser()
parser.add_argument("inputs", nargs="+")
args = parser.parse_args()

# Validates on every update!
config = Config(schema=TrainingConfig)
for item in args.inputs:
    config.update(item)  # Raises ValidationError if invalid

config.freeze()  # Lock the config
model = config.resolve("model")
```

**Usage:**
```bash
python train.py base.yaml optimizer::lr=0.001 trainer::epochs=100
```

!!! warning "Validation Errors"
    Invalid overrides raise `ValidationError` immediately - helps catch config errors early!

## Next Steps

- **[Configuration Basics](basics.md)** - Loading and accessing configs
- **[Operators](operators.md)** - Composition, replacement, and deletion
- **[Schema Validation](schema-validation.md)** - Type-safe configs with dataclasses
- **[API Reference](reference/)** - Full API documentation
