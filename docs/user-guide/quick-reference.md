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

    Files and dicts merge by default; `=` replaces and `~` deletes.

    ```yaml title="base.yaml"
    debug: true
    layers: [64, 128, 256, 512]
    model: {size: 256, dropout: 0.1}
    scheduler: {name: cosine, warmup: 5}
    ```

    ```yaml title="experiment.yaml"
    model: {size: 512}          # merge (default) → {size: 512, dropout: 0.1}
    =scheduler: {name: step}    # replace → {name: step}
    ~debug: null                # delete the key
    ~layers: [1, 3]             # delete list items 1 and 3 → [64, 256]
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

### Config Composition

Later files merge into earlier ones (`python train.py base.yaml override.yaml replace.yaml`):

```yaml title="base.yaml"
model:
  hidden_size: 512
  dropout: 0.1
```

```yaml title="override.yaml"
model:  # merged → {hidden_size: 1024, dropout: 0.1}
  hidden_size: 1024
```

```yaml title="replace.yaml"
=model:  # replaced → {hidden_size: 256}
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

!!! warning "Replace a list with `=`"
    `model::channels=[64,128]` is an error on a list that has items. Write `=model::channels=[64,128]` to replace it.

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
    python train.py config.yaml =model::channels=[64,128]  # → [64, 128]
    ```

=== "Replace and delete"

    ```bash
    python train.py config.yaml '=model={hidden_size: 1024}'  # → {hidden_size: 1024}
    python train.py config.yaml '~model::dropout'
    ```

Overrides change keys that exist, or add an argument to a `_target_` component. Anything else is most likely a typo and raises an error with a did-you-mean; put new keys in a YAML file. Values follow YAML rules (`8` is an int, `[1,2]` a list, `{a: 1}` a dict — note the space after `:`); quote overrides that contain spaces or `$`, `@`, `~` for your shell.

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
    - ✅ Leverage composition-by-default (no operators needed)
    - ✅ Use expressions for computed values
    - ✅ Keep configs simple and readable

!!! warning "Avoid This"
    - ❌ Don't create circular references
    - ❌ Don't overuse expressions (hurts readability)
    - ❌ Don't use operators when default composition works
    - ❌ Don't put complex logic in configs

## Common Gotchas

| Issue | Problem | Solution |
|-------|---------|----------|
| **Reference not found** | `@key` doesn't exist | Check spelling and nesting |
| **Circular reference** | `a: "@b"`, `b: "@a"` | Restructure to break cycle |
| **Type mismatch** | Schema expects `int`, got `str` | Fix the value's type (quote it for `str`, leave quotes off for numbers) |
| **Expression error** | Invalid Python after `$` | Check syntax and references |
| **Unexpected merge** | Dict merged when you wanted replace | Use `=key` to replace |
| **List grew** | A YAML file's `layers: [1, 2]` extended the list | Use `=layers: [1, 2]` to replace |
| **Override is a list** | `layers=[1,2]` on a list that has items | Use `=layers=[1,2]` to replace |
| **Key does not exist** | An override names a missing key | Fix the typo (or use `::`, not `.`); put new keys in a YAML file |

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
- **[Operators](operators.md)** - Composition with `=` and `~`
- **[Schema Validation](schema-validation.md)** - Type-safe configs
- **[Troubleshooting](troubleshooting.md)** - Common errors and their fixes
