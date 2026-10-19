# Quick Reference

A one-page cheat sheet for Sparkwheel syntax and features.

## Core Syntax

=== "References"

    | Syntax | Type | Returns | Example |
    |--------|------|---------|---------|
    | `@key` | Resolved reference | Final computed value | `lr: "@defaults::learning_rate"` |
    | `%key` | Raw reference | Unprocessed YAML | `config: "%base.yaml::model"` |
    | `@key::nested` | Nested access | Nested value | `@dataset::train::batch_size` |
    | `@list::0` | List indexing | List element | `@transforms::0` |

=== "Expressions"

    An expression is a `$` followed by Python; `@key` inside it is the value of `key`.

    ```yaml
    lr: 0.01
    name: resnet
    debug: false
    items: [1, 2, 3]
    scaled: "$@lr * 0.1"                    # math → 0.001
    run_name: "$@name + '_v2'"              # strings → resnet_v2
    mode: "$'dev' if @debug else 'prod'"    # Python's conditional → prod
    first: "$@items[0]"                     # indexing → 1
    count: "$len(@items)"                   # built-in functions → 3
    ```

=== "Operators"

    Keys set, `+` combines, `~` deletes. A `::` path sets one value deep inside.

    ```yaml title="base.yaml"
    debug: true
    layers: [64, 128, 256, 512]
    model: {size: 256, dropout: 0.1}
    optimizer: {lr: 0.1, momentum: 0.9}
    scheduler: {name: cosine, warmup: 5}
    callbacks: [checkpoint]
    ```

    ```yaml title="experiment.yaml"
    scheduler: {name: step}        # set → {name: step}
    model::size: 512               # set one value → {size: 512, dropout: 0.1}
    +optimizer: {lr: 0.01}         # merge → {lr: 0.01, momentum: 0.9}
    +callbacks: [early_stopping]   # append → [checkpoint, early_stopping]
    ~debug: null                   # delete the key
    ~layers: [1, 3]                # delete list items 1 and 3 → [64, 256]
    ```

=== "Instantiation"

    | Key | Type | Purpose | Example |
    |-----|------|---------|---------|
    | `_target_` | str | Class/function to instantiate | `torch.optim.Adam` |
    | `_args_` | list | Positional arguments | `[arg1, arg2]` |
    | `_disabled_` | bool | Skip instantiation | `true` |
    | `_mode_` | str | Instantiation mode | `"default"` / `"callable"` / `"debug"` |

## Common Patterns

### Single Source of Truth

```yaml
defaults:
  learning_rate: 0.001

optimizer:
  lr: "@defaults::learning_rate"

scheduler:
  base_lr: "@defaults::learning_rate"
```

### Computed Values

```yaml
dataset:
  samples: 10000
  batch_size: 32

training:  # → {steps_per_epoch: 312}
  steps_per_epoch: "$@dataset::samples // @dataset::batch_size"
```

### Conditional Configuration

```yaml
environment: "production"

database:
  prod_host: "prod.db.com"
  dev_host: "localhost"
  host: "$@database::prod_host if @environment == 'production' else @database::dev_host"
```

### Object Instantiation

```yaml
# Basic instantiation
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10

# With positional arguments
sequential:
  _target_: torch.nn.Sequential
  _args_:
    - _target_: torch.nn.Linear
      in_features: 784
      out_features: 128
    - _target_: torch.nn.ReLU

# With optimizer
optimizer:
  _target_: torch.optim.Adam
  params: "$@model.parameters()"
  lr: 0.001
```

### Layering Files

Each later file changes the ones before it (`python train.py base.yaml override.yaml replace.yaml`):

```yaml title="base.yaml"
model:
  hidden_size: 512
  dropout: 0.1
```

```yaml title="override.yaml"
+model:  # merged → {hidden_size: 1024, dropout: 0.1}
  hidden_size: 1024
```

```yaml title="replace.yaml"
model:  # set → {hidden_size: 256}
  hidden_size: 256
```

## CLI Overrides

Each command-line argument is a YAML file or a `key=value` override. The examples use this file:

```yaml title="config.yaml"
learning_rate: 0.001
batch_size: 32
model:
  hidden_size: 512
  dropout: 0.1
  channels: [16, 32]
```

!!! tip "Add with `+`"
    `key=value` sets a key that exists, so a typo is an error. `+key=value` merges into a dict, appends to a list, or adds a new key.

=== "Set values"

    ```bash
    python train.py config.yaml learning_rate=0.01 batch_size=64
    ```

=== "Nested keys"

    ```bash
    python train.py config.yaml model::hidden_size=1024 model::dropout=0.2
    ```

    Nested keys are separated by `::`. A dot (`model.hidden_size=1024`) is an error that suggests the `::` path.

