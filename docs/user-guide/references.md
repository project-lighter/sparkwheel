# References

Sparkwheel provides two types of references for linking configuration values:

- **`@` - Resolved References**: Get the final, instantiated/evaluated value
- **`%` - Raw References**: Get the unprocessed YAML content

## Quick Comparison

| Feature | `@ref` (Resolved) | `%ref` (Raw) | `$expr` (Expression) |
|---------|-------------------|--------------|----------------------|
| **Returns** | Final computed value | Raw YAML content | Evaluated expression result |
| **When processed** | Lazy (`resolve()`) | External: Eager / Local: Lazy | Lazy (`resolve()`) |
| **Instantiates objects** | ✅ Yes | ❌ No | ✅ Yes (if referenced) |
| **Evaluates expressions** | ✅ Yes | ❌ No | ✅ Yes |
| **Use in dataclass validation** | ✅ Yes | ⚠️ Limited | ✅ Yes |
| **CLI override compatible** | ✅ Yes | ✅ Yes | ❌ No |
| **Cross-file references** | ✅ Yes | ✅ Yes | ❌ No |
| **When to use** | Get computed results | Copy config structures | Compute new values |

## Two-Phase Processing Model

Sparkwheel processes raw references (`%`) in two phases to support CLI overrides:

!!! abstract "When References Are Processed"

    **Phase 1: Eager Processing (during `update()`)**

    - **External file raw refs (`%file.yaml::key`)** are expanded immediately
    - External files are frozen—their content won't change based on CLI overrides
    - Enables copy-then-delete workflows with external files

    **Phase 2: Lazy Processing (during `resolve()`)**

    - **Local raw refs (`%key`)** are expanded after all composition is complete
    - **Resolved References (`@`)** are processed on-demand
    - **Expressions (`$`)** are evaluated when needed
    - **Components (`_target_`)** are instantiated only when requested
    - CLI overrides can affect local `%` refs

**Why two phases?**

This design ensures CLI overrides work intuitively with local raw references:

```yaml
# base.yaml
vars:
  features_path: null  # Default, will be overridden

# model.yaml
dataset:
  path: "%vars::features_path"  # Local ref - sees CLI override
```

```python
config = Config()
config.update("base.yaml")
config.update("model.yaml")
config.update("vars::features_path=/data/features.npz")  # CLI override

# Local % ref sees the override!
path = config.resolve("dataset::path")  # "/data/features.npz"
```

!!! tip "External vs Local Raw References"

    | Type | Example | When Expanded | Use Case |
    |------|---------|---------------|----------|
    | **External** | `%file.yaml::key` | Eager (update) | Import from frozen files |
    | **Local** | `%vars::key` | Lazy (resolve) | Reference config values |

    External files are "frozen"—their content is fixed at load time.
    Local config values may be overridden via CLI, so local refs see the final state.

## Resolution Flow

!!! abstract "How References Are Resolved"

    **Step 1: Load Configs** → During `update()`

    - Parse YAML files
    - Expand external `%file.yaml::key` refs immediately
    - Keep local `%key` refs as strings

    **Step 2: Apply Overrides** → During `update()` calls

    - CLI overrides modify local config values
    - Local `%` refs still see the string form

    **Step 3: Resolve** → During `resolve()`

    - Expand local `%key` refs (now sees final values)
    - Resolve `@` dependencies in order
    - Check for circular references → ❌ **Error if found**
    - Evaluate expressions and instantiate objects
    - Return final computed value ✅

## Resolved References (`@`)

Use `@` followed by the key path with `::` separator to reference **resolved values** (after instantiation, expression evaluation, etc.):

```yaml title="config.yaml" hl_lines="7 10"
dataset:
  path: "/data/images"
  num_classes: 10
  batch_size: 32

model:
  num_outputs: "@dataset::num_classes"  # (1)!

training:
  batch: "@dataset::batch_size"  # (2)!
```

1. References the resolved value of `dataset.num_classes` (10)
2. Uses `::` separator for nested key access

```python title="main.py"
config = Config()
config.update("config.yaml")

# References are resolved when you call resolve()
num_outputs = config.resolve("model::num_outputs")  # 10
batch = config.resolve("training::batch")  # 32
```

!!! tip "Single Source of Truth"
    References prevent copy-paste errors by maintaining a single source of truth for shared values across your configuration.

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

!!! danger "Avoid Circular References"
    Circular references will cause a resolution error and must be avoided:

    ```yaml
    # ❌ This will fail!
    a: "@b"
    b: "@a"
    ```

    Sparkwheel detects circular dependencies during resolution and raises a descriptive error to help you identify the cycle.

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

Local raw references are expanded lazily during `resolve()`, which means CLI overrides can affect them:

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

!!! tip "CLI Overrides Work with Local Raw Refs"

    ```python
    config = Config()
    config.update("config.yaml")
    config.update("defaults::timeout=60")  # CLI override

    # Local % ref sees the override!
    config.resolve("api_config::timeout")  # 60
    ```

### Key Distinction

!!! abstract "@ vs % - When to Use Each"

    | Reference Type | Symbol | What You Get | When To Use |
    |----------------|--------|--------------|-------------|
    | **Resolved Reference** | `@` | Final value after instantiation/evaluation | When you want the computed result or object instance |
    | **Raw Reference** | `%` | Unprocessed YAML content | When you want to copy/reuse configuration definitions |

**Example showing the difference:**

```yaml title="config.yaml" hl_lines="8 11"
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10

# Resolved reference - gets the actual instantiated torch.nn.Linear object
trained_model: "@model"  # (1)!

# Raw reference - gets the raw dict with _target_, in_features, out_features
model_config_copy: "%model"  # (2)!
```

1. ✅ Returns an actual `torch.nn.Linear` instance
2. ✅ Returns a dictionary: `{"_target_": "torch.nn.Linear", "in_features": 784, "out_features": 10}`

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
