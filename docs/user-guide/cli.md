# CLI Support

Sparkwheel provides built-in utilities for parsing command-line configuration overrides, making it easy to build CLI applications that use YAML configs with runtime overrides.

## Quick Start

```python
from sparkwheel import Config

# Load config with CLI overrides
config = Config.from_cli(
    "config.yaml",
    ["model::lr=0.001", "trainer::max_epochs=100"]
)
```

That's it! Your config is loaded and overrides are applied.

## CLI Override Format

Overrides use Sparkwheel's path notation with `::` separators:

```bash
key::path=value
```

### Basic Examples

```bash
# Simple key
debug=True

# Nested path
model::lr=0.001

# Deeply nested
system::model::optimizer::lr=0.001
```

## Type Parsing

Values are automatically parsed as Python literals when possible:

### Integers

```bash
trainer::max_epochs=100    # Parsed as int: 100
```

### Floats

```bash
model::lr=0.001           # Parsed as float: 0.001
```

### Booleans

```bash
debug=True                # Parsed as bool: True
trainer::fast_dev_run=False  # Parsed as bool: False
```

### None

```bash
model::scheduler=None     # Parsed as None
```

### Lists

```bash
trainer::devices=[0,1,2]  # Parsed as list: [0, 1, 2]
model::layers=[128,256,512]  # Nested int list
```

### Dicts

```bash
model::config={'dropout':0.1,'activation':'relu'}
# Parsed as dict: {"dropout": 0.1, "activation": "relu"}
```

### Strings

If parsing fails, values are kept as strings:

```bash
model::name=resnet50      # Parsed as string: "resnet50"
path=/data/train          # String with special chars
```

## Using Config.from_cli()

The `Config.from_cli()` method is the easiest way to load configs with CLI overrides:

```python
from sparkwheel import Config

config = Config.from_cli(
    source="config.yaml",           # Config file(s)
    cli_overrides=["model::lr=0.001"],  # CLI overrides
    schema=MySchema,                # Optional validation
    globals={"torch": "torch"}      # Optional globals
)
```

### Parameters

- **source**: File path, list of paths, or dict (same as `Config.load()`)
- **cli_overrides**: List of override strings in format `"key::path=value"`
- **schema**: Optional dataclass schema for validation
- **globals**: Optional globals for expression evaluation

### Examples

**Single file with overrides:**

```python
config = Config.from_cli(
    "config.yaml",
    ["model::lr=0.001", "trainer::max_epochs=100"]
)
```

**Multiple files (merged in order):**

```python
# Files are merged, then overrides applied
config = Config.from_cli(
    ["base.yaml", "experiment.yaml", "prod.yaml"],
    ["model::lr=0.001", "trainer::devices=[0,1,2]"]
)

# Later files override earlier ones, CLI overrides applied last
```

**With schema validation:**

```python
from dataclasses import dataclass

@dataclass
class TrainingConfig:
    model: dict
    trainer: dict

config = Config.from_cli(
    "config.yaml",
    ["model::lr=0.001"],
    schema=TrainingConfig  # Validates after overrides
)
```

**No overrides:**

```python
# Empty list is fine
config = Config.from_cli("config.yaml", [])
```

## Lower-Level API

For more control, use the parsing functions directly:

### parse_override()

Parse a single override string:

```python
from sparkwheel import parse_override

key, value = parse_override("model::lr=0.001")
print(key)    # "model::lr"
print(value)  # 0.001 (float)
```

### parse_overrides()

Parse multiple override strings:

```python
from sparkwheel import parse_overrides

overrides = parse_overrides([
    "model::lr=0.001",
    "trainer::max_epochs=100",
    "trainer::devices=[0,1,2]"
])

print(overrides)
# {
#     "model::lr": 0.001,
#     "trainer::max_epochs": 100,
#     "trainer::devices": [0, 1, 2]
# }
```

### Manual Application

You can manually apply overrides:

```python
from sparkwheel import Config, parse_overrides

# Load base config
config = Config.load("config.yaml")

# Parse overrides
overrides = parse_overrides(["model::lr=0.001"])

# Apply manually
for key, value in overrides.items():
    config.set(key, value)
```

## Building a CLI Application

Sparkwheel's CLI utilities work seamlessly with popular argument parsers.

### Using Python Fire

```python
# train.py
import fire
from sparkwheel import Config

class Trainer:
    def fit(self, config: str, *overrides: str):
        """Train a model."""
        # Parse comma-separated config files
        configs = config.split(",") if "," in config else config
        cfg = Config.from_cli(configs, list(overrides))

        resolved = cfg.resolve()
        print(f"Training with lr={resolved['model']['lr']}")
        # ... training logic ...

    def test(self, config: str, *overrides: str):
        """Test a model."""
        cfg = Config.from_cli(config, list(overrides))
        # ... testing logic ...

if __name__ == "__main__":
    fire.Fire(Trainer)
```

