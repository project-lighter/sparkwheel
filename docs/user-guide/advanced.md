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
from sparkwheel import ConfigParser

parser = ConfigParser.load("base.yaml")
parser.merge("override.yaml")

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
parser = ConfigParser.load("base.yaml")
parser.update({"~model::dropout": None})

# dropout is now removed from model config
```

**Note:** The `~` directive now validates that the key exists, catching typos and config ordering issues early.

### Using update()

Batch updates with directives:

```python
parser = ConfigParser.load("config.yaml")

# Apply multiple updates at once
parser.update({
    "model::hidden_size": 1024,        # Replace
    "+optimizer": {"lr": 0.01},        # Merge
    "~training::old_param": None,      # Delete
})
```

## CLI Overrides

Parse command-line arguments with automatic type inference:

```python
from sparkwheel import ConfigParser, parse_args
import sys

# Load base config
parser = ConfigParser.load("config.yaml")

# Parse CLI args: python main.py model::lr=0.01 training::batch_size=64
cli_overrides = parse_args(sys.argv[1:])

# Apply overrides
parser.update(cli_overrides)
```

Supported types (auto-detected):

```bash
# Numbers
python main.py model::lr=0.001 epochs=100

# Booleans
python main.py debug=true use_gpu=false

# Strings
python main.py name="My Experiment"

# Lists
python main.py layers=[64,128,256]

# Dicts
python main.py optimizer={lr:0.01,momentum:0.9}

# Merge directive
python main.py +model::layers=[512]

# Delete directive
python main.py ~model::dropout
```

## Config Validation

Check your config for errors:

```python
from sparkwheel import check_config, format_check_result

# Check config file
result = check_config("config.yaml")

if result.is_valid:
    print("✓ Config is valid!")
    print(f"  - {result.num_references} references")
    print(f"  - {result.num_expressions} expressions")
    print(f"  - {result.num_components} components")
else:
    print(format_check_result(result, verbose=True))
```

Checks performed:
- YAML syntax validation
- Reference resolution (`@references`)
- Circular dependency detection
- Expression evaluation (`$expressions`)
- Component instantiation (`_target_`)

## Config Diffing

Compare configurations to see what changed:

```python
from sparkwheel import diff_configs, format_diff_tree

# Compare two configs
diff = diff_configs("config_v1.yaml", "config_v2.yaml")

print(f"Changes: {diff.summary()}")
print(format_diff_tree(diff))

# Semantic diff - compare resolved values
diff = diff_configs("config_v1.yaml", "config_v2.yaml", resolve=True)

if not diff.has_changes():
    print("Configs are semantically equivalent!")
```

Output formats:
- **Tree** (human-readable): `format_diff_tree(diff)`
- **Unified** (git-style): `format_diff_unified(diff)`
- **JSON** (machine-readable): `format_diff_json(diff)`

### Semantic Diff

Compare configs after resolving references and expressions:

```yaml
# config1.yaml
base_lr: 0.001
model:
  lr: "@base_lr"

# config2.yaml
model:
  lr: 0.001
```

```python
# Syntactic diff - shows differences
diff = diff_configs("config1.yaml", "config2.yaml", resolve=False)
assert diff.has_changes()  # Different syntax

# Semantic diff - resolves first
diff = diff_configs("config1.yaml", "config2.yaml", resolve=True)
assert not diff.has_changes()  # Same resolved values!
```

## Enhanced Error Messages

Sparkwheel provides helpful error messages with suggestions:

```python
from sparkwheel import ConfigParser

parser = ConfigParser.load({
    "model": {"hidden_size": 512, "num_layers": 4},
    "training": {"batch_size": 32}
})

try:
    # Typo in key name
    value = parser.resolve("model::hiden_size")
except ConfigKeyError as e:
    print(e)
    # Output:
    # Config ID 'model::hiden_size' not found
    #
    # Did you mean one of these?
    #   - model::hidden_size (90% match)
    #   - model::num_layers (40% match)
```

Color output is auto-detected and respects `NO_COLOR` environment variable.

## Type Hints

```python
from sparkwheel import ConfigParser

parser: ConfigParser = ConfigParser.load("config.yaml")
config: dict = parser.resolve()
```

For complete details, see the [API Reference](../reference/).
