# Configuration Basics

Learn the fundamentals of Sparkwheel configuration files.

## Configuration File Format

Sparkwheel uses YAML for configuration:

```yaml
# config.yaml
name: "My Project"
version: 1.0
settings:
  debug: true
  timeout: 30
```

YAML provides excellent readability and native support for comments, making it ideal for configuration files.

## Loading Configurations

### Basic Loading

```python
from sparkwheel import Config

# Load from file
config = Config.load("config.yaml")
```

### Loading from Dictionary

```python
config_dict = {
    "name": "Test",
    "value": 42
}

# Load from dict
config = Config.load(config_dict)
```

### Loading Multiple Files

```python
# Load and merge multiple config files
config = Config.load(["base.yaml", "override.yaml"])
```

## Accessing Configuration Values

Sparkwheel provides two equivalent syntaxes for accessing nested configuration values:

### Two Ways to Access Nested Values

```python
config = Config.load("config.yaml")

# Method 1: Standard nested dictionary access
name = config["name"]
debug = config["settings"]["debug"]
lr = config["model"]["optimizer"]["lr"]

# Method 2: Path notation with :: separator
debug = config["settings::debug"]
lr = config["model::optimizer::lr"]

# Both methods work identically!
assert config["settings"]["debug"] == config["settings::debug"]
```

**When to use each:**

- **Nested access** (`config["a"]["b"]`) - Familiar Python syntax, works like any dict
- **Path notation** (`config["a::b"]`) - More concise for deeply nested values, easier to pass as strings

### Using get() and resolve()

The same two syntaxes work with `get()` and `resolve()`:

```python
# Method 1: Nested access
raw_value = config.get("model")["optimizer"]["lr"]

# Method 2: Path notation (more convenient)
raw_value = config.get("model::optimizer::lr")

# Both work with resolve() too
debug_mode = config.resolve("settings::debug")
debug_mode = config.resolve("settings")["debug"]  # Also works

# Resolve entire config
all_config = config.resolve()

# Resolve specific section
training_config = config.resolve("training")
```

**Key difference:**
- `get()` returns raw values (references like `"@model::lr"` are not resolved)
- `resolve()` resolves references, evaluates expressions, and instantiates objects

## Choosing Between Syntaxes

Both syntaxes have their place:

### Use Path Notation (`::`) When:

```python
# 1. Passing paths as function arguments
def get_param(config, path: str):
    return config.get(path)

lr = get_param(config, "model::optimizer::lr")

# 2. Working with very deep nesting (more readable)
value = config["a::b::c::d::e"]

# 3. Setting values programmatically
config.set("model::optimizer::lr", 0.001)

# 4. Matching reference syntax in YAML
# YAML: lr: "@model::optimizer::base_lr"
base_lr = config.get("model::optimizer::base_lr")
```

### Use Standard Dict Access When:

```python
# 1. You want to work with intermediate sections
model_config = config["model"]
model_config["dropout"] = 0.1
model_config["lr"] = 0.001

# 2. Iterating over config sections
for key in config["training"].keys():
    print(key, config["training"][key])

# 3. It feels more natural for your use case
settings = config["app"]["settings"]
if settings["debug"]:
    print("Debug mode enabled")
```

## Configuration Structure

### Nested Structures

```yaml
project:
  name: "Sparkwheel Demo"
  version: 1.0

  database:
    host: "localhost"
    port: 5432
    credentials:
      username: "admin"
      password: "secret"

  features:
    authentication: true
    logging: true
```

Access nested values with either syntax:

```python
# Path notation (concise)
db_host = config.resolve("project::database::host")
username = config.resolve("project::database::credentials::username")

# Standard dict access (also works)
db_host = config.resolve("project")["database"]["host"]
username = config["project"]["database"]["credentials"]["username"]
```

### Lists and Arrays

```yaml
colors:
  - red
  - green
  - blue

matrix:
  - [1, 2, 3]
  - [4, 5, 6]
  - [7, 8, 9]
```

Access list elements with either syntax:

```python
# Path notation
first_color = config.resolve("colors::0")  # "red"
matrix_row = config.resolve("matrix::1")  # [4, 5, 6]

# Standard list access
first_color = config["colors"][0]  # "red"
matrix_row = config["matrix"][1]  # [4, 5, 6]
```

## Configuration Sections

### Organizing Large Configs

Break large configurations into logical sections:

```yaml
# Application settings
app:
  name: "My App"
  version: "2.0.0"
  debug: false

# Database configuration
database:
  host: "localhost"
  port: 5432
  pool_size: 10

# Logging configuration
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  handlers:
    - console
    - file

# Training configuration
training:
  batch_size: 32
  epochs: 100
  learning_rate: 0.001
```

## Configuration Validation

### Schema Validation with Dataclasses

Sparkwheel supports automatic validation using Python dataclasses. This is the recommended approach for production code:

```python
from dataclasses import dataclass
from sparkwheel import Config

@dataclass
class AppConfig:
    name: str
    version: str
    port: int
    debug: bool = False

# Validate automatically on load
config = Config.load("config.yaml", schema=AppConfig)

# Or validate explicitly
config = Config.load("config.yaml")
config.validate(AppConfig)
```

Schema validation provides:
- **Type checking**: Ensures values have the correct types
- **Required fields**: Catches missing configuration
- **Clear errors**: Points directly to the problem with helpful messages

See the [Schema Validation Guide](schema-validation.md) for complete details.

### Manual Validation

You can also validate manually:

```python
from sparkwheel import Config

# Load config
config = Config.load("config.yaml")

# Validate required keys
required_keys = ["name", "version", "settings"]
for key in required_keys:
    if key not in config:
        raise ValueError(f"Missing required key: {key}")

# Validate by attempting resolution
try:
    resolved = config.resolve()
    print("Config resolved successfully!")
except Exception as e:
    print(f"Config validation failed: {e}")
```

## Best Practices

### 1. Use Descriptive Keys

```yaml
# Good
database_connection_pool_size: 10
max_retry_attempts: 3

# Avoid
db_pool: 10
retries: 3
```

### 2. Group Related Settings

```yaml
# Good - grouped by feature
email:
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  from_address: "noreply@example.com"

# Avoid - scattered
smtp_host: "smtp.gmail.com"
smtp_port: 587
email_from: "noreply@example.com"
```

### 3. Use Comments

```yaml
training:
  batch_size: 32  # Optimal for 16GB GPU
  learning_rate: 0.001  # Recommended by paper X

  # Experimental: improved convergence
  warmup_steps: 1000
```

### 4. Separate Environment-Specific Config

```yaml
# base_config.yaml
common:
  app_name: "My App"
  features:
    caching: true

# dev_config.yaml
environment: development
debug: true
database:
  host: "localhost"

# prod_config.yaml
environment: production
debug: false
database:
  host: "prod-db.example.com"
```

## Configuration Inheritance

Load and merge multiple config files:

```python
from sparkwheel import Config

# Method 1: Load multiple files at once
config = Config.load(["base_config.yaml", "prod_config.yaml"])

# Method 2: Load then merge
config = Config.load("base_config.yaml")
config.update("prod_config.yaml")

# Method 3: Merge Config instances
base = Config.load("base.yaml")
cli = Config.from_cli("override.yaml", ["model::lr=0.001"])
base.merge(cli)  # Merge one Config into another

# Later configs override earlier ones
resolved = config.resolve()
```

See [Composition & Operators](operators.md) for details on composition-by-default, replace (`=`), and delete (`~`) operators.

## Special Keys

Sparkwheel reserves certain keys with special meaning:

- `_target_`: Specifies a class to instantiate
- `_disabled_`: Skip instantiation if true
- `_requires_`: Dependencies that must be resolved first
- `_mode_`: Instantiation mode (default, callable, debug)

These are covered in detail in [Instantiation Guide](instantiation.md).

## Common Patterns

### Default Values

```yaml
defaults:
  timeout: 30
  retries: 3
  debug: false

# Override specific values
api:
  timeout: "@defaults::timeout"
  retries: 5  # Override default
  debug: "@defaults::debug"
```

### Feature Flags

```yaml
features:
  authentication: true
  rate_limiting: true
  caching: false
  analytics: true

# Reference in other parts
api:
  enable_auth: "@features::authentication"
  enable_cache: "@features::caching"
```

### Environment Variables

```yaml
database:
  # Use environment variable with fallback
  host: "$import os; os.getenv('DB_HOST', 'localhost')"
  port: "$import os; int(os.getenv('DB_PORT', '5432'))"
```

## Next Steps

- [References](references.md) - Link configuration values
- [Expressions](expressions.md) - Execute Python code
- [Instantiation](instantiation.md) - Create objects from config
- [Advanced Features](advanced.md) - Power user techniques
