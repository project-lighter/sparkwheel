# Schema Validation

Validate configurations at runtime using Python dataclasses with **continuous validation** - errors caught immediately when you mutate the config.

## Coercion policy

`Config(schema=Schema, coerce=True)` normalizes compatible concrete values during
transactional `set()`/`update()` and checks resolved arguments during `resolve()`.
`validate(mapping, Schema)` and `config.validate(Schema)` check types without
coercing or executing configured references and expressions.

| Input | Declared type | Conversion |
|---|---|---|
| Numeric string | `int` / `float` | Parse a valid integer / float |
| Integral float, such as `3.0` | `int` | Convert without truncation |
| Integer | `float` | Convert only when exactly representable |
| `"true"`, `"yes"`, `"1"` / `"false"`, `"no"`, `"0"` | `bool` | Case-insensitive, ignoring surrounding whitespace |
| Integer `0` / `1` | `bool` | `False` / `True` |
| Integer, float, boolean | `str` | Built-in string conversion |

Booleans do not satisfy numeric fields, and lists/dicts are not converted to
strings. Dictionary keys are checked without coercion. Coercion recurses through
annotated containers and dataclasses. An already valid union branch wins, so
`int | str` preserves `"002"`; ambiguous conversions such as `"2"` to
`int | float` raise `ValidationError`. Set `coerce=False` to disable conversion.

## Quick Start

Define a schema with dataclasses:

```python title="app.py" hl_lines="10 14 15"
from dataclasses import dataclass
from sparkwheel import Config

@dataclass
class AppConfigSchema:
    name: str
    port: int
    debug: bool = False

# Continuous validation - validates on every update/set!
config = Config(schema=AppConfigSchema)  # (1)!
config.update("config.yaml")

# Errors caught immediately at mutation time
config.set("port", "8080")  # (2)!
config.set("port", "not a number")  # (3)!

# Or validate explicitly after loading
config = Config()
config.update("config.yaml")
config.validate(AppConfigSchema)  # (4)!
```

1. ✅ Enable continuous validation - errors caught on every mutation
2. ✅ Auto-coerced to `int(8080)` (coercion enabled by default)
3. ❌ Raises `ValidationError` immediately - invalid type conversion
4. ✅ Alternative: validate explicitly after loading all config

With **type coercion** enabled by default, compatible types are automatically converted:

```python
# config.yaml:
# name: "myapp"
# port: "8080"  # String value
# debug: "true" # String value

config = Config(schema=AppConfigSchema, coerce=True)
config.update("config.yaml")
# ✓ port coerced to int(8080)
# ✓ debug coerced to bool(True)
```

If validation fails, you get clear errors:

```python
# With coercion disabled
config = Config(schema=AppConfigSchema, coerce=False)
config.update({"port": "8080"})
# ValidationError: Validation error at 'port': Type mismatch
#   Expected type: int
#   Actual type: str
#   Actual value: '8080'
```

## Defining Schemas

Schemas are Python dataclasses with type hints. Postponed annotations are
resolved in the defining module; unresolved annotation names raise a clear error.
`strict` and `allow_missing` apply recursively, including selected union branches.

Dataclass defaults make fields optional for validation; they are not inserted
into the authored source or constructor arguments. Type-only validation does not
call default factories. A target's own Python signature determines its runtime
defaults. Custom validators do create a schema instance, so its defaults,
`default_factory`, and `__post_init__` may execute.

### Basic Types

```python
@dataclass
class ConfigSchema:
    text: str
    count: int
    ratio: float
    enabled: bool
    items: list[str]
    mapping: dict[str, int]
```

### Optional Fields

```python
from typing import Optional

@dataclass
class ConfigSchema:
    required: str
    optional_with_none: Optional[int] = None
    optional_with_default: int = 42
```

### Nested Dataclasses

```python
@dataclass
class DatabaseConfigSchema:
    host: str
    port: int
    pool_size: int = 10

@dataclass
class AppConfigSchema:
    database: DatabaseConfigSchema  # Nested
    secret_key: str
```

