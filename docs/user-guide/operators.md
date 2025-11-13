# Composition & Operators

Sparkwheel uses **composition-by-default**: configs merge naturally with just 2 operators (`=`, `~`) for explicit control.

## Composition by Default

By default, configs compose naturally - dicts merge, lists extend:

**Dicts merge automatically:**

```yaml
# base.yaml
model:
  hidden_size: 512
  activation: "relu"
  dropout: 0.1
```

```yaml
# override.yaml
model:
  hidden_size: 1024  # Update this field
  # Other fields preserved!
```

```python
config = Config.load(["base.yaml", "override.yaml"])
# Result:
# model:
#   hidden_size: 1024   (updated)
#   activation: "relu"  (preserved)
#   dropout: 0.1        (preserved)
```

**Lists extend automatically:**

```yaml
# base.yaml
plugins:
  - logger
  - metrics

# override.yaml
plugins:
  - cache  # Adds to the list!

# Result: [logger, metrics, cache]
```

!!! success "Natural Composition"
    **No operators needed for the common case!** Sparkwheel merges dicts and extends lists by default, matching how you naturally think about config layering.

## The `=` Operator: Explicit Replace

When you need to completely replace something, use `=key`:

```yaml
# override.yaml
=model:  # Replace the entire model dict
  hidden_size: 1024
  # Old fields (activation, dropout) are GONE!
```

```python
config = Config.load(["base.yaml", "override.yaml"])
# Result:
# model:
#   hidden_size: 1024  (only this remains)
```

### When to Use `=`

Use `=` when you want to:
- Replace an entire section with a fresh start
- Change the type of a value (e.g., dict → list)
- Clear out all previous settings

```yaml
# Replace list entirely (no extension)
=plugins: [redis, cache]

# Replace nested section
training:
  =optimizer:  # Replace optimizer, but merge training
    type: "sgd"
    lr: 0.1
```

!!! tip "Quoting in YAML Files"
    When using `=` in YAML files, you can quote the key (`'=model'`) for clarity, but it's not required. In Python code, no quoting is needed.

## The `~` Operator: Delete

Remove keys or list items with `~key`:

### Delete Entire Keys

```yaml
# Remove keys (idempotent - no error if missing!)
~old_param: null
~debug_settings: null
```

### Delete Dict Keys

Use path notation for nested keys:

```yaml
# Path notation
~model::dropout: null
~training::old_params: null
```

Or structural notation:

```yaml
# Structural notation (works without parent operator!)
model:
  lr: 0.01           # Update
  ~dropout: null     # Delete
  ~batch_norm: null  # Delete
```

!!! success "No Parent Context Required!"
    With composition-by-default, nested `~` just works - no special parent operator needed!

### Delete from Lists

Remove items by index (batch syntax):

```yaml
# base.yaml
plugins:
  - logger    # 0
  - metrics   # 1
  - cache     # 2
  - auth      # 3
  - debug     # 4

# override.yaml - Remove by indices
~plugins: [0, 2, 4]  # Remove indices 0, 2, 4

# Result: [metrics, auth]
```

**Negative indices work too:**

```yaml
~plugins: [-1]      # Remove last item
~plugins: [0, -1]   # Remove first and last
```

### Delete from Dicts

Remove nested dict keys by name:

```yaml
# base.yaml
dataloaders:
  train: {batch_size: 32}
  val: {batch_size: 16}
  test: {batch_size: 8}

# override.yaml
~dataloaders: ["train", "test"]

# Result:
# dataloaders:
#   val: {batch_size: 16}
```

!!! warning "Removing List Items"
    To remove items from a list, **you must use the batch syntax** `~key: [indices]`:

    ```yaml
    # ✓ CORRECT - Batch deletion syntax
    ~plugins: [0, 2, 4]
    ```

    ```yaml
    # ✗ WRONG - Path notation doesn't work for list items!
    ~plugins::0: null
    ```

    **Why?** Path notation is designed for dict keys, not list indices. The batch syntax handles index normalization and processes deletions correctly (high to low order).

### Idempotent Delete

Delete operations don't error if the key doesn't exist:

```yaml
# production.yaml - Remove debug settings if they exist
~debug_mode: null
~dev_logger: null
~test_data: null
# No errors if these don't exist!
```

This enables **reusable configs** that work with multiple bases:

```yaml
# production.yaml works with ANY base config
~debug_settings: null
~verbose_logging: null
database:
  pool_size: 100
```

## Combining Operators

Mix composition, replace, and delete:

```yaml
# base.yaml
application:
  name: "MyApp"
  version: 1.0
  features:
    auth: enabled
    cache: enabled
    debug: enabled
  plugins: [logger, metrics]
  database:
    host: localhost
    port: 5432
    pool_size: 10

# production.yaml
application:
  version: 1.1              # Compose: update (default)
  features:                 # Compose: merge (default)
    cache: redis            # Update
    ~debug: null            # Delete
  plugins: [monitor]        # Compose: extend (default!)
  =database:                # Replace: fresh db config
    host: prod.example.com
    port: 5432
    ssl: true

# Result:
# application:
#   name: "MyApp"           (preserved)
#   version: 1.1            (updated)
#   features:
#     auth: enabled         (preserved)
#     cache: redis          (updated)
#     # debug removed
#   plugins: [logger, metrics, monitor]  (extended!)
#   database:               (replaced entirely)
#     host: prod.example.com
#     port: 5432
#     ssl: true
```