**Usage:**

```bash
# Single config
python train.py fit config.yaml model::lr=0.001

# Multiple configs (merged in order)
python train.py fit base.yaml,experiment.yaml model::lr=0.001

# Multiple overrides
python train.py fit config.yaml \
  model::lr=0.001 \
  trainer::max_epochs=50 \
  trainer::devices=[0,1,2,3]
```

### Using argparse

```python
# train.py
import argparse
from sparkwheel import Config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Config file(s), comma-separated")
    parser.add_argument("overrides", nargs="*", help="Config overrides")
    args = parser.parse_args()

    # Support multiple config files
    configs = args.config.split(",")
    config = Config.from_cli(configs, args.overrides)

    resolved = config.resolve()
    print(f"Training with lr={resolved['model']['lr']}")
    # ... use config ...

if __name__ == "__main__":
    main()
```

**Usage:**

```bash
# Single config
python train.py config.yaml model::lr=0.001

# Multiple configs
python train.py base.yaml,experiment.yaml model::lr=0.001 trainer::max_epochs=100
```

### Using Typer

```python
# train.py
import typer
from typing import List, Optional
from sparkwheel import Config

app = typer.Typer()

@app.command()
def fit(
    config: str,
    overrides: Optional[List[str]] = typer.Argument(None)
):
    """Train a model."""
    configs = config.split(",")
    cfg = Config.from_cli(configs, overrides or [])

    resolved = cfg.resolve()
    typer.echo(f"Training with lr={resolved['model']['lr']}")
    # ... training logic ...

if __name__ == "__main__":
    app()
```

**Usage:**

```bash
# Single config
python train.py fit config.yaml model::lr=0.001

# Multiple configs
python train.py fit base.yaml,experiment.yaml \
  model::lr=0.001 \
  trainer::max_epochs=50
```

### Using Click

```python
# train.py
import click
from sparkwheel import Config

@click.command()
@click.argument("config")
@click.argument("overrides", nargs=-1)
def fit(config: str, overrides: tuple):
    """Train a model."""
    configs = config.split(",")
    cfg = Config.from_cli(configs, list(overrides))

    resolved = cfg.resolve()
    click.echo(f"Training with lr={resolved['model']['lr']}")
    # ... training logic ...

if __name__ == "__main__":
    fit()
```

**Usage:**

```bash
# Single config
python train.py config.yaml model::lr=0.001

# Multiple configs
python train.py base.yaml,experiment.yaml \
  model::lr=0.001 \
  trainer::devices=[0,1,2]
```

## Advanced Usage

### Overriding References

CLI overrides work with references:

```yaml
# config.yaml
base_lr: 0.01
model:
  lr: "@base_lr"
```

```python
config = Config.from_cli(
    "config.yaml",
    ["base_lr=0.001"]  # Override the base value
)

resolved = config.resolve()
print(resolved["model"]["lr"])  # 0.001 (resolved reference)
```

### Overriding in Expressions

```yaml
# config.yaml
batch_size: 32
num_batches: 100
total_samples: "$@batch_size * @num_batches"
```

```python
config = Config.from_cli(
    "config.yaml",
    ["batch_size=64"]  # Change input to expression
)

resolved = config.resolve()
print(resolved["total_samples"])  # 6400 (64 * 100)
```

### Adding New Keys

CLI overrides can add new keys not in the base config:

```python
config = Config.from_cli(
    {"model": {"lr": 0.01}},
    [
        "model::dropout=0.1",      # Add new key
        "trainer::max_epochs=100"  # Add entire new section
    ]
)

print(config["model::dropout"])      # 0.1
print(config["trainer::max_epochs"]) # 100
```

### Complex Nested Structures

```bash
# Override nested lists
model::layer_sizes=[512,256,128]

# Override nested dicts
model::optimizer={'type':'adam','lr':0.001}

# Mix them
model::config={'layers':[128,256],'dropout':0.1}
```

## Integration with Other Features

### With Merge Directives

You can use merge directives in CLI overrides by including them in the key:

```python
from sparkwheel import Config

config = Config.load({"model": {"lr": 0.01, "hidden": 256}})

# Use merge directive in override
config.update({"+model::optimizer": {"lr": 0.001}})
```

Or load from files that use merge directives and override with CLI:

```python
config = Config.from_cli(
    ["base.yaml", "override.yaml"],  # Files with +/~ directives
    ["model::lr=0.001"]               # CLI overrides applied last
)
```

