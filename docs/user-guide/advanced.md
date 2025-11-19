# Advanced Features

## Frozen Configs

Prevent modifications after initialization:

```python
from sparkwheel import Config

config = Config(schema=MySchema)
config.update("config.yaml")

# Freeze to make immutable
config.freeze()

# Mutations now raise FrozenConfigError
try:
    config.set("model::lr", 0.001)
except FrozenConfigError as e:
    print(f"Error: {e}")  # Cannot modify frozen config

# Read operations still work
value = config.get("model::lr")
resolved = config.resolve()

# Check if frozen
if config.is_frozen():
    print("Config is frozen!")

# Unfreeze if needed
config.unfreeze()
config.set("model::lr", 0.001)  # Now works
```

**Use cases:**
- Prevent accidental modifications in production
- Ensure config consistency across app lifecycle
- Debug configuration issues by freezing after initial setup

## MISSING Sentinel

Support partial configs with required-but-not-yet-set values:

```python
from sparkwheel import Config, MISSING
from dataclasses import dataclass

@dataclass
class APIConfigSchema:
    api_key: str
    endpoint: str
    timeout: int = 30

# Build config incrementally with MISSING values
config = Config(schema=APIConfigSchema, allow_missing=True)
config.update({
    "api_key": MISSING,  # Will be set later
    "endpoint": "https://api.example.com",
    "timeout": 60
})

# Fill in missing values from environment
import os
config.set("api_key", os.getenv("API_KEY"))

# Validate that nothing is MISSING anymore
config.validate(APIConfigSchema)  # Uses allow_missing=False by default

# Freeze for production use
config.freeze()
```

**MISSING vs None:**
- `None` is a valid value that satisfies `Optional[T]` fields
- `MISSING` indicates a required field that hasn't been set yet
- `MISSING` raises ValidationError unless `allow_missing=True`

**Common patterns:**

```python
# Template configs with placeholders
base_config = {
    "database::host": MISSING,
    "database::port": MISSING,
    "database::name": "myapp",
    "api_key": MISSING
}

# Environment-specific configs fill in MISSING values
config = Config(schema=MySchema, allow_missing=True)
config.update(base_config)
config.set("database::host", os.getenv("DB_HOST"))
config.set("database::port", int(os.getenv("DB_PORT")))
config.set("api_key", os.getenv("API_KEY"))
config.validate(MySchema)  # Ensure complete
```

## Macros (`%`)

Load **raw YAML values** from external files using `%`:

```yaml
# base.yaml
defaults:
  learning_rate: 0.001

# experiment.yaml
training:
  lr: "%base.yaml::defaults::learning_rate"
```

**Important:** `%` references get the raw YAML definition (not instantiated), while `@` references get the resolved/instantiated object from the current config.

## Special Keys

Sparkwheel recognizes these special keys in configuration:

- `_target_`: Class or function path to instantiate (e.g., `"torch.nn.Linear"`)
- `_disabled_`: Boolean or expression - skip instantiation if evaluates to `True`
- `_requires_`: List of dependencies to evaluate/instantiate first
- `_mode_`: Operating mode for instantiation (see below)

### `_mode_` - Instantiation Modes

The `_mode_` key controls how the target is instantiated:

- **`"default"`** (default): Returns `component(**kwargs)` - normal instantiation
- **`"callable"`**: Returns the component itself, or `functools.partial(component, **kwargs)` if kwargs provided
- **`"debug"`**: Returns `pdb.runcall(component, **kwargs)` - runs in debugger

```yaml
# Example: Get a callable instead of instance
model_class:
  _target_: torch.nn.Linear
  _mode_: "callable"
  in_features: 784
  out_features: 10
  # This returns functools.partial(torch.nn.Linear, in_features=784, out_features=10)
  # instead of an instantiated Linear object

# Example: Debug mode
buggy_component:
  _target_: mymodule.BuggyClass
  _mode_: "debug"  # Will run in pdb debugger
  param: value
```

## Composition & Operators

