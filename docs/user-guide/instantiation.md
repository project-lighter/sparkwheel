# Instantiation

Create Python objects directly from configuration using the `_target_` key.

## Basic Instantiation

```yaml
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10
```

```python
from sparkwheel import Config

config = Config()
config.update("config.yaml")

# Instantiate the object
model = config.resolve("model")
# model is now a torch.nn.Linear(784, 10) instance!
```

## The `_target_` Key

`_target_` specifies the full Python path to a class or function:

```yaml
examples:
  # Class instantiation
  linear:
    _target_: torch.nn.Linear
    in_features: 100
    out_features: 10

  # Class with multiple parameters
  adam:
    _target_: torch.optim.Adam
    params: "$@model.parameters()"
    lr: 0.001
    betas: [0.9, 0.999]

  # Custom class
  custom:
    _target_: myproject.models.CustomModel
    hidden_size: 256
```

## Positional Arguments with `_args_`

Use `_args_` to pass positional arguments to classes or functions that require them:

```yaml
# Basic example with list()
my_list:
  _target_: builtins.list
  _args_:
    - [1, 2, 3, 4, 5]
  # Equivalent to: list([1, 2, 3, 4, 5])

# torch.nn.Sequential requires positional args
model:
  _target_: torch.nn.Sequential
  _args_:
    - _target_: torch.nn.Linear
      in_features: 784
      out_features: 128
    - _target_: torch.nn.ReLU
    - _target_: torch.nn.Linear
      in_features: 128
      out_features: 10
  # Equivalent to: nn.Sequential(Linear(784, 128), ReLU(), Linear(128, 10))
```

### Mixing `_args_` and Keyword Arguments

You can combine positional arguments with keyword arguments:

```yaml
pipeline:
  _target_: sklearn.pipeline.Pipeline
  _args_:
    - - scaler:
          _target_: sklearn.preprocessing.StandardScaler
      - model:
          _target_: sklearn.linear_model.LogisticRegression
  memory: null  # Keyword argument
  verbose: true  # Keyword argument
```

!!! note "List Requirement"
    `_args_` must always be a list, even if you're only passing a single positional argument. Each item in the list becomes a positional argument in order.

## Nested Instantiation

Instantiate objects within objects:

```yaml
# Nested components
transform:
  _target_: torchvision.transforms.Compose
  transforms:
    - _target_: torchvision.transforms.Resize
      size: [224, 224]
    - _target_: torchvision.transforms.ToTensor
    - _target_: torchvision.transforms.Normalize
      mean: [0.485, 0.456, 0.406]
      std: [0.229, 0.224, 0.225]
```

## Complex Example

```yaml
# Complete training setup
dataset:
  path: "/data/cifar10"

transform:
  _target_: torchvision.transforms.Compose
  transforms:
    - _target_: torchvision.transforms.ToTensor
    - _target_: torchvision.transforms.Normalize
      mean: [0.5, 0.5, 0.5]
      std: [0.5, 0.5, 0.5]

dataloader:
  _target_: torch.utils.data.DataLoader
  dataset: "@dataset"
  batch_size: 32
  shuffle: true

model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10

optimizer:
  _target_: torch.optim.Adam
  params: "$@model.parameters()"
  lr: 0.001
```

## Special Keys

### `_mode_` - Instantiation Modes

Control how objects are instantiated with `_mode_`:

```yaml
# Default: instantiate normally
model:
  _target_: torch.nn.Linear
  _mode_: "default"  # Optional, this is the default
  in_features: 784
  out_features: 10
  # Returns: Linear(in_features=784, out_features=10)

# Callable: return the class/function, not an instance
model_factory:
  _target_: torch.nn.Linear
  _mode_: "callable"
  in_features: 784
  # Returns: functools.partial(torch.nn.Linear, in_features=784)

# Debug: run in debugger
debug_component:
  _target_: mymodule.MyClass
  _mode_: "debug"
  # Runs in pdb debugger
```

### `_disabled_` - Skip Instantiation

Skip instantiation of a component without removing it from config:

```yaml
callbacks:
  - _target_: pytorch_lightning.callbacks.EarlyStopping
    monitor: val_loss
    patience: 3
  - _target_: pytorch_lightning.callbacks.ModelCheckpoint
    _disabled_: true  # This callback is removed from the list
    save_top_k: 3
```

**Behavior:**

- When `_disabled_: true`, the component is skipped entirely
- **Inline in lists/dicts**: Disabled components are **removed** from the parent structure
- **Direct resolution**: `config.resolve("disabled_component")` returns `None`
- **References**: `@disabled_component` resolves to `None`
- Default is `false` (component is enabled)
- Accepts boolean values (`true`/`false`) or strings (`"true"`/`"false"`, case-insensitive)
- The config is preserved—you can re-enable by setting `_disabled_: false`

**Use cases:**

```yaml
# Temporarily disable a feature for debugging
scheduler:
  _target_: torch.optim.lr_scheduler.CosineAnnealingLR
  _disabled_: true  # Disable while debugging optimizer issues
  optimizer: "@optimizer"
  T_max: 100

# Environment-specific components
profiler:
  _target_: pytorch_lightning.profilers.PyTorchProfiler
  _disabled_: "$not os.environ.get('ENABLE_PROFILER')"  # Expression support

# A/B testing configurations
augmentation:
  _target_: torchvision.transforms.RandomErasing
  _disabled_: false  # Toggle between experiments
  p: 0.5
```

!!! tip "Disabled vs Deleted"
    Use `_disabled_` when you want to keep the config for future use. Use the delete operator (`~key: null`) when you want to permanently remove a key.

### Other Special Keys

- `_target_`: Class or function path to instantiate (required)
- `_args_`: List of positional arguments to pass
- `_disabled_`: Skip instantiation if `true` (removed from parent)
- `_mode_`: Instantiation mode (`"default"`, `"callable"`, or `"debug"`)

For complete details, see the [Advanced Features](advanced.md) and [API Reference](../reference/).
