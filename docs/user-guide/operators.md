# Merging & Deleting

Learn how to combine and modify configurations with fine-grained control using merge (`+`) and delete (`~`) operators.

## Basic Merging

By default, later configs completely replace earlier ones:

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
  hidden_size: 1024
```

```python
from sparkwheel import Config

config = Config.load(["base.yaml", "override.yaml"])

# Result: model only has hidden_size=1024
# activation and dropout are GONE!
```

This replacement behavior is often not what you want. That's where merge operators come in.

## Merge Operator (`+`)

Use `+key` to merge a dict into existing config, preserving other keys:

```yaml
# override.yaml
+model:  # Merge into model, don't replace
  hidden_size: 1024
```

```python
config = Config.load(["base.yaml", "override.yaml"])

# Result:
# model:
#   hidden_size: 1024  (updated)
#   activation: "relu"  (preserved!)
#   dropout: 0.1        (preserved!)
```

### Nested Merging

Merge operators work at any nesting level:

```yaml
# base.yaml
training:
  optimizer:
    type: "adam"
    lr: 0.001
    betas: [0.9, 0.999]
  scheduler:
    type: "cosine"
    warmup: 1000
```

```yaml
# override.yaml
training:
  +optimizer:  # Merge into optimizer
    lr: 0.01   # Update only lr
  # scheduler is untouched
```

### Implicit Propagation

When a nested key has `+`, parent keys automatically merge:

```yaml
# override.yaml
model:
  layers:
    +conv1:  # This causes model and layers to merge too!
      filters: 64
```

This is equivalent to:

```yaml
# override.yaml
+model:
  +layers:
    +conv1:
      filters: 64
```

## Delete Operator (`~`)

Use `~key: null` to remove a key from config (the value must be present for valid YAML, but is ignored):

```yaml
# base.yaml
model:
  hidden_size: 512
  dropout: 0.1
  batch_norm: true
```

```yaml
# override.yaml
+model:
  ~dropout: null     # Remove dropout
  ~batch_norm: null  # Remove batch_norm
```

```python
config = Config.load(["base.yaml", "override.yaml"])

# Result:
# model:
#   hidden_size: 512  (preserved)
#   # dropout and batch_norm are gone
```

**Note:** YAML syntax requires a value for delete operators. Both `~key: null` and `~key:` (empty value) are valid. **Only `null` or empty values are allowed** - any other value will raise an error.

### Two Ways to Delete Nested Keys

!!! tip "Nested Path vs Structural Syntax"
    Sparkwheel supports two equivalent syntaxes for deleting nested keys:

    **Nested path syntax** (flat, programmatic):
    ```yaml
    ~parent::child::subchild: null
    ```

    **Structural syntax** (nested, matches YAML structure):
    ```yaml
    parent:
      child:
        ~subchild: null
    ```

    Both delete `subchild` from within `parent.child`.

    **When to use each:**

    - **Nested path** - CLI overrides, programmatic operations, deeply nested deletions
    - **Structural** - Cleaner YAML configs, better readability, grouping multiple changes

    **Choose based on context and readability!**

#### Nested Path Examples

```yaml
# override.yaml
~model::optimizer::weight_decay: null  # Remove specific nested key
~training::old_params: null            # Remove entire section
~system::dataloaders::predict: null    # Remove predict dataloader
```

This syntax is ideal for:
- Command-line overrides
- Programmatic config manipulation
- Very deep nesting (e.g., `~a::b::c::d::e: null`)

#### Structural Examples

```yaml
# override.yaml
+model:
  optimizer:
    ~weight_decay: null  # Remove weight_decay from optimizer
    ~momentum: null      # Remove momentum too

training:
  ~old_params: null      # Remove old_params from training
