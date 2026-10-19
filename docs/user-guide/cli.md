# CLI Overrides

Override configuration values from the command line with automatic file and override detection.

## Auto-Detection Pattern

!!! success "Dead Simple CLI Integration"
    **Just loop over CLI arguments** - `config.update()` automatically detects whether each string is a file path or an override!

    - Strings naming an existing file → Loaded as files (so `runs/lr=0.1/config.yaml` works)
    - Other strings **with** `=` or starting with `~` → Parsed as overrides (e.g., `key=value`, `+key=value`, `~key`)
    - Everything else → Loaded as file paths
    - No manual separation needed!

!!! tip "Same statements as YAML"
    An override is one statement: `key=value` sets, `+key=value` combines, `~key` deletes, exactly like `key:`, `+key:` and `~key` in a file. See [Set, Combine, Delete](operators.md).

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

Nested keys are separated by `::` (`model::lr=0.001`, not `model.lr`).

| Statement | Syntax | Behavior | Example |
|-----------|--------|----------|---------|
| **Set** | `key=value` | Replaces the value (a dict, list or scalar) | `model::lr=0.001`, `devices=[0,1]` |
| **Combine** | `+key=value` | Merges a dict into a dict, appends a list to a list, or adds a new key | `'+trainer={max_epochs: 5}'`, `+callbacks=[ema]` |
| **Delete** | `~key` | Removes the key (errors if missing) | `~debug`, `~callbacks::0`, `'~callbacks=[0, 2]'` |

Setting a `_target_` component to a dict without `_target_` is an error that suggests `+key` or a `::` path, since it would drop the class: write `model::lr=0.01` or `'+model={lr: 0.01}'`.

!!! warning "`key=value` changes keys that exist"
    `key=value` may set any key that already exists, add one argument (or a special key such as `_disabled_`) directly under a `_target_` component, or give a dict a `_target_`. Anything else is most likely a typo, so it raises an error instead of adding a key that nothing reads:

    ```
    'trainer::max_epoch' does not exist

    [override → trainer::max_epoch]:
      → trainer::max_epoch=5

      💡 Did you mean 'max_epochs'? To add a new key, write '+trainer::max_epoch=5'.
    ```

    `+key=value` may add a key, but the keys above it must exist.

!!! info "Values are YAML"
    Override values are parsed with the same rules as your YAML files:

    - `lr=0.001` → `float` (`lr=1e-3` too)
    - `epochs=100` → `int`
    - `debug=true` → `bool`
    - `devices=[0,1,2]` → `list`
    - `'optimizer={lr: 0.001}'` → `dict` (YAML needs the space after `:`; quote it for your shell)
    - `name=resnet50` → `str`

!!! note "No `=key=value`"
    Before Sparkwheel 0.1, `=key=value` replaced a value. Setting now always replaces, so write `key=value`; the old form is an error that says so.

!!! tip "Adding Your Own Flags"
    The examples above show minimal integration. You can add your own flags (e.g., `--verbose`, `--device`) alongside the config inputs - Sparkwheel only cares about the arguments you pass to `config.update()`!

## Check Before Running

`config.check()` finds mistakes without building anything: `@` references that don't exist, `_target_`s and `_imports_` that can't be imported, `_mode_`s that don't exist, arguments the target doesn't accept or is missing, and `$` expressions that don't compile. It raises one `ValidationError` that lists every problem with its file:line or override, so call it right after applying the command line:

```python
config = Config()
for item in args.inputs:
    config.update(item)
config.check()
```

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
- **[Set, Combine, Delete](operators.md)** - What `key`, `+key` and `~key` do
- **[Schema Validation](schema-validation.md)** - Type-safe configs with dataclasses
- **[API Reference](reference/)** - Full API documentation
