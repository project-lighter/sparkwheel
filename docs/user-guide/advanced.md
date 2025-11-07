# Advanced Features

## Macros (`%`)

Load values from external files:

```yaml
# base.yaml
defaults:
  learning_rate: 0.001

# experiment.yaml
training:
  lr: "%base.yaml::defaults::learning_rate"
```

## Special Keys

Sparkwheel recognizes these special keys in configuration:

- `_target_`: Class or function path to instantiate (e.g., `"torch.nn.Linear"`)
- `_args_`: List of positional arguments to pass to the target
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

## Configuration Merging

```python
parser = ConfigParser()
parser.read_config("base.yaml")
parser.read_config("override.yaml")  # Merges with base
```

## Type Hints

```python
from sparkwheel import ConfigParser

parser: ConfigParser = ConfigParser()
config: dict = parser.get()
```

For complete details, see the [API Reference](../reference/).
