# Schema Validation

Validate your configurations at runtime using Python dataclasses. Define the expected structure and types of your config, then let Sparkwheel catch errors early with clear, helpful messages.

## Quick Start

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

If your YAML doesn't match the schema, you'll get a clear error:

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

## Why Use Schema Validation?

Schema validation catches configuration errors early:

- **Type safety**: Ensure values have the correct types (int, str, float, etc.)
- **Required fields**: Catch missing configuration early
- **Clear errors**: Get specific error messages pointing to the problem
- **Documentation**: Schemas serve as documentation for your config structure
- **IDE support**: Get autocomplete and type checking in your IDE

## Defining Schemas

Schemas are just Python dataclasses with type hints:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class DatabaseConfig:
    host: str
    port: int
    username: str
    password: str
    pool_size: int = 10  # Optional with default

@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

@dataclass
class AppConfig:
    server: ServerConfig  # Nested schema
    database: DatabaseConfig
    secret_key: str
```

The corresponding YAML:

```yaml
server:
  port: 3000
  # host and debug use defaults

database:
  host: localhost
  port: 5432
  username: admin
  password: secret
  # pool_size uses default of 10

secret_key: my-secret-key
```

## Supported Types

### Basic Types

```python
@dataclass
class BasicTypes:
    text: str
    count: int
    ratio: float
    enabled: bool
```

### Lists

```python
@dataclass
class ListConfig:
    items: list[str]  # List of strings
    numbers: list[int]  # List of integers
    matrix: list[list[float]]  # Nested lists
```

```yaml
items:
  - apple
  - banana
  - orange

numbers: [1, 2, 3, 4, 5]

matrix:
  - [1.0, 2.0]
  - [3.0, 4.0]
```

### Dictionaries

```python
@dataclass
class DictConfig:
    mapping: dict[str, int]
    settings: dict[str, str]
```

```yaml
mapping:
  a: 1
  b: 2
  c: 3

settings:
  theme: dark
  language: en
```

### Optional Fields

Use `Optional[T]` for fields that may be `None`:

```python
from typing import Optional

@dataclass
class OptionalConfig:
    required: str
    optional_with_none: Optional[int] = None
    optional_with_default: int = 42
```

All three ways work:

```yaml
# Option 1: Provide all values
required: "value"
optional_with_none: 10
optional_with_default: 100

# Option 2: Use None explicitly
required: "value"
optional_with_none: null
optional_with_default: 50

# Option 3: Omit optional fields (use defaults)
required: "value"
```

### Nested Dataclasses

Build complex schemas by nesting dataclasses:

```python
@dataclass
class OptimizerConfig:
    lr: float
    momentum: float = 0.9
    weight_decay: float = 0.0

@dataclass
class ModelConfig:
    hidden_size: int
    num_layers: int
    dropout: float
    optimizer: OptimizerConfig  # Nested

@dataclass
class TrainingConfig:
    batch_size: int
    epochs: int
    model: ModelConfig  # Nested
```

```yaml
batch_size: 32
epochs: 100

model:
  hidden_size: 512
  num_layers: 6
  dropout: 0.1

  optimizer:
    lr: 0.001
    momentum: 0.95
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

## Validation with Sparkwheel Features

Schema validation works seamlessly with Sparkwheel's references, expressions, and instantiation.

### References

References (`@`) are allowed and validated after resolution:

```python
@dataclass
class Config:
    base_lr: float
    optimizer_lr: float  # Will reference base_lr

config = Config.load({
    "base_lr": 0.001,
    "optimizer_lr": "@base_lr"
}, schema=Config)

# Passes validation - @base_lr is allowed for float field
```

### Expressions

Expressions (`$`) are validated as the target type:

```python
@dataclass
class Config:
    batch_size: int
    total_steps: int  # Computed via expression

config = Config.load({
    "batch_size": 32,
    "total_steps": "$@batch_size * 100"
}, schema=Config)

# Passes validation - expression will evaluate to int
```

### Component Instantiation

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

# Passes - _target_, _disabled_, etc. are special keys
```

## Error Messages

Schema validation provides detailed error messages:

### Type Mismatch

```python
@dataclass
class Config:
    port: int

Config.load({"port": "8080"}, schema=Config)
# ValidationError: Validation error at 'port': Type mismatch
#   Expected type: int
#   Actual type: str
#   Actual value: '8080'
```

### Missing Required Field

```python
@dataclass
class Config:
    required_field: str

Config.load({}, schema=Config)
# ValidationError: Validation error at 'required_field':
#   Missing required field 'required_field'
#   Expected type: str
```

### Unexpected Field

```python
@dataclass
class Config:
    allowed: str

