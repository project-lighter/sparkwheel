# Advanced Features

## Source inspection and resolution generations

`get()` and subscript access return source values without importing modules,
constructing targets, or evaluating expressions. Resolution compiles a separate
working tree: the source keeps its local `%` copies, relative references and
`_imports_` declarations. External `%file.yaml` includes are still expanded into
snapshots when `update()` loads them.

```python
config = Config().update({"n": 2, "copy": "%n"})
assert config.resolve("copy") == 2
assert config.get("copy") == "%n"
config.set("n", 7)
assert config.resolve("copy") == 7
```

Successful edits clear cached runtime values. Objects already returned to your
code are not rewritten; subsequent resolution builds a new generation. Unfrozen
raw container views remain mutable: use `set()`/`update()` for changes that should
invalidate the runtime cache. Frozen configurations return detached
container snapshots. Source export preserves configuration data, not
Python module state or arbitrary prebuilt objects. Migration: code that previously
read expanded local `%` values through `get()` after resolution should call
`resolve(path)` instead. Constructor `imports=` values
are supplied by the caller; declare serializable import paths in `_imports_`
when a standalone YAML export needs them.

## Resolution modes and object sharing

`resolve()` caches results separately for each pair of `instantiate` and
`eval_expr` options. Switching options cannot return a representation left by an
earlier call. Within the same mode, repeated resolution and `@` references retain
shared object identity, including after switching away and back.

```python
from sparkwheel import Config

config = Config().update({"object": {"_target_": "builtins.dict", "value": 8}})
definition = config.resolve("object", instantiate=False)  # Component wrapper
instance = config.resolve("object")  # {"value": 8}
assert config.resolve("object") is instance
assert config.resolve("object", instantiate=False) is definition
```

`instantiate=False` returns `Component` wrappers; `eval_expr=False` returns
`Expression` wrappers. References inside these wrappers are still resolved in the
selected mode. Different modes may construct separate objects and evaluate
expressions separately. Successful config edits or `resolve(lazy=False)` start a
fresh generation for all resolution modes. Published lambdas and generators keep
their original generation, including its reference cache and import namespace. `Resolver.get_item()` now consistently keeps the registered
Item definition, including after `get_item(resolve=True)`; callers needing a
resolved value should use `resolve()`.

These options are not a pure static-inspection API: configuration
imports can still run, and either enabled option can execute Python code.

## Retained recipes and construction scopes

Framework integrations can capture a configuration definition and create isolated
runtime graphs without adding YAML syntax:

```python
config = Config().update(
    {
        "network": {"_target_": "myproject.Network"},
        "optimizer": {"_target_": "myproject.Optimizer", "network": "@network"},
    }
)
recipe = config.retain()
network_scope = recipe.scope(blocked_paths={"optimizer"})
network = network_scope.resolve("network")
optimizer_scope = recipe.scope(bindings={"network": network})
optimizer = optimizer_scope.resolve("optimizer")
```

`recipe.definition(path="")` returns a detached source-container snapshot of one
retained node. It follows the local `%` copy chain needed to select that node,
without expanding its children or executing imports, `@` references, expressions,
or constructors. Missing paths raise `ConfigKeyError`; opaque leaves retain identity.

`retain()` captures source containers, locations, and caller-provided import
bindings, without copying runtime caches. Opaque Python leaves retain their
identity. Creating a recipe or scope executes no configured imports or targets;
resolution creates a fresh namespace and cache for that scope. Local `%` copies
remain independent recipes; `@` aliases share resolved objects within one scope.
New scopes share only explicitly supplied bindings or caller-owned opaque inputs.

Bindings are authoritative **exact source paths**, checked before their recipes
or dependencies are traversed. A bound parent suppresses its subtree when
resolving that parent or an ancestor. Explicitly resolving an unbound descendant
still builds that descendant's source recipe; it does not read an attribute from
the bound object. For example, binding `model` and `model::network` still permits
resolving `model::optimizer` from its definition.

Blocked paths prohibit their nodes and descendants. Explicit reachable references
are checked before imports or construction; bound subtrees are pruned from that
check. Binding a parent and blocking one of its descendants is valid. Binding at
or beneath a blocked path fails. This is graph checking, not static analysis of
arbitrary Python code inside expressions or constructors.

A static true `_disabled_` guard (including an exact literal guard binding) prunes
its payload before preflight. The guard itself remains subject to bindings and
blocks. Dynamic guards keep conservative preflight: a blocked argument is rejected
before the guard executes, even if that guard would later disable the node.
This preserves the scope's check-before-effects guarantee. Ordinary `Config`
resolution has no declared block set and evaluates a dynamic guard first.

`scope.bind(path, value)` adds a binding for a valid source path. The same identity
may be bound repeatedly. A different identity cannot replace a value already
resolved or consumed by a cached ancestor: create a fresh scope instead. This
prevents cached parents from silently retaining old children.

`scope.materialized_components()` returns a defensive mapping of `_target_` paths
to objects constructed in the scope. It excludes merely supplied bindings,
disabled components, expressions and iterator outputs (including iterators returned by a target). The mapped objects
remain live objects; modifying the returned dictionary does not change scope
bookkeeping.