```

This syntax is ideal for:
- Grouping multiple changes in one section
- YAML files that closely mirror the config structure
- Better readability when making many changes

!!! warning "Watch Where You Place the `~`!"
    The `~` operator **only affects the key it's directly on**. Placing it on a parent key deletes the entire parent!

    ```yaml
    # ✗ WRONG - Deletes entire 'parent' dict (nested content ignored!)
    ~parent:
      child:
        subchild: null

    # ✓ CORRECT - Deletes only 'subchild'
    parent:
      child:
        ~subchild: null

    # ✓ ALSO CORRECT - Deletes only 'subchild' using path notation
    ~parent::child::subchild: null
    ```

    **Remember:** `~key: <value>` means "delete `key`" - the value must be `null` or empty, and nested content is not allowed.

## List Merging

The `+` operator can also merge lists by appending the override list to the base list:

```yaml
# base.yaml
plugins:
  - logger
  - metrics

middleware:
  - cors
  - auth
```

```yaml
# override.yaml
+plugins:      # Append to existing list
  - cache
  - redis

+middleware:
  - rate_limit
```

```python
from sparkwheel import Config

config = Config.load(["base.yaml", "override.yaml"])

# Result:
# plugins: [logger, metrics, cache, redis]
# middleware: [cors, auth, rate_limit]
```

**Note:** Duplicates are kept. If base has `[a, b]` and override has `[b, c]`, the result is `[a, b, b, c]`.

### Type Validation

Both values must be lists for list merging. Mixing types will raise an error:

```yaml
# base.yaml
items:
  - a
  - b

# override.yaml - ✗ Error!
+items: c  # String, not a list - type mismatch
```

The `+` operator validates types to ensure merge operations make sense:
- **Both dicts** → Recursive merge
- **Both lists** → Append override to base
- **Type mismatch** → Error with helpful suggestion

## Operator Validation

Sparkwheel validates that operators are used correctly to catch common mistakes early:

### Merge Validation

The `+` operator requires the key to already exist and types to match:

```yaml
# base.yaml
model:
  hidden_size: 512

plugins:
  - logger
  - metrics
```

```yaml
# override.yaml - ✓ Valid (dict merge)
+model:
  hidden_size: 1024

# override.yaml - ✓ Valid (list append)
+plugins:
  - new_plugin

# override.yaml - ✗ Error!
+optimizer:  # Error: 'optimizer' doesn't exist in base
  lr: 0.001
```

**Error message for non-existent key:**
```
Cannot merge into non-existent key 'optimizer'

The '+' prefix merges values into existing keys.
To create a new key, use 'optimizer' without the '+' prefix.

Change '+optimizer:' to 'optimizer:'
```

**Error message for type mismatch:**
```
Cannot merge '+model': type mismatch

Base value is list, override value is dict.

The '+' prefix only works when both values are dicts (merge) or lists (append).
To replace with a different type, remove the '+' prefix.

Change '+model:' to 'model:'
```

### Delete Validation

The `~` operator requires the key to exist:

```yaml
# base.yaml
model:
  hidden_size: 512
  dropout: 0.1
```

```yaml
# override.yaml - ✓ Valid
+model:
  ~dropout: null

# override.yaml - ✗ Error!
+model:
  ~batch_norm: null  # Error: 'batch_norm' doesn't exist
```

**Error message:**
```
Cannot delete non-existent key 'batch_norm'

The '~' prefix deletes existing keys from configuration.

Either remove '~batch_norm' or check if the key name is correct.
```

### Why Validate?

These validations catch common mistakes:
- **Typos in key names** - `+optimzer` instead of `+optimizer`
- **Wrong config file ordering** - Override loaded before base
- **Missing base configurations** - Trying to merge into undefined keys
- **Outdated override configs** - Referencing removed keys from earlier versions

## Programmatic Updates

Apply operators programmatically using `set()` and `merge()`:

```python
from sparkwheel import Config

config = Config.load("config.yaml")

# Set individual values
config.set("model::hidden_size", 1024)

# Merge using nested path syntax (flat, programmatic)
config.update({
    "+optimizer": {"lr": 0.01},        # Merge dict
    "~training::old_param": None,      # Delete key using path
    "~model::dropout": None,           # Delete nested key
})