### With Instantiation

CLI overrides work seamlessly with `_target_` instantiation:

```yaml
# config.yaml
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10
```

```python
config = Config.from_cli(
    "config.yaml",
    ["model::out_features=100"]  # Override before instantiation
)

model = config.resolve("model")  # Instantiates with out_features=100
```

## Best Practices

### 1. Use :: for Paths

Always use `::` for nested paths in CLI overrides (not dots):

```bash
# ✅ Correct
model::optimizer::lr=0.001

# ❌ Wrong (dots are for expressions, not CLI)
model.optimizer.lr=0.001
```

### 2. Quote Complex Values

For complex strings or values with special shell characters:

```bash
# Strings with spaces
python app.py config.yaml "model::name=ResNet 50"

# Dicts/lists are fine without quotes (usually)
python app.py config.yaml model::layers=[128,256,512]
```

### 3. Validate After Overrides

Use schema validation to catch override errors:

```python
config = Config.from_cli(
    "config.yaml",
    cli_overrides,
    schema=MySchema  # Validates after applying overrides
)
```

### 4. Document Override Keys

Make it easy for users to know what can be overridden:

```python
def train(self, config: str, *overrides: str):
    """
    Train a model.

    Common overrides:
      - model::lr=0.001         Learning rate
      - trainer::max_epochs=100 Training epochs
      - trainer::devices=[0,1]  GPU devices
      - model::dropout=0.1      Dropout probability
    """
    cfg = Config.from_cli(config, list(overrides))
    # ...
```

### 5. Provide Sensible Defaults

Make most overrides optional by providing good defaults in your base config:

```yaml
# config.yaml - good defaults
model:
  lr: 0.001              # Sensible default
  hidden_size: 256       # Sensible default
  dropout: 0.1           # Sensible default

# Users only override what they need
# python app.py config.yaml model::lr=0.01
```

## Error Handling

### Invalid Format

```python
from sparkwheel import parse_override

try:
    parse_override("invalid_no_equals")
except ValueError as e:
    print(e)  # "Invalid override format: ..."
```

### Validation Errors

```python
from sparkwheel import Config, ValidationError

try:
    config = Config.from_cli(
        "config.yaml",
        ["model::lr=not_a_number"],
        schema=MySchema
    )
except ValidationError as e:
    print(f"Validation error: {e}")
```

## Common Patterns

### Hyperparameter Sweeps

```bash
# Sweep learning rates
for lr in 0.001 0.01 0.1; do
    python train.py fit config.yaml model::lr=$lr
done

# Grid search
for lr in 0.001 0.01; do
    for dropout in 0.1 0.2 0.3; do
        python train.py fit config.yaml \
            model::lr=$lr \
            model::dropout=$dropout
    done
done
```

### Environment-Specific Configs

```bash
# Development
python app.py run dev.yaml debug=True

# Production
python app.py run prod.yaml \
    database::pool_size=20 \
    cache::enabled=True
```

### Multiple Config Files with Overrides

```bash
# Base + experiment + CLI overrides
python train.py fit base.yaml,experiment.yaml \
    model::lr=0.001 \
    trainer::devices=[0,1,2,3]
```

### Debug Runs

```bash
# Quick debug run with overrides
python train.py fit config.yaml \
    trainer::max_epochs=1 \
    trainer::fast_dev_run=True \
    data::subset=0.01
```

### Configuration Validation

```python
# train.py
from sparkwheel import Config, ValidationError
import sys

def fit(config: str, *overrides: str):
    try:
        cfg = Config.from_cli(config, list(overrides), schema=AppConfig)
    except ValidationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Config is valid, proceed with training
    resolved = cfg.resolve()
    # ...
```

## Tips and Tricks

### Default Config Paths

```python
def fit(config: str = "config.yaml", *overrides: str):
    """Train with default config if none provided."""
    cfg = Config.from_cli(config, list(overrides))
    # ...
```

### Dry Run Mode

```python
def fit(config: str, *overrides: str, dry_run: bool = False):
    """Train model with optional dry run."""
    cfg = Config.from_cli(config, list(overrides))

    if dry_run:
        print("Config:", cfg.resolve())
        return

    # Actual training
    # ...
```

### Shell Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias train='python train.py fit'
alias train-debug='python train.py fit config.yaml trainer::max_epochs=1'

# Usage
train base.yaml,experiment.yaml model::lr=0.001
train-debug
```

## Next Steps

- [Configuration Basics](basics.md) - Learn about Sparkwheel's core features
- [References](references.md) - Using `@` references in configs
- [Schema Validation](schema-validation.md) - Validate configs with dataclasses
- [Merging](merging.md) - Combining multiple config files
