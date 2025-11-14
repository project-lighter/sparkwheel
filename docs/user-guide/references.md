# References

Sparkwheel provides two types of references for linking configuration values:

- **`@` - Resolved References**: Get the final, instantiated/evaluated value
- **`%` - Raw References**: Get the unprocessed YAML content

## Resolved References (`@`)

Use `@` followed by the key path with `::` separator to reference **resolved values** (after instantiation, expression evaluation, etc.):

```yaml
dataset:
  path: "/data/images"
  num_classes: 10
  batch_size: 32

model:
  num_outputs: "@dataset::num_classes"

training:
  batch: "@dataset::batch_size"
```

```python
config = Config.load("config.yaml")

# References are resolved when you call resolve()
num_outputs = config.resolve("model::num_outputs")  # 10
batch = config.resolve("training::batch")  # 32
```

## List References

Reference list elements by index (0-based):

```yaml
transforms:
  - resize
  - normalize
  - augment

first_transform: "@transforms::0"  # "resize"
last_transform: "@transforms::2"   # "augment"
```

## Nested References

References can reference other references:

```yaml
base:
  value: 100

derived:
  double: "$@base::value * 2"  # 200

final:
  quad: "$@derived::double * 2"  # 400
```

## Resolution Order

Sparkwheel resolves references in dependency order:

```yaml
a: 10
b: "@a"              # Resolved first
c: "$@a + @b"        # Resolved after a and b
d: "$@c * 2"         # Resolved last
```

### Circular References

Circular references raise an error:

```yaml
# This will fail!
a: "@b"
b: "@a"
```

## Advanced Patterns

### Conditional References

```yaml
environment: "production"

database:
  prod_host: "prod.db.example.com"
  dev_host: "localhost"
  host: "$@database::prod_host if @environment == 'production' else @database::dev_host"
```

### Dynamic Selection

```yaml
datasets:
  train: "/data/train"
  test: "/data/test"
  val: "/data/val"

mode: "train"
current_dataset: "$@datasets[@mode]"  # Dynamically select based on mode
```

**Note:** This requires Python expression evaluation.

## Raw References (`%`)

Use `%` to reference **raw YAML content** (unprocessed, before instantiation/evaluation). Works with both external files and within the same file:

### External File Raw References

```yaml
# base.yaml
defaults:
  learning_rate: 0.001
  batch_size: 32

model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10

# experiment.yaml
training:
  lr: "%base.yaml::defaults::learning_rate"  # Gets raw value: 0.001
  batch: "%base.yaml::defaults::batch_size"   # Gets raw value: 32

# Gets the raw dict definition (with _target_), NOT the instantiated object
model_template: "%base.yaml::model"
```

### Local Raw References

```yaml
# config.yaml
defaults:
  timeout: 30
  retries: 3

# Copy raw YAML from same file
api_config:
  timeout: "%defaults::timeout"  # Gets raw value: 30

# Copy entire section
backup_defaults: "%defaults"  # Gets the whole defaults dict
```

### Key Distinction

| Reference Type | Symbol | What You Get | When To Use |
|----------------|--------|--------------|-------------|
| **Resolved Reference** | `@` | Final value after instantiation/evaluation | When you want the computed result or object instance |
| **Raw Reference** | `%` | Unprocessed YAML content | When you want to copy/reuse configuration definitions |

**Example showing the difference:**

```yaml
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10

# Resolved reference - gets the actual instantiated torch.nn.Linear object
trained_model: "@model"

# Raw reference - gets the raw dict with _target_, in_features, out_features
model_config_copy: "%model"
```

See [Advanced Features](advanced.md) for more on raw references.

## Common Use Cases

### Shared Hyperparameters

```yaml
# Single source of truth
model_config:
  hidden_size: 512

encoder:
  size: "@model_config::hidden_size"

decoder:
  size: "@model_config::hidden_size"
```

### Computed Values

```yaml
dataset:
  samples: 10000
  batch_size: 32

training:
  steps: "$@dataset::samples // @dataset::batch_size"  # 312
```

### Object Parameters

```yaml
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10

optimizer:
  _target_: torch.optim.Adam
  params: "$@model.parameters()"  # Call model's method
  lr: 0.001
```

## Next Steps

- **[Expressions](expressions.md)** - Execute Python code in configs
- **[Instantiation](instantiation.md)** - Create objects with references
- **[Advanced Features](advanced.md)** - Complex reference patterns
