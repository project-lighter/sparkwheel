# CLI Support

Parse command-line configuration overrides with built-in utilities.

## Quick Start

```python
from sparkwheel import Config

# Load config with CLI overrides
config = Config.from_cli(
    "config.yaml",
    ["model::lr=0.001", "trainer::max_epochs=100"]
)
```

## CLI Override Format

Overrides use path notation with `::` separators:

```bash
key::path=value
```

Examples:

```bash
# Simple key
debug=True

# Nested path
model::lr=0.001

# Deeply nested
system::model::optimizer::lr=0.001
```

## Type Parsing

Values are automatically parsed as Python literals:

| Input | Parsed As | Result |
|-------|-----------|--------|
| `100` | int | `100` |
| `0.001` | float | `0.001` |
| `True` | bool | `True` |
| `None` | None | `None` |
| `[0,1,2]` | list | `[0, 1, 2]` |
| `{'a':1}` | dict | `{"a": 1}` |
| `resnet50` | str | `"resnet50"` (fallback) |

If parsing fails, values are kept as strings.

## Using Config.from_cli()

The easiest way to load configs with CLI overrides:

```python
from sparkwheel import Config

config = Config.from_cli(
    source="config.yaml",              # Config file(s)
    cli_overrides=["model::lr=0.001"], # CLI overrides
    schema=MySchema,                   # Optional validation
    globals={"torch": "torch"}         # Optional globals
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
config = Config.from_cli(
    ["base.yaml", "experiment.yaml", "prod.yaml"],
    ["model::lr=0.001", "trainer::devices=[0,1,2]"]
)
# Files are merged, then overrides applied
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
config = Config.from_cli("config.yaml", [])  # Empty list is fine
```

## Building a CLI Application

Sparkwheel works seamlessly with argument parsers.

### Using argparse

```python
# train.py
import argparse
from sparkwheel import Config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Config file")
    parser.add_argument("overrides", nargs="*", help="Config overrides")
    args = parser.parse_args()

    config = Config.from_cli(args.config, args.overrides)

    # Use config
    resolved = config.resolve()
    print(f"Training with lr={resolved['model']['lr']}")

if __name__ == "__main__":
    main()
```

**Usage:**

```bash
python train.py config.yaml model::lr=0.001 trainer::max_epochs=100
```

### Using Python Fire

```python
# train.py
import fire
from sparkwheel import Config

class Trainer:
    def fit(self, config: str, *overrides: str):
        """Train a model."""
        cfg = Config.from_cli(config, list(overrides))

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
python train.py fit config.yaml model::lr=0.001

python train.py fit config.yaml \
  model::lr=0.001 \
  trainer::max_epochs=50 \
  trainer::devices=[0,1,2,3]
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

CLI overrides can add new keys:

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

### With Instantiation

CLI overrides work seamlessly with `_target_`:

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

## Lower-Level API

For more control, use parsing functions directly:

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

## Common Patterns

### Hyperparameter Sweeps

```bash
# Sweep learning rates
for lr in 0.001 0.01 0.1; do
    python train.py config.yaml model::lr=$lr
done

# Grid search
for lr in 0.001 0.01; do
    for dropout in 0.1 0.2 0.3; do
        python train.py config.yaml \
            model::lr=$lr \
            model::dropout=$dropout
    done
done
```

### Environment-Specific Overrides

```bash
# Development
python app.py dev.yaml debug=True

# Production
python app.py prod.yaml \
    database::pool_size=20 \
    cache::enabled=True
```

### Multiple Configs + CLI Overrides

```bash
# Base + experiment + CLI overrides
python train.py base.yaml,experiment.yaml \
    model::lr=0.001 \
    trainer::devices=[0,1,2,3]
```

Note: Comma-separate multiple config files.

### Debug Runs

```bash
# Quick debug run with overrides
python train.py config.yaml \
    trainer::max_epochs=1 \
    trainer::fast_dev_run=True \
    data::subset=0.01
```

## Best Practices

### Always Use :: for Paths

```bash
# ✅ Correct
model::optimizer::lr=0.001

# ❌ Wrong (dots are for expressions, not CLI)
model.optimizer.lr=0.001
```

### Quote Complex Values

For strings with spaces or special shell characters:

```bash
# Strings with spaces
python app.py config.yaml "model::name=ResNet 50"

# Dicts/lists usually don't need quotes
python app.py config.yaml model::layers=[128,256,512]
```

### Validate After Overrides

Use schema validation to catch override errors:

```python
config = Config.from_cli(
    "config.yaml",
    cli_overrides,
    schema=MySchema  # Validates after applying overrides
)
```

### Provide Sensible Defaults

Make most overrides optional:

```yaml
# config.yaml - good defaults
model:
  lr: 0.001        # Sensible default
  hidden_size: 256 # Sensible default

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

## Next Steps

- **[Configuration Basics](basics.md)** - Core config features
- **[Composition & Operators](operators.md)** - Config composition with `=` and `~`
- **[Schema Validation](schema-validation.md)** - Validate with dataclasses
