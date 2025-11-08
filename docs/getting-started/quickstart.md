# Quick Start

Get up and running with Sparkwheel in 5 minutes!

## Basic Usage

### 1. Create a Configuration File

Create a file `config.yaml`:

```yaml
# config.yaml
name: "My Project"
version: 1.0

paths:
  data: "/data/raw"
  output: "/data/processed"

training:
  batch_size: 32
  epochs: 10
  learning_rate: 0.001
```

### 2. Load the Configuration

```python
from sparkwheel import Config

# Load config (single line!)
config = Config.load("config.yaml")

# Access values - two equivalent syntaxes:
print(config["name"])  # "My Project"

# Nested dict access (standard Python)
print(config["training"]["batch_size"])  # 32

# Path notation with :: (more concise)
print(config["training::batch_size"])  # 32
```

## Using References

References let you link values together using `@`:

```yaml
# config.yaml
dataset:
  path: "/data/images"
  num_classes: 10
  image_size: 224

model:
  input_size: "@dataset::image_size"  # References dataset.image_size
  num_outputs: "@dataset::num_classes"  # References dataset.num_classes
```

```python
config = Config.load("config.yaml")

# The @ reference is automatically resolved
print(config.resolve("model::input_size"))  # 224
print(config.resolve("model::num_outputs"))  # 10
```

## Using Expressions

Execute Python code with `$`:

```yaml
# config.yaml
training:
  batch_size: 32
  total_samples: 10000
  steps_per_epoch: "$@training::total_samples // @training::batch_size"

data:
  # Create a list using Python
  values: "$[x**2 for x in range(5)]"

  # Import and use libraries
  pi: "$import math; math.pi"
```

```python
config = Config.load("config.yaml")

print(config.resolve("training::steps_per_epoch"))  # 312
print(config.resolve("data::values"))  # [0, 1, 4, 9, 16]
print(config.resolve("data::pi"))  # 3.14159...
```

## Creating Objects with `_target_`

Instantiate Python objects directly from configuration:

```yaml
# config.yaml
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

```python
from sparkwheel import Config

config = Config.load("config.yaml")

# Get the instantiated object
transform = config.resolve("transform")

# transform is now a torchvision.transforms.Compose object!
# You can use it directly
transformed_image = transform(image)
```

## Complete Example: Training Setup

Here's a realistic example combining all features:

```yaml
# training_config.yaml
dataset:
  path: "/data/cifar10"
  num_classes: 10
  image_size: 32

model:
  _target_: torch.nn.Linear
  in_features: "$@dataset::image_size ** 2 * 3"  # 32*32*3
  out_features: "@dataset::num_classes"

optimizer:
  _target_: torch.optim.Adam
  lr: 0.001
  # This references the model's parameters method
  params: "$@model.parameters()"

training:
  batch_size: 64
  epochs: 50
  device: "$'cuda' if torch.cuda.is_available() else 'cpu'"
```

```python
import torch
from sparkwheel import Config

# Load configuration
config = Config.load("training_config.yaml")

# Get instantiated objects
model = config.resolve("model")
optimizer = config.resolve("optimizer")
device = config.resolve("training::device")

# Everything is ready to use!
model = model.to(device)
print(f"Model: {model}")
print(f"Optimizer: {optimizer}")
print(f"Device: {device}")

# Training loop (simplified)
for epoch in range(config["training"]["epochs"]):
    # Your training code here
    pass
```

## Path Notation

Sparkwheel uses `::` as a separator for nested paths, making it easy to work with deeply nested configurations:

```yaml
data:
  train:
    path: "/data/train"
  test:
    path: "/data/test"

# Reference nested values using ::
validation:
  path: "@data::train::path"  # Accesses data.train.path
```

```python
# In Python, both syntaxes work:
train_path = config["data"]["train"]["path"]  # Standard dict access
train_path = config["data::train::path"]      # Path notation (same result!)
```

The `::` notation is especially useful for:
- Passing paths as strings: `config.get("model::optimizer::lr")`
- Deep nesting: `config["a::b::c::d::e"]` vs `config["a"]["b"]["c"]["d"]["e"]`
- Config references: `"@section::subsection::key"`

## Working with Lists

You can reference list elements by index:

```yaml
transforms:
  - resize
  - crop
  - normalize

preprocessing:
  first_step: "@transforms::0"  # References "resize"
  last_step: "@transforms::2"   # References "normalize"
```

## Why YAML?

Sparkwheel uses YAML because it:
- Supports comments for documentation
- Is more readable than JSON
- Handles multi-line strings naturally
- Is the standard for configuration files in the Python ecosystem

## Next Steps

Now that you understand the basics:

- [Configuration Basics](../user-guide/basics.md) - Learn more about config structure
- [References Guide](../user-guide/references.md) - Master the reference system
- [Expressions Guide](../user-guide/expressions.md) - Explore Python expressions
- [Instantiation Guide](../user-guide/instantiation.md) - Deep dive into object creation
- [Examples](../examples/simple.md) - See more real-world examples