# Or use structural syntax (nested, readable)
config.update({
    "+optimizer": {"lr": 0.01},
    "training": {
        "~old_param": None             # Delete using structure
    },
    "+model": {
        "~dropout": None               # Delete nested in structure
    }
})

# Both approaches work - choose based on readability
```

## Using `merge()` Method

Merge additional configs after loading:

```python
# Load base config
config = Config.load("base.yaml")

# Merge additional configs
config.update("experiments/exp1.yaml")
config.update("environments/prod.yaml")

# Or merge a dict
config.update({
    "+model": {"dropout": 0.2},
    "~training::debug_mode": None
})
```

### Merging Config Instances

You can merge one `Config` instance into another:

```python
from sparkwheel import Config

# Load different configs
base_config = Config.load("base.yaml")
cli_config = Config.from_cli("override.yaml", ["model::lr=0.001"])

# Merge the second config into the first
base_config.update(cli_config)
```

**Use Cases:**

1. **Combine configs from different sources:**
   ```python
   # Base configuration
   base = Config.load("base.yaml")

   # CLI overrides
   cli = Config.from_cli({}, ["trainer::max_epochs=100", "model::lr=0.001"])

   # Merge CLI overrides into base
   base.merge(cli)
   ```

2. **Load with different validation:**
   ```python
   from dataclasses import dataclass

   @dataclass
   class ModelSchema:
       lr: float
       hidden_size: int

   @dataclass
   class TrainerSchema:
       max_epochs: int
       devices: list

   # Load and validate different parts separately
   model_config = Config.load("model.yaml", schema=ModelSchema)
   trainer_config = Config.load("trainer.yaml", schema=TrainerSchema)

   # Combine into one config
   full_config = Config.load({})
   full_config.update(model_config)
   full_config.update(trainer_config)
   ```

3. **Programmatic config construction:**
   ```python
   # Build config programmatically
   defaults = Config.load({"model": {"lr": 0.01, "hidden_size": 256}})
   overrides = Config.load({"model": {"lr": 0.001}, "trainer": {"max_epochs": 50}})

   # Merge overrides into defaults
   defaults.merge(overrides)
   ```

**Behavior:**
- Follows same rules as merging files/dicts
- Replaces by default (no implicit `+`)
- Use `+` operators in the source config for merging
- Metadata is preserved and merged

**Example with merge operators:**

```python
# Config with replacement (default)
config1 = Config.load({"model": {"lr": 0.01, "dropout": 0.1}})
config2 = Config.load({"model": {"lr": 0.001}})  # Only lr

config1.update(config2)
# Result: model = {"lr": 0.001}  (dropout is lost!)

# Config with merge operator
config1 = Config.load({"model": {"lr": 0.01, "dropout": 0.1}})
config2 = Config.load({"+model": {"lr": 0.001}})  # Use + operator

config1.update(config2)
# Result: model = {"lr": 0.001, "dropout": 0.1}  (dropout preserved!)
```

## Merge Strategies Comparison

### Replace (Default)

```yaml
# override.yaml
model:
  hidden_size: 1024
```

**Result:** Entire `model` dict is replaced. Other keys are lost.

### Merge (`+`)

```yaml
# override.yaml
+model:
  hidden_size: 1024
```

**Result:** `hidden_size` is updated, other keys in `model` are preserved.

### Delete (`~`)

```yaml
# override.yaml
+model:
  ~dropout: null
```

**Result:** `dropout` is removed from existing `model` dict, other keys are preserved.

## Advanced Patterns

### Conditional Deletion

```yaml
# base.yaml
model:
  dropout: 0.1
  use_dropout: true

# override.yaml
+model:
  use_dropout: false
  ~dropout: null  # Remove dropout when not needed
```

### Selective Override

Override some parameters while preserving others:

```yaml
# base.yaml
optimizer:
  type: "adam"
  lr: 0.001
  betas: [0.9, 0.999]
  weight_decay: 0.0001
  eps: 1e-8

