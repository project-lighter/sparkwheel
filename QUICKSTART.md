# Quick Start Guide

Get up and running with Sparkwheel in 5 minutes!

## Installation

```bash
pip install sparkwheel
```

**Requirements:** Python 3.10+

## 5-Minute Tutorial

### 1. Create a YAML configuration

```yaml
# config.yaml
learning_rate: 0.001
batch_size: 32

# Reference other values with @
optimizer:
  _target_: torch.optim.Adam
  lr: "@learning_rate"

# Use expressions with $
total_batches: "$@batch_size * 10"

# Copy configurations with %
train_config:
  shuffle: true
  drop_last: true

val_config: "%train_config"
```

### 2. Load and use the configuration

```python
from sparkwheel import ConfigParser

# Load the config
parser = ConfigParser("config.yaml")
parser.parse()

# Access values
lr = parser["learning_rate"]  # 0.001
batch_size = parser["batch_size"]  # 32

# Get computed values
total = parser.get_parsed_content("total_batches")  # 320

# Instantiate components
optimizer = parser.get_parsed_content("optimizer", instantiate=True)
# Returns: Adam optimizer with lr=0.001
```

### 3. Key Features

#### References (`@`)
```yaml
base_value: 100
derived_value: "@base_value"  # References base_value
```

#### Expressions (`$`)
```yaml
a: 10
b: 20
sum: "$@a + @b"  # Evaluates to 30
```

#### Nested Access (`::`)
```yaml
model:
  hidden_dim: 128

classifier:
  in_features: "@model::hidden_dim"  # Access nested values
```

#### Macros (`%`)
```yaml
template:
  key1: value1
  key2: value2

copy: "%template"  # Copies entire template
```

#### Component Instantiation (`_target_`)
```yaml
model:
  _target_: torch.nn.Linear
  in_features: 10
  out_features: 5
```

## Environment Variables

Control behavior:

```bash
# Disable expression evaluation
export CONFIG_EVAL_EXPR=0

# Enable debug mode
export CONFIG_DEBUG=1

# Allow missing references (just warn)
export CONFIG_ALLOW_MISSING_REF=1

# Fail on duplicate YAML keys
export CONFIG_STRICT_KEYS=1
```

## Next Steps

- 📖 [Full Documentation](https://project-lighter.github.io/sparkwheel)
- 🚀 [Quick Start Tutorial](https://project-lighter.github.io/sparkwheel/getting-started/quickstart/)
- 📚 [User Guide](https://project-lighter.github.io/sparkwheel/user-guide/basics/)
- 💡 [Examples](https://project-lighter.github.io/sparkwheel/examples/simple/)
- 🤝 [Contributing](CONTRIBUTING.md)

## Common Patterns

### Pattern 1: PyTorch Training Setup

```yaml
model:
  _target_: torchvision.models.resnet18
  pretrained: false
  num_classes: 10

optimizer:
  _target_: torch.optim.Adam
  params: "$@model.parameters()"
  lr: 0.001

criterion:
  _target_: torch.nn.CrossEntropyLoss
```

### Pattern 2: Shared Configurations

```yaml
# Define once
base_transform:
  resize: 224
  normalize: true

# Reuse multiple times
train_transform: "%base_transform"
val_transform: "%base_transform"
test_transform: "%base_transform"
```

### Pattern 3: Conditional Components

```yaml
use_feature: false

feature:
  _target_: SomeClass
  _disabled_: "$not @use_feature"  # Skip if use_feature is false
```

## Key Features

1. **YAML-only**: Focused on YAML for simplicity and readability
2. **Explicit paths**: Must use full module paths (e.g., `torch.nn.Linear`, not just `Linear`)
3. **Simple**: No automatic module scanning - just configuration
4. **Environment variables**: Control behavior with `CONFIG_*` env vars
5. **Standalone**: Minimal dependencies (just PyYAML)
6. **Well documented**: Comprehensive documentation and examples

## Getting Help

- 📖 [Documentation](https://project-lighter.github.io/sparkwheel)
- 🐛 [Report Issues](https://github.com/project-lighter/sparkwheel/issues)
- 💬 [Discussions](https://github.com/project-lighter/sparkwheel/discussions)