## Programmatic Usage

Apply operators in Python:

```python
from sparkwheel import Config

config = Config.load("base.yaml")

# Compose (merge dict) - default behavior
config.update({"model": {"hidden_size": 1024}})

# Replace explicitly
config.update({"=optimizer": {"type": "sgd", "lr": 0.1}})

# Delete keys (idempotent)
config.update({
    "~training::old_param": None,
    "~model::dropout": None
})

# Combine operations
config.update({
    "model": {                      # Merge
        "hidden_size": 1024,        # Update
        "~dropout": None            # Delete
    },
    "=database": {                  # Replace
        "host": "prod.example.com"
    }
})

# Remove list items by index
config.update({"~plugins": [0, 2, 4]})

# Remove dict keys
config.update({"~dataloaders": ["train", "test"]})
```

### Merging Config Instances

Configs compose when merged:

```python
base = Config.load("base.yaml")
override = Config.load("override.yaml")

# Merge one Config into another (composes by default!)
base.update(override)
```

## Common Patterns

### Environment-Specific Configs

```yaml
# base.yaml
database:
  host: "localhost"
  port: 5432
  pool_size: 10
  ssl: false

# production.yaml (merges automatically!)
database:
  host: "prod-db.example.com"
  ssl: true
  pool_size: 50
  # Other settings inherited from base
```

### Experiment Variations

```yaml
# base_model.yaml
model:
  hidden_size: 512
  num_layers: 6
  dropout: 0.1

# experiment_large.yaml (merges automatically!)
model:
  hidden_size: 1024
  num_layers: 12

# experiment_no_dropout.yaml (merges automatically, deletes dropout)
model:
  ~dropout: null
```

### Feature Flags

```yaml
# base.yaml
plugins:
  - logger
  - metrics
  - profiler
  - debugger
  - test_reporter

# production.yaml - Remove debug/test plugins
~plugins: [2, 3, 4]  # Remove profiler, debugger, test_reporter

# Result: [logger, metrics]
```

### Layered Configuration

```python
# Build configs in layers (all compose naturally!)
config = Config.load("defaults.yaml")
config.update("models/resnet50.yaml")
config.update("datasets/imagenet.yaml")
config.update("experiments/exp_042.yaml")
config.update("env/production.yaml")
```

## Best Practices

### Leverage Composition

```yaml
# Good - natural composition (no operators!)
optimizer:
  lr: 0.01

# Unnecessary - = not needed for simple updates
=optimizer:
  lr: 0.01
```

### Use `=` Only When Needed

```yaml
# Use = when completely replacing
=optimizer:  # Start fresh, discard all old settings
  type: "sgd"
  lr: 0.1

# Default composition is usually what you want
optimizer:   # Keep other settings, update lr
  lr: 0.01
```

### Choose Path vs Structural Notation

**Use path notation** for single, independent operations:

```yaml
# Quick single updates/deletes
~model::dropout: null
~training::old_param: null
```

**Use structural notation** for bulk related operations:

```yaml
# Multiple related changes
model:
  hidden_size: 1024
  num_layers: 12
  ~dropout: null
  ~batch_norm: null
```

### Write Reusable Configs

Use idempotent delete for portable configs:

```yaml
# production.yaml - works with ANY base!
~debug_mode: null        # Remove if exists
~verbose_logging: null   # No error if missing
database:
  pool_size: 100
  ssl: true
```

## Common Mistakes

### Using `=` When Not Needed

```yaml
# Unnecessary - composition merges by default!
=model:
  hidden_size: 1024

# Better - let it compose naturally
model:
  hidden_size: 1024
```

### Expecting List Replacement by Default

```yaml
# This EXTENDS the list (doesn't replace)
plugins: [cache]

# Use = to replace
=plugins: [cache]
```

### Wrong List Deletion Syntax

```yaml
# Wrong - path notation doesn't work for list indices
~plugins::0: null

# Correct - use batch syntax
~plugins: [0]
```

### Forgetting Quotes for Operators

```yaml
# Wrong - YAML might misinterpret
=model:
  lr: 0.001

# Safer - quote operators (optional but clearer)
'=model':
  lr: 0.001
```

## Comparison with Other Systems

### vs Hydra

| Feature | Hydra | Sparkwheel |
|---------|-------|------------|
| Dict merge default | Yes ✅ | Yes ✅ |
| List extend default | No ❌ | **Yes** ✅ |
| Operators in YAML | No ❌ | Yes ✅ (`=`, `~`) |
| Operator count | 4 (`+`, `++`, `~`) | **2** (`=`, `~`) ✅ |
| Delete dict keys | No ❌ | Yes ✅ |
| Delete list items | No ❌ | Yes ✅ |
| Idempotent delete | N/A | Yes ✅ |

Sparkwheel goes beyond Hydra with:
- Full composition-first philosophy (dicts **and** lists)
- Operators directly in YAML files
- Just 2 simple operators
- Delete operations for fine-grained control

## Next Steps

- **[Configuration Basics](basics.md)** - Core config management
- **[Advanced Features](advanced.md)** - Macros and power features
- **[Examples](../examples/simple.md)** - Real-world patterns