Use `Config.update()` to snapshot external `%file.yaml` includes before retaining.
Direct `Config(data=...)` inputs containing unexpanded external includes are not
loaded later by a scope. Retention is not a serializer or a guarantee of deep
immutability for opaque inputs. Ordinary `Config.resolve()` retains its existing
cache and ownership behavior.

## Atomic edits and container paths

`set()` and `update()` stage a candidate source tree, apply the complete edit,
and validate it against the configured raw schema before publishing. If an edit,
external include, or validation fails, the prior source, source locations,
expression namespace and cached runtime identities remain intact. Multi-field
updates are validated together; `set()` is a single-field transaction.

Path edits respect existing dictionaries and lists. `set("layers::1::width", 64)`
updates the second list item without replacing the list. Traversing a scalar or
using an out-of-range list index raises instead of erasing unrelated content.
Missing dictionary paths are created as dictionaries; extend lists with normal
list composition instead of assigning a sparse index.

`update("~layers::0")` removes one list element. Removing several items with
`update({"~group::layers": [0, 2]})` has the same meaning as the structural form
`update({"group": {"~layers": [0, 2]}})`. Both remove those indices from the list
as it existed before that batch of removals.

The transaction protects Config state, not external side effects performed by
custom validators or file reads. Raw validation still permits unresolved
references/expressions; resolved values receive their separate schema check when
requested. Opaque Python inputs retain identity during edits.

Schema-enabled configurations validate resolved argument values before calling
a target constructor. Defaults are validation aids and do not silently become
authored arguments; see [Schema Validation](schema-validation.md) for coercion,
union and partial-resolution rules.

## Frozen Configs

Prevent source modifications after initialization:

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

`freeze()` detaches source containers from views handed out earlier. While frozen,
`get()` and subscript access return defensive ordinary dictionaries/lists, so
editing such a view cannot change the stored source or invalidate a cached run.
These snapshots remain easy to export as YAML. Opaque Python leaves, such as a
prebuilt network or module, and resolved runtime objects are not deeply frozen.
Use `unfreeze()` followed by `set()`/`update()` to change the source again.

Migration: nested mutation of a frozen raw view now affects only that snapshot.
Path writes into an existing list now address list elements, and nested batch
removals preserve their declared item-removal meaning.

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
config.update(
    {
        "api_key": MISSING,  # Will be set later
        "endpoint": "https://api.example.com",
        "timeout": 60,
    }
)

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
base_config = {"database::host": MISSING, "database::port": MISSING, "database::name": "myapp", "api_key": MISSING}

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
- `_disabled_`: Skip instantiation if `true` (removed from parent). See [Instantiation](instantiation.md#_disabled_-skip-instantiation) for details.
- `_mode_`: Operating mode for instantiation (see below)
- `_imports_`: Declare imports available to all expressions (see [Imports](#imports-for-expressions) below)

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

### Programmatic Updates

Apply operators programmatically:

```python
config = Config()
config.update("config.yaml")

# Set individual values
config.set("model::hidden_size", 1024)

# Use operators
config.update(
    {
        "optimizer": {"lr": 0.01},  # Compose (merge by default)
        "=database": {"host": "prod.db"},  # Replace
        "~training::old_param": None,  # Delete
    }
)
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
config.update({"model": {"hidden_size": 512, "num_layers": 4}, "training": {"batch_size": 32}})

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

## Imports for Expressions

Make modules available to all expressions. There are two ways to do this:

### Method 1: `_imports_` Key in YAML

Declare imports directly in your config file:

```yaml
# config.yaml
_imports_:
  torch: torch
  np: numpy
  Path: pathlib.Path

# Now use them in expressions
device: "$torch.device('cuda' if torch.cuda.is_available() else 'cpu')"
data: "$np.array([1, 2, 3])"
save_path: "$Path('/data/models')"
```

The `_imports_` key is retained in the source returned by `get()`, including after
resolution. It is omitted only from the resolved runtime dictionary. This lets
`Config.export_config_file(config.get(), path)` preserve imports for replay in a
fresh process. After an edit, resolution starts a fresh expression namespace;
removed YAML imports and `$import ...` aliases no longer remain available. Imports
provided through the Python constructor remain available across generations.

Migration: code that expected resolution to delete `_imports_` from `get()` should
use `resolve()` when it needs the runtime dictionary without that declaration.

### Method 2: `imports` Parameter in Python

Pass imports when creating the Config:

```python
from sparkwheel import Config

# Pre-import modules for all expressions
config = Config(imports={"torch": "torch", "np": "numpy"})
config.update("config.yaml")

# Now expressions can use torch and np without importing
```

### Combining Both Methods

You can use both approaches together—they merge:

```python
from collections import Counter

config = Config(imports={"Counter": Counter})
config.update({"_imports_": {"json": "json"}, "data": '$json.dumps({"a": 1})', "counts": "$Counter([1, 1, 2])"})
```

## Type Hints

```python
from sparkwheel import Config

config: Config = Config()
config.update("config.yaml")
resolved: dict = config.resolve()
```

For complete details, see the [API Reference](../reference/index.md).