# experiments/high_lr.yaml
+optimizer:
  lr: 0.01  # Only change learning rate
  # All other params preserved
```

### Environment-Specific Configs

```yaml
# base.yaml
database:
  host: "localhost"
  port: 5432
  pool_size: 10
  ssl: false
  timeout: 30

# environments/production.yaml
+database:
  host: "prod-db.example.com"
  ssl: true
  # Other settings inherited from base
```

### Feature Flags

```yaml
# base.yaml
features:
  caching: true
  analytics: true
  experimental_ui: false
  debug_mode: true

# production.yaml
+features:
  experimental_ui: false
  ~debug_mode: null  # Remove debug in production
```

## Using apply_operators()

For advanced use cases, use `apply_operators()` directly:

```python
from sparkwheel import apply_operators

base = {
    "model": {"hidden_size": 512, "dropout": 0.1},
    "training": {"epochs": 100}
}

override = {
    "+model": {"hidden_size": 1024},  # Merge into model
    "~training::epochs": None          # Delete epochs
}

result = apply_operators(base, override)

# result:
# {
#   "model": {"hidden_size": 1024, "dropout": 0.1},
#   "training": {}
# }
```

## Best Practices

### 1. Use `+` for Partial Updates

When you want to change only specific parameters:

```yaml
# Good - preserves other optimizer settings
+optimizer:
  lr: 0.01

# Avoid - loses all other settings
optimizer:
  lr: 0.01
```

### 2. Delete Unused Keys

Keep configs clean by removing unused parameters:

```yaml
# experiments/no_regularization.yaml
+model:
  ~dropout: null
  ~weight_decay: null
  ~batch_norm: null
```

### 3. Layer Your Configs

Build configs in layers from general to specific:

```python
# Layer 1: Defaults
config = Config.load("defaults.yaml")

# Layer 2: Model architecture
config.update("models/resnet50.yaml")

# Layer 3: Dataset specific
config.update("datasets/imagenet.yaml")

# Layer 4: Experiment specific
config.update("experiments/exp_042.yaml")

# Layer 5: Environment
config.update("env/production.yaml")
```

### 4. Document Merge Behavior

Add comments to clarify merge intentions:

```yaml
# experiments/ablation_study.yaml

# Merge into base model - preserve other hyperparameters
+model:
  hidden_size: 1024

# Remove regularization for this experiment
+training:
  ~dropout: null
  ~weight_decay: null
```

## Common Pitfalls

### Forgetting `+` Prefix

```yaml
# Wrong - replaces entire dict
model:
  hidden_size: 1024

# Correct - merges into existing
+model:
  hidden_size: 1024
```

### Typos in Key Names

```yaml
# This will now error if 'optimzer' doesn't exist
+optimzer:  # Typo! Should be 'optimizer'
  lr: 0.001

# The error message will help you catch the typo
```

With validation, typos in merge and delete operators are caught immediately, helping you find and fix mistakes faster.

### Misplacing the `~` Operator

```yaml
# Wrong - deletes entire 'model' dict!
~model:
  dropout: 0.1
  batch_norm: true

# Correct - deletes only nested keys
+model:
  ~dropout: null
  ~batch_norm: null

# Or use path notation
~model::dropout: null
~model::batch_norm: null
```

The `~` operator only affects the key it's on. Nested values under a `~key:` are not allowed and will raise a validation error.

### Merge Order Matters

```python
# These produce different results:

# Order 1: base -> exp -> env
config = Config.load(["base.yaml", "exp.yaml", "env.yaml"])

# Order 2: base -> env -> exp (experiment overrides environment)
config = Config.load(["base.yaml", "env.yaml", "exp.yaml"])
```

## Next Steps

- [Advanced Features](advanced.md) - Macros, special keys, and power user techniques
- [Examples](../examples/simple.md) - Real-world merging patterns