Sparkwheel uses **composition-by-default**: configs naturally merge (dicts) or extend (lists). Use operators for explicit control:

### Default Behavior: Composition

By default, configs compose naturally - no operators needed:

```yaml
# base.yaml
model:
  hidden_size: 512
  activation: "relu"
  dropout: 0.1
```

```yaml
# override.yaml
model:  # Merges by default!
  hidden_size: 1024  # Update this
  # activation and dropout are preserved!
```

```python
from sparkwheel import Config

config = Config()
config.update("base.yaml")
config.update("override.yaml")

# Result:
# model:
#   hidden_size: 1024  (updated)
#   activation: "relu"  (preserved - composition!)
#   dropout: 0.1        (preserved - composition!)
```

### Replace Operator (`=`)

Use `=key` when you need to completely replace instead of merge:

```yaml
# override.yaml
=model:  # Replace entire model dict
  hidden_size: 1024
  # activation and dropout are GONE!
```

See [Composition & Operators](operators.md) for full details on composition-by-default and the `=` operator.

### Delete Directive (`~`)

Use `~key: null` to delete a key, or `~key: [items]` to delete specific items from lists/dicts:

```yaml
# override.yaml
~model::dropout: null  # Remove entire key

# Remove specific list items by index
~plugins: [0, 2, 4]  # Remove items at indices 0, 2, 4

# Remove specific dict keys
~dataloaders: ["train", "test"]  # Remove these keys

# Negative indices work too
~plugins: [-1]  # Remove last item
```

```python
config = Config()
config.update("base.yaml")
config.update({"~model::dropout": None})  # Remove entire key
config.update({"~plugins": [0, 2]})  # Remove list items
config.update({"~dataloaders": ["train", "test"]})  # Remove dict keys
```

**Note:** The `~` directive is idempotent - it doesn't error if the key doesn't exist, enabling reusable configs.

### Programmatic Updates

Apply operators programmatically:

```python
config = Config()
config.update("config.yaml")

# Set individual values
config.set("model::hidden_size", 1024)

# Use operators
config.update({
    "optimizer": {"lr": 0.01},         # Compose (merge by default)
    "=database": {"host": "prod.db"},  # Replace
    "~training::old_param": None,      # Delete
})
```

## Relative ID References

Use relative references to navigate the config hierarchy:

```yaml
model:
  encoder:
    hidden_size: 512
    activation: "relu"
  decoder:
    # Reference sibling section
    hidden_size: "@::encoder::hidden_size"  # Same level (model)
    # Reference parent level
    loss_fn: "@::::training::loss"  # Go up to root, then to training
```

**Syntax:**
- `@::` - Same level (sibling)
- `@::::` - Parent level
- Add more `::` to go up more levels

## Enhanced Error Messages

Sparkwheel provides helpful error messages with suggestions:

```python
from sparkwheel import Config, ConfigKeyError

config = Config()
config.update({
    "model": {"hidden_size": 512, "num_layers": 4},
    "training": {"batch_size": 32}
})

try:
    # Typo in key name
    value = config.resolve("model::hiden_size")
except ConfigKeyError as e:
    print(e)
    # Output:
    # Config ID 'model::hiden_size' not found
    #
    # Did you mean one of these?
    #   - model::hidden_size
    #   - model::num_layers
```

Color output is auto-detected and respects `NO_COLOR` environment variable.

## Globals for Expressions

Pre-import modules for use in expressions:

```python
from sparkwheel import Config

# Pre-import torch for all expressions
config = Config(globals={"torch": "torch", "np": "numpy"})
config.update("config.yaml")

# Now expressions can use torch and np without importing
```

Example config:

```yaml
device: "$torch.device('cuda' if torch.cuda.is_available() else 'cpu')"
data: "$np.array([1, 2, 3])"
```

## Type Hints

```python
from sparkwheel import Config

config: Config = Config()
config.update("config.yaml")
resolved: dict = config.resolve()
```

For complete details, see the [API Reference](../reference/).
