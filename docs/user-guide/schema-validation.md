# Schema Validation

Validate configurations at runtime using Python dataclasses.

## Quick Start

Define a schema with dataclasses:

```python
from dataclasses import dataclass
from sparkwheel import Config

@dataclass
class AppConfig:
    name: str
    port: int
    debug: bool = False

# Validate on load
config = Config.load("config.yaml", schema=AppConfig)

# Or validate explicitly
config = Config.load("config.yaml")
config.validate(AppConfig)
```

If validation fails, you get clear errors:

```python
# config.yaml:
# name: "myapp"
# port: "not a number"  # Wrong type!

config = Config.load("config.yaml", schema=AppConfig)
# ValidationError: Validation error at 'port': Type mismatch
#   Expected type: int
#   Actual type: str
#   Actual value: 'not a number'
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

### References

```python
@dataclass
class Config:
    base_lr: float
    optimizer_lr: float  # Can be a reference

config = Config.load({
    "base_lr": 0.001,
    "optimizer_lr": "@base_lr"  # Reference allowed
}, schema=Config)
```

### Expressions

```python
@dataclass
class Config:
    batch_size: int
    total_steps: int  # Computed

config = Config.load({
    "batch_size": 32,
    "total_steps": "$@batch_size * 100"  # Expression allowed
}, schema=Config)
```

### Instantiation

Special keys like `_target_` are automatically ignored:

```python
@dataclass
class OptimizerConfig:
    lr: float
    momentum: float = 0.9

config = Config.load({
    "_target_": "torch.optim.SGD",  # Ignored by validation
    "lr": 0.001,
    "momentum": 0.95
}, schema=OptimizerConfig)
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

### On Load (Recommended)

```python
config = Config.load("config.yaml", schema=MySchema)
# Raises ValidationError immediately
```

### Explicit

```python
config = Config.load("config.yaml")
# ... maybe modify ...
config.validate(MySchema)
```

### Standalone Function

```python
from sparkwheel import validate

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

# Load and validate
config = Config.load("production.yaml", schema=AppConfig)

# Access validated config
print(f"Starting {config['app_name']} on port {config['api::port']}")
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