Corresponding YAML:

```yaml
database:
  host: localhost
  port: 5432
  # pool_size may be omitted; the schema does not insert it

secret_key: my-secret
```

### Lists of Dataclasses

```python
@dataclass
class PluginConfigSchema:
    name: str
    enabled: bool = True

@dataclass
class AppConfigSchema:
    plugins: list[PluginConfigSchema]
```

```yaml
plugins:
  - name: logger
    enabled: true
  - name: metrics
  - name: cache
    enabled: false
```

### Dictionaries with Dataclass Values

```python
@dataclass
class ModelConfigSchema:
    hidden_size: int
    dropout: float

@dataclass
class ConfigSchema:
    models: dict[str, ModelConfigSchema]
```

```yaml
models:
  small:
    hidden_size: 128
    dropout: 0.1
  large:
    hidden_size: 512
    dropout: 0.2
```

## Custom Validation

Add validation logic with `@validator`:

```python
from sparkwheel import validator

@dataclass
class TrainingConfigSchema:
    lr: float
    batch_size: int

    @validator
    def check_lr(self):
        """Validate learning rate."""
        if not (0 < self.lr < 1):
            raise ValueError(f"lr must be between 0 and 1, got {self.lr}")

    @validator
    def check_batch_size(self):
        """Validate batch size is power of 2."""
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.batch_size & (self.batch_size - 1) != 0:
            raise ValueError("batch_size must be power of 2")
```

### Cross-Field Validation

Validators can check relationships between fields:

```python
@dataclass
class ConfigSchema:
    start_epoch: int
    end_epoch: int
    warmup_epochs: int

    @validator
    def check_epochs(self):
        """Ensure epoch configuration is valid."""
        if self.end_epoch <= self.start_epoch:
            raise ValueError("end_epoch must be > start_epoch")
        if self.warmup_epochs >= (self.end_epoch - self.start_epoch):
            raise ValueError("warmup_epochs too large")
```

### With Optional Fields

```python
@dataclass
class ConfigSchema:
    value: float
    max_value: Optional[float] = None

    @validator
    def check_max(self):
        """Check value doesn't exceed max if specified."""
        if self.max_value is not None and self.value > self.max_value:
            raise ValueError(f"value ({self.value}) exceeds max_value ({self.max_value})")
```

Validators run after type checking. Framework metadata such as `_target_` and
lenient extra keys are excluded from the schema instance's initializer. Setup
failures and unexpected validator exceptions propagate as contextual
`ValidationError` with their original cause, including inside unions. Validator
code can have external effects; configuration rollback cannot undo them. Prefer
pure checks. Nested argument dictionaries remain dictionaries in validator
instances; schemas do not recursively instantiate nested dataclasses for you.

## Discriminated Unions

Use tagged unions for type-safe variants:

```python
from typing import Literal, Union

@dataclass
class SGDOptimizerSchema:
    type: Literal["sgd"]  # Discriminator
    lr: float
    momentum: float = 0.9

@dataclass
class AdamOptimizerSchema:
    type: Literal["adam"]  # Discriminator
    lr: float
    beta1: float = 0.9

@dataclass
class ConfigSchema:
    optimizer: Union[SGDOptimizerSchema, AdamOptimizerSchema]
```

YAML:

```yaml
optimizer:
  type: sgd  # Selects SGDOptimizer
  lr: 0.01
  momentum: 0.95
```

Sparkwheel detects `type` as a discriminator and validates against the matching schema.

**Error examples:**

```python
# Missing discriminator
{"optimizer": {"lr": 0.01}}
# ValidationError: Missing discriminator field 'type'

# Invalid value
{"optimizer": {"type": "rmsprop", "lr": 0.01}}
# ValidationError: Invalid discriminator value 'rmsprop'. Valid: 'sgd', 'adam'

# Wrong fields for type
{"optimizer": {"type": "adam", "momentum": 0.9}}
# ValidationError: Missing required field 'lr'
```

