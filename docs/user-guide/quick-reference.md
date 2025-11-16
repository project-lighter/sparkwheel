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

    | Expression | Description | Example |
    |------------|-------------|---------|
    | `$(@a + @b)` | Math operations | `$(@lr * 0.1)` |
    | `$(@name + "_v2")` | String concatenation | `$(@model_name + "_trained")` |
    | `$(@debug ? "dev" : "prod")` | Ternary conditional | `$(@is_training ? 0.5 : 0.0)` |
    | `$(@items[0])` | Dynamic indexing | `$(@datasets[@mode])` |
    | `$len(@items)` | Built-in functions | `$len(@layers)` |

=== "Operators"

    | Operator | Purpose | Example | Result |
    |----------|---------|---------|--------|
    | `=key` | Replace (don't merge) | `=optimizer: sgd` | Replaces entire dict/value |
    | `~key` | Delete key | `~debug: true` | Removes the key |
    | `~list: [0, 2]` | Delete list items | `~layers: [1, 3]` | Removes items at indices 1 and 3 |
    | (none) | Default: Merge | `model: {size: 512}` | Merges with existing dict |

=== "Instantiation"

    | Key | Type | Purpose | Example |
    |-----|------|---------|---------|
    | `_target_` | str | Class/function to instantiate | `torch.optim.Adam` |
    | `_partial_` | bool | Return partial function | `true` |
    | `_disabled_` | bool | Skip instantiation | `true` |
    | `_mode_` | str | Instantiation mode | `"dict"` / `"dataclass"` |

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

training:
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
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10

optimizer:
  _target_: torch.optim.Adam
  params: "$@model.parameters()"
  lr: 0.001
```

### Config Composition

```yaml title="base.yaml"
model:
  hidden_size: 512
  dropout: 0.1
```

```yaml title="override.yaml"
# Merge by default
model:
  hidden_size: 1024  # Updates only this field

# Or replace completely
=model:
  hidden_size: 1024  # Replaces entire dict
```

## Type Coercion

| From | To | Supported | Notes |
|------|----|-----------| ------|
| str → int | ✅ | `"42"` → `42` |
| str → float | ✅ | `"3.14"` → `3.14` |
| str → bool | ✅ | `"true"` → `True` | Accepts: true/false, yes/no, 1/0 |
| int → float | ✅ | `42` → `42.0` |
| float → int | ✅ | `3.14` → `3` | Truncates decimal |
| Any → str | ✅ | Universal |

## CLI Overrides

=== "Direct Assignment"

    ```bash
    python train.py learning_rate=0.01 batch_size=64
    ```

=== "Nested Keys"

    ```bash
    python train.py model.hidden_size=1024 optimizer.lr=0.001
    ```

=== "List Values"

    ```bash
    python train.py layers=[128,256,512]
    ```

=== "Replace vs Merge"

    ```bash
    # Merge (default)
    python train.py model.dropout=0.2

    # Replace entire section
    python train.py =model={hidden_size:1024}
    ```

## Schema Validation

```python
from dataclasses import dataclass
from sparkwheel import Config, validator

@dataclass
class AppConfig:
    name: str
    port: int
    debug: bool = False

    @validator
    def check_port(self):
        if not (1024 <= self.port <= 65535):
            raise ValueError(f"Invalid port: {self.port}")

# Continuous validation (validates on every mutation)
config = Config(schema=AppConfig)

# Or explicit validation
config = Config()
config.update("config.yaml")
config.validate(AppConfig)
```

## Resolution Order

References are resolved in dependency order:

```yaml
a: 10
b: "@a"              # Resolved first (depends on a)
c: "$@a + @b"        # Resolved after a and b
d: "$@c * 2"         # Resolved last (depends on c)
```

!!! danger "Avoid Circular References"
    ```yaml
    # ❌ This will fail!
    a: "@b"
    b: "@a"
    ```

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
| **Type mismatch** | Schema expects `int`, got `str` | Enable coercion or fix type |
| **Expression error** | Invalid Python in `$()` | Check syntax and references |
| **Unexpected merge** | Dict merged when you wanted replace | Use `=key` to replace |
| **List not extending** | List replaced instead of extended | This is default for scalars, expected |

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

## Performance Tips

!!! info "Expression Evaluation"
    Expressions are evaluated at **access time**. For frequently accessed values:

    ```python
    # Slow: Re-evaluates expression each time
    for i in range(1000):
        x = config.resolve("computed_value")

    # Fast: Evaluate once
    computed = config.resolve("computed_value")
    for i in range(1000):
        x = computed
    ```

## Next Steps

- **[Configuration Basics](basics.md)** - Learn config fundamentals
- **[References](references.md)** - Deep dive into `@` and `%`
- **[Expressions](expressions.md)** - Master `$()` expressions
- **[Operators](operators.md)** - Composition with `=` and `~`
- **[Schema Validation](schema-validation.md)** - Type-safe configs