Config.load({"allowed": "ok", "unexpected": "oops"}, schema=Config)
# ValidationError: Validation error at 'unexpected':
#   Unexpected field 'unexpected' not in schema Config
```

### Nested Field Errors

```python
@dataclass
class Inner:
    value: int

@dataclass
class Outer:
    inner: Inner

Config.load({"inner": {"value": "wrong"}}, schema=Outer)
# ValidationError: Validation error at 'inner.value': Type mismatch
#   Expected type: int
#   Actual type: str
#   Actual value: 'wrong'
```

## Validation Timing

### Validate on Load (Recommended)

Catch errors immediately when loading config:

```python
config = Config.load("config.yaml", schema=MySchema)
# Raises ValidationError if config doesn't match schema
```

### Validate Explicitly

Load first, validate later:

```python
config = Config.load("config.yaml")
# ... maybe modify config ...
config.validate(MySchema)
# Raises ValidationError if current config doesn't match schema
```

### Validate Function

Use the standalone `validate()` function:

```python
from sparkwheel import validate

config_dict = {
    "name": "myapp",
    "port": 8080
}

validate(config_dict, AppSchema)
# Raises ValidationError if invalid
```

## Real-World Example

Here's a complete example of a web API configuration:

```python
from dataclasses import dataclass, field
from typing import Optional
from sparkwheel import Config

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
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None

@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "json"
    file: Optional[str] = None

@dataclass
class APIConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    cors_origins: list[str] = field(default_factory=list)

@dataclass
class AppConfig:
    app_name: str
    environment: str
    debug: bool = False
    api: APIConfig
    database: DatabaseConfig
    redis: RedisConfig
    logging: LoggingConfig

# Load and validate
config = Config.load("production.yaml", schema=AppConfig)

# Access validated config
print(f"Starting {config['app_name']} on port {config['api::port']}")

# Resolve and use
db_config = config.resolve("database")
```

The YAML file:

```yaml
app_name: "My API"
environment: production
debug: false

api:
  port: 3000
  workers: 8
  cors_origins:
    - https://example.com
    - https://app.example.com

database:
  host: db.example.com
  port: 5432
  database: myapp
  username: "$import os; os.getenv('DB_USER')"
  password: "$import os; os.getenv('DB_PASSWORD')"
  pool_size: 20

redis:
  host: redis.example.com
  password: "$import os; os.getenv('REDIS_PASSWORD')"

logging:
  level: WARNING
  file: /var/log/myapp/app.log
```

## Best Practices

### 1. Define Schemas Close to Usage

Keep schema definitions near the code that uses them:

```python
# config/schemas.py
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    host: str
    port: int
    # ...

# database/connection.py
from config.schemas import DatabaseConfig
from sparkwheel import Config

def connect_to_database():
    config = Config.load("db.yaml", schema=DatabaseConfig)
    db_config = config.resolve("database")
    # Use validated config...
```

### 2. Use Type Hints Everywhere

Make your intent clear with specific types:

```python
@dataclass
class GoodConfig:
    count: int  # Clear
    ratio: float  # Clear
    items: list[str]  # Specific list type
```

### 3. Provide Sensible Defaults

Make optional fields truly optional:

```python
@dataclass
class Config:
    # Required (no default)
    api_key: str

    # Optional with good defaults
    timeout: int = 30
    retry_count: int = 3
    debug: bool = False
```

### 4. Document Complex Schemas

Use docstrings and comments:

```python
@dataclass
class ModelConfig:
    """Configuration for the neural network model.

    Attributes:
        hidden_size: Number of hidden units (typically 128-1024)
        num_layers: Number of transformer layers
        dropout: Dropout probability (0.0-0.5 recommended)
    """
    hidden_size: int
    num_layers: int
    dropout: float = 0.1  # Default works well for most cases
```

### 5. Validate Early

Always validate at the entry point of your application:

```python
def main():
    # Validate immediately
    config = Config.load("config.yaml", schema=AppConfig)

    # Now you can trust the config structure
    run_app(config)
```

## When Not to Use Schemas

Schema validation is optional. Skip it when:

- Prototyping or experimenting
- Config structure is extremely dynamic
- Using third-party configs you don't control
- Performance is critical (validation has small overhead)

You can always add schemas later as your project matures:

```python
# Early development - no schema
config = Config.load("config.yaml")

# Production - with validation
config = Config.load("config.yaml", schema=ProductionConfig)
```

## Next Steps

- [References](references.md) - Link configuration values with @
- [Expressions](expressions.md) - Compute values with Python expressions
- [Instantiation](instantiation.md) - Create objects from configuration
- [Merging](merging.md) - Combine multiple configuration files