## With Sparkwheel Features

Validation works with references, expressions, and instantiation.

## Type Coercion

Sparkwheel automatically converts compatible types when `coerce=True` (default):

```python
@dataclass
class ServerConfigSchema:
    port: int
    timeout: float
    enabled: bool

# Coercion enabled by default
config = Config(schema=ServerConfigSchema)
config.update({
    "port": "8080",        # str → int
    "timeout": "30.5",     # str → float
    "enabled": "true"      # str → bool
})

print(config["port"])      # 8080 (int, not str!)
print(config["timeout"])   # 30.5 (float)
print(config["enabled"])   # True (bool)
```

**Supported coercions:**
- `str → int` (e.g., `"42"` → `42`)
- `str → float` (e.g., `"3.14"` → `3.14`)
- `str → bool` (e.g., `"true"` → `True`, `"false"` → `False`)
- `int → float` (e.g., `42` → `42.0`)
- Recursive coercion through lists, dicts, and nested dataclasses

**Disable coercion if needed:**

```python
config = Config(schema=ServerConfigSchema, coerce=False)
config.update({
    "port": "8080"  # ValidationError: expected int, got str
})
```

## Strict vs Lenient Mode

Control whether extra fields are rejected:

```python
@dataclass
class MySchema:
    required_field: int

# Strict mode (default) - rejects extra fields
config = Config(schema=MySchema, strict=True)
config.update({
    "required_field": 42,
    "extra_field": "oops"  # ✗ ValidationError!
})

# Lenient mode - allows extra fields
config = Config(schema=MySchema, strict=False)
config.update({
    "required_field": 42,
    "extra_field": "ok"  # ✓ Allowed
})
```

Use lenient mode for:
- Development/prototyping
- Gradual schema migration
- Configs with experimental fields

## MISSING Sentinel

Support partial configs with required-but-not-yet-set values:

```python
from sparkwheel import Config, MISSING

@dataclass
class APIConfigSchema:
    api_key: str
    endpoint: str
    timeout: int = 30

# Partial config - api_key not set yet
config = Config(schema=APIConfigSchema, allow_missing=True)
config.update({
    "api_key": MISSING,
    "endpoint": "https://api.example.com"
})

# Later, fill in the missing value
import os
config.set("api_key", os.getenv("API_KEY"))

# Now validate that nothing is MISSING
config.validate(APIConfigSchema)  # Uses allow_missing=False by default
```

## Frozen Configs

Prevent modifications after initialization:

```python
config = Config(schema=MySchema)
config.update("config.yaml")
config.freeze()

# Mutations now raise FrozenConfigError
config.set("model::lr", 0.001)  # ✗ FrozenConfigError!
config.update({"new": "data"})   # ✗ FrozenConfigError!

# Read operations still work
value = config.get("model::lr")
resolved = config.resolve()

# Unfreeze if needed
config.unfreeze()
config.set("model::lr", 0.001)  # ✓ Now works
```

## With Sparkwheel Features

Validation works with references, expressions, and instantiation.

### References

```python
@dataclass
class ConfigSchema:
    base_lr: float
    optimizer_lr: float  # Can be a reference

config = Config(schema=ConfigSchema)
config.update({
    "base_lr": 0.001,
    "optimizer_lr": "@base_lr"  # Reference allowed
})
```

### Expressions

```python
@dataclass
class ConfigSchema:
    batch_size: int
    total_steps: int  # Computed

config = Config(schema=ConfigSchema)
config.update({
    "batch_size": 32,
    "total_steps": "$@batch_size * 100"  # Expression allowed
})
```

### Instantiation

Special keys like `_target_` are automatically ignored:

```python
@dataclass
class OptimizerConfigSchema:
    lr: float
    momentum: float = 0.9

config = Config(schema=OptimizerConfigSchema)
config.update({
    "_target_": "torch.optim.SGD",  # Ignored by validation
    "lr": 0.001,
    "momentum": 0.95
})
```

