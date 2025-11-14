# Quick Start

Get productive with Sparkwheel in 5 minutes.

## Installation

```bash
pip install sparkwheel
```

## Your First Config

Create a file `config.yaml`:

```yaml
# config.yaml
dataset:
  path: "/data/train"
  num_classes: 10
  batch_size: 32

model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: "@dataset::num_classes"  # Reference!

training:
  epochs: 10
  learning_rate: 0.001
  steps_per_epoch: "$10000 // @dataset::batch_size"  # Expression!
```

Load and use it in Python:

```python
from sparkwheel import Config

# Load the config
config = Config.load("config.yaml")

# Access values with path notation
batch_size = config["dataset::batch_size"]  # 32
epochs = config["training::epochs"]  # 10

# Resolve references and expressions
steps = config.resolve("training::steps_per_epoch")  # 312 (10000 // 32)

# Instantiate objects
model = config.resolve("model")  # Actual torch.nn.Linear(784, 10) instance!

print(f"Training for {epochs} epochs with batch size {batch_size}")
print(f"Model: {model}")
```

**That's it!** You just:

- ✓ Loaded a YAML config
- ✓ Referenced resolved values with `@` (gets instantiated/computed results)
- ✓ Computed values with `$` (Python expressions)
- ✓ Instantiated a Python object from config with `_target_`

!!! tip "Two Types of References"
    - `@` = **Resolved reference** - gets the final instantiated/evaluated value
    - `%` = **Raw reference** - copies unprocessed YAML content (from same or external file)

## Experiment Without Copying

Create a variant without duplicating the base config (merges automatically!):

```yaml
# experiment_large.yaml
model:  # Merges by default - no operator needed!
  in_features: 1568  # Override just this
  # out_features is still @dataset::num_classes

training:
  learning_rate: 0.0001  # Lower learning rate
  # epochs and steps_per_epoch inherited from base
```

Load both configs:

```python
config = Config.load(["config.yaml", "experiment_large.yaml"])

model = config.resolve("model")  # Linear(1568, 10) - merged automatically!
lr = config["training::learning_rate"]  # 0.0001
epochs = config["training::epochs"]  # 10 (inherited)
```

**Sparkwheel composes by default!** Dicts merge and lists extend - no operators needed for the common case.

## CLI Overrides

Override values from the command line without editing files:

```python
# train.py
from sparkwheel import Config
import sys

config = Config.from_cli("config.yaml", sys.argv[1:])
# ... use config ...
```

Run with overrides:

```bash
python train.py training::learning_rate=0.01 dataset::batch_size=64
```

## Next Steps

Now that you've seen the basics:

- **[Core Concepts](../user-guide/basics.md)** - Learn more about references, expressions, and instantiation
- **[Examples](../examples/simple.md)** - See complete real-world examples
- **[Composition & Operators](../user-guide/operators.md)** - Master config composition with `=` and `~`
- **[Schema Validation](../user-guide/schema-validation.md)** - Validate configs with dataclasses
