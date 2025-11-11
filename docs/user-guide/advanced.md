# Advanced Features

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

## Fine-Grained Merging with +/~ Directives

Control exactly how configs merge with special prefixes:

### Merge Directive (`+`)

Use `+key` to merge a dict or append a list into existing config, preserving other keys:

```yaml
# base.yaml
model:
  hidden_size: 512
  activation: "relu"
  dropout: 0.1
```

```yaml
# override.yaml
+model:  # Merge into model, don't replace
  hidden_size: 1024  # Update this
  # activation and dropout are preserved!
```

```python
from sparkwheel import Config

config = Config.load("base.yaml")
config.merge("override.yaml")

# Result:
# model:
#   hidden_size: 1024  (updated)
#   activation: "relu"  (preserved)
#   dropout: 0.1        (preserved)
```

**Note:** The `+` directive validates that the key exists and types match (both dicts or both lists), catching configuration errors early. See [Merging Guide](merging.md) for detailed validation behavior and list merging examples.

### Delete Directive (`~`)

Use `~key: null` to delete a key (the value must be present for valid YAML, but is ignored):

```yaml
# override.yaml
~model::dropout: null  # Remove dropout from model
```

```python
config = Config.load("base.yaml")
config.merge({"~model::dropout": None})

# dropout is now removed from model config
```

**Note:** The `~` directive now validates that the key exists, catching typos and config ordering issues early.

### Programmatic Updates

Apply directives programmatically:

```python
config = Config.load("config.yaml")

# Set individual values
config.set("model::hidden_size", 1024)

# Merge with directives
config.merge({
    "+optimizer": {"lr": 0.01},        # Merge
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

config = Config.load({
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
config = Config.load("config.yaml", globals={"torch": "torch", "np": "numpy"})

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

config: Config = Config.load("config.yaml")
resolved: dict = config.resolve()
```

For complete details, see the [API Reference](../reference/).