## Error Messages

### Type Mismatch

```python
# Expected int, got str
# ValidationError: Validation error at 'port': Type mismatch
#   Expected type: int
#   Actual type: str
#   Actual value: '8080'
```

### Missing Field

```python
# ValidationError: Validation error at 'required_field':
#   Missing required field 'required_field'
#   Expected type: str
```

### Unexpected Field

```python
# ValidationError: Validation error at 'unexpected':
#   Unexpected field 'unexpected' not in schema ConfigSchema
```

### Nested Errors

```python
# ValidationError: Validation error at 'database.port': Type mismatch
#   Expected type: int
#   Actual type: str
#   Actual value: 'wrong'
```

## Validation Timing

`set()` and `update()` validate the staged authored source once and publish it
only on success. Deferred `@`, `$`, and `%` values are checked when resolved. A
deferred union discriminator postpones branch checks until the branch is known.

`resolve(path)` validates that node and its ordinary dependencies. It also
resolves a deferred union discriminator when needed to select that node's schema,
so parent values and later child resolutions use the same coerced cache. It does not
construct unrelated nodes to run a root-level cross-field validator; use
`resolve()` to validate the complete resolved argument tree. For `_target_`
nodes, schemas describe **constructor arguments**, not the object returned by
the target. Invalid resolved arguments fail before that target is called.
Dependencies, imports, and expressions may already have executed; resolution is
not an effect rollback mechanism.

Nested components and aliases are checked using their resolved argument
mappings while constructors receive their native objects. Existing shared
container/component identities are preserved. An alias cannot coerce an
already-built object's argument mapping into a different schema. Expression
coercion affects runtime values and preserves the authored expression string.
`instantiate=False` still checks resolved arguments; `eval_expr=False` keeps
wrappers and postpones resolved-value checks.

Retained construction scopes currently reject attached schemas explicitly.
Use schema-aware `Config.resolve()` for these configurations; a retained scope
must not silently discard a schema policy.


### Continuous (Recommended)

```python
# Validates on every update() and set()
config = Config(schema=MySchema)
config.update("config.yaml")
config.set("port", "8080")  # Validates immediately!
```

### Explicit

```python
# Load without schema, validate later
config = Config()
config.update("config.yaml")
# ... maybe modify ...
config.validate(MySchema)
```

### Standalone Function

```python
from sparkwheel import validate

# Validate a dict directly
validate(config_dict, AppConfigSchema)
```

## Complete Example

```python
from dataclasses import dataclass
from typing import Optional
from sparkwheel import Config, validator

@dataclass
class DatabaseConfigSchema:
    host: str
    port: int
    database: str
    username: str
    password: str
    pool_size: int = 10
    timeout: int = 30

@dataclass
class APIConfigSchema:
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    @validator
    def check_port(self):
        if not (1024 <= self.port <= 65535):
            raise ValueError(f"port must be 1024-65535, got {self.port}")

@dataclass
class AppConfigSchema:
    app_name: str
    environment: str
    api: APIConfigSchema
    database: DatabaseConfigSchema
    debug: bool = False

# Load and validate continuously
config = Config(schema=AppConfigSchema)
config.update("production.yaml")

# Access validated config
print(f"Starting {config['app_name']} on port {config['api::port']}")

# Freeze to prevent modifications
config.freeze()
```

The YAML:

```yaml
app_name: "My API"
environment: production
debug: false

api:
  port: 3000
  workers: 8

database:
  host: db.example.com
  port: 5432
  database: myapp
  username: "$import os; os.getenv('DB_USER')"
  password: "$import os; os.getenv('DB_PASSWORD')"
  pool_size: 20
```

## Next Steps

- **[Configuration Basics](basics.md)** - Learn config management
- **[References](references.md)** - Link values with @
- **[Expressions](expressions.md)** - Compute values with $