=== "Lists"

    ```bash
    python train.py config.yaml model::channels=[64,128]  # → [64, 128]
    python train.py config.yaml +model::channels=[64]  # → [16, 32, 64]
    ```

=== "Set, merge, add, delete"

    ```bash
    python train.py config.yaml 'model={hidden_size: 1024}'  # → {hidden_size: 1024}
    python train.py config.yaml '+model={dropout: 0.2}'  # → {hidden_size: 512, dropout: 0.2, channels: [16, 32]}
    python train.py config.yaml +seed=42  # → 42
    python train.py config.yaml '~model::dropout'
    ```

`key=value` changes a key that exists, or adds an argument to a `_target_` component. Anything else is most likely a typo and raises an error with a did-you-mean; write `+key=value` to add a new key. Values follow YAML rules (`8` is an int, `[1,2]` a list, `{a: 1}` a dict — note the space after `:`); quote overrides that contain spaces or `$`, `@`, `~` for your shell.

## Schema Validation

```python
from dataclasses import dataclass
from sparkwheel import Config, validator


@dataclass
class AppConfigSchema:
    name: str
    port: int
    debug: bool = False

    @validator
    def check_port(self):
        if not (1024 <= self.port <= 65535):
            raise ValueError(f"Invalid port: {self.port}")


# Continuous validation: checked on every update()
config = Config(schema=AppConfigSchema)
config.update({"name": "app", "port": 8080})

# Or validate explicitly
config = Config().update({"name": "app", "port": 8080})
config.validate(AppConfigSchema)
```

## Resolution Order

References are resolved in dependency order:

```yaml
a: 10
b: "@a"              # resolved after a → 10
c: "$@a + @b"        # resolved after a and b → 20
d: "$@c * 2"         # resolved last → 40
```

!!! danger "Avoid Circular References"
    `a: "@b"` with `b: "@a"` can never be resolved: Sparkwheel raises `CircularReferenceError`.

## Best Practices

!!! success "Do This"
    - ✅ Use `@` references for DRY config
    - ✅ Enable schema validation for type safety
    - ✅ Change part of a section with a `::` path or `+key`
    - ✅ Use expressions for computed values
    - ✅ Keep configs simple and readable

!!! warning "Avoid This"
    - ❌ Don't create circular references
    - ❌ Don't overuse expressions (hurts readability)
    - ❌ Don't repeat a whole section to change one value
    - ❌ Don't put complex logic in configs

## Common Gotchas

| Issue | Problem | Solution |
|-------|---------|----------|
| **Reference not found** | `@key` doesn't exist | Check spelling and nesting |
| **Circular reference** | `a: "@b"`, `b: "@a"` | Restructure to break cycle |
| **Type mismatch** | Schema expects `int`, got `str` | Fix the value's type (quote it for `str`, leave quotes off for numbers) |
| **Expression error** | Invalid Python after `$` | Check syntax and references |
| **Section lost its keys** | A later file's `model: {lr: 0.01}` set the whole `model` | Write `model::lr: 0.01` or `+model: {lr: 0.01}` |
| **Component replaced** | `trainer: {max_epochs: 5}` on a `_target_` component | Write `+trainer` or `trainer::max_epochs` |
| **List not appended** | `+trainer: {callbacks: [x]}` set `callbacks` | Write `+trainer::callbacks: [x]` |
| **Key does not exist** | An override names a missing key | Fix the typo (or use `::`, not `.`); write `+key=value` to add a key |
| **`=` operator removed** | `=key` from Sparkwheel < 0.1 | Write `key`: setting replaces |

## File Organization

### Small Projects

```
project/
├── config.yaml          # Single config file
└── train.py
```

### Medium Projects

```
project/
├── configs/
│   ├── defaults.yaml    # Shared defaults
│   ├── dev.yaml         # Development
│   └── prod.yaml        # Production
└── train.py
```

### Large Projects

```
project/
├── configs/
│   ├── base/
│   │   ├── model.yaml
│   │   ├── dataset.yaml
│   │   └── training.yaml
│   ├── experiments/
│   │   ├── baseline.yaml
│   │   └── improved.yaml
│   └── env/
│       ├── dev.yaml
│       ├── staging.yaml
│       └── prod.yaml
└── train.py
```

## Next Steps

- **[Configuration Basics](basics.md)** - Learn config fundamentals
- **[References](references.md)** - Deep dive into `@` and `%`
- **[Expressions](expressions.md)** - Master `$` expressions
- **[Set, Combine, Delete](operators.md)** - `key`, `+key` and `~key`
- **[Schema Validation](schema-validation.md)** - Type-safe configs
- **[Troubleshooting](troubleshooting.md)** - Common errors and their fixes
