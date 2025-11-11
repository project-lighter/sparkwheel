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

config = Config.load("config.yaml")

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

### Other Special Keys

- `_disabled_`: Skip instantiation if `True`
- `_requires_`: Dependencies to resolve first
- `_target_`: Class or function path to instantiate

For complete details, see the [Advanced Features](advanced.md) and [API Reference](../reference/).
