# Schema Validation

Validate configurations at runtime using Python dataclasses with **continuous validation** - errors caught immediately when you mutate the config.

## Type Coercion Matrix

Sparkwheel automatically converts compatible types when coercion is enabled (default: `True`):

| From ↓ To → | `int` | `float` | `str` | `bool` | `list` | `dict` |
|-------------|-------|---------|-------|--------|--------|--------|
| **int** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **float** | ✅* | ✅ | ✅ | ❌ | ❌ | ❌ |
| **str** | ✅** | ✅** | ✅ | ✅*** | ❌ | ❌ |
| **bool** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **list** | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |
| **dict** | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |

\* Truncates decimal part (e.g., `3.14` → `3`)
\*\* Requires valid format (e.g., `"42"` for int, `"3.14"` for float)
\*\*\* Accepts: `"true"`, `"false"`, `"1"`, `"0"`, `"yes"`, `"no"` (case-insensitive)

!!! success "Default Behavior"
    Type coercion is **enabled by default** to handle common cases like environment variables and CLI arguments (which are always strings).

!!! warning "Disable for Strict Validation"
    Set `coerce=False` for strict type checking:
    ```python
    config = Config(schema=AppConfig, coerce=False)
    ```

## Quick Start

Define a schema with dataclasses:

```python title="app.py" hl_lines="10 14 15"
from dataclasses import dataclass
from sparkwheel import Config

@dataclass
class AppConfig:
    name: str
    port: int
    debug: bool = False

# Continuous validation - validates on every update/set!
config = Config(schema=AppConfig)  # (1)!
config.update("config.yaml")

# Errors caught immediately at mutation time
config.set("port", "8080")  # (2)!
config.set("port", "not a number")  # (3)!

# Or validate explicitly after loading
config = Config()
config.update("config.yaml")
config.validate(AppConfig)  # (4)!
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

config = Config(schema=AppConfig, coerce=True)
config.update("config.yaml")
# ✓ port coerced to int(8080)
# ✓ debug coerced to bool(True)
```

If validation fails, you get clear errors:

```python
# With coercion disabled
config = Config(schema=AppConfig, coerce=False)
config.update({"port": "8080"})
# ValidationError: Validation error at 'port': Type mismatch
#   Expected type: int
#   Actual type: str
#   Actual value: '8080'
```

## Defining Schemas

Schemas are Python dataclasses with type hints.

### Basic Types

```python
@dataclass
class Config:
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
class Config:
    required: str
    optional_with_none: Optional[int] = None
    optional_with_default: int = 42
```

### Nested Dataclasses

```python
@dataclass
class DatabaseConfig:
    host: str
    port: int
    pool_size: int = 10

@dataclass
class AppConfig:
    database: DatabaseConfig  # Nested
    secret_key: str
```

Corresponding YAML:

```yaml
database:
  host: localhost
  port: 5432
  # pool_size uses default

secret_key: my-secret
```

### Lists of Dataclasses

```python
@dataclass
class PluginConfig:
    name: str
    enabled: bool = True

@dataclass
class AppConfig:
    plugins: list[PluginConfig]
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
class ModelConfig:
    hidden_size: int
    dropout: float

@dataclass
class Config:
    models: dict[str, ModelConfig]
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
class TrainingConfig:
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
class Config:
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
class Config:
    value: float
    max_value: Optional[float] = None

    @validator
    def check_max(self):
        """Check value doesn't exceed max if specified."""
        if self.max_value is not None and self.value > self.max_value:
            raise ValueError(f"value ({self.value}) exceeds max_value ({self.max_value})")
```

**Note:** Validators run after type checking. If types are wrong, validation stops there.

## Discriminated Unions

Use tagged unions for type-safe variants:

```python
from typing import Literal, Union

@dataclass
class SGDOptimizer:
    type: Literal["sgd"]  # Discriminator
    lr: float
    momentum: float = 0.9

@dataclass
class AdamOptimizer:
    type: Literal["adam"]  # Discriminator
    lr: float
    beta1: float = 0.9

@dataclass
class Config:
    optimizer: Union[SGDOptimizer, AdamOptimizer]
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
class ServerConfig:
    port: int
    timeout: float
    enabled: bool

# Coercion enabled by default
config = Config(schema=ServerConfig)
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
config = Config(schema=ServerConfig, coerce=False)
config.update({
    "port": "8080"  # ValidationError: expected int, got str
})
```

## Strict vs Lenient Mode

Control whether extra fields are rejected:

```python
@dataclass
class Schema:
    required_field: int

# Strict mode (default) - rejects extra fields
config = Config(schema=Schema, strict=True)
config.update({
    "required_field": 42,
    "extra_field": "oops"  # ✗ ValidationError!
})

# Lenient mode - allows extra fields
config = Config(schema=Schema, strict=False)
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
class APIConfig:
    api_key: str
    endpoint: str
    timeout: int = 30

# Partial config - api_key not set yet
config = Config(schema=APIConfig, allow_missing=True)
config.update({
    "api_key": MISSING,
    "endpoint": "https://api.example.com"
})

# Later, fill in the missing value
import os
config.set("api_key", os.getenv("API_KEY"))

# Now validate that nothing is MISSING
config.validate(APIConfig)  # Uses allow_missing=False by default
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
class Config:
    base_lr: float
    optimizer_lr: float  # Can be a reference

config = Config(schema=Config)
config.update({
    "base_lr": 0.001,
    "optimizer_lr": "@base_lr"  # Reference allowed
})
```

### Expressions

```python
@dataclass
class Config:
    batch_size: int
    total_steps: int  # Computed

config = Config(schema=Config)
config.update({
    "batch_size": 32,
    "total_steps": "$@batch_size * 100"  # Expression allowed
})
```

### Instantiation

Special keys like `_target_` are automatically ignored:

```python
@dataclass
class OptimizerConfig:
    lr: float
    momentum: float = 0.9

config = Config(schema=OptimizerConfig)
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
#   Unexpected field 'unexpected' not in schema Config
```

### Nested Errors

```python
# ValidationError: Validation error at 'database.port': Type mismatch
#   Expected type: int
#   Actual type: str
#   Actual value: 'wrong'
```

## Validation Timing

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
validate(config_dict, AppSchema)
```

## Complete Example

```python
from dataclasses import dataclass
from typing import Optional
from sparkwheel import Config, validator

@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    pool_size: int = 10
    timeout: int = 30

@dataclass
class APIConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    @validator
    def check_port(self):
        if not (1024 <= self.port <= 65535):
            raise ValueError(f"port must be 1024-65535, got {self.port}")

@dataclass
class AppConfig:
    app_name: str
    environment: str
    debug: bool = False
    api: APIConfig
    database: DatabaseConfig

# Load and validate continuously
config = Config(schema=AppConfig)
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
