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
from sparkwheel import ConfigParser

# Load from file
parser = ConfigParser.load("config.yaml")
```

### Loading from Dictionary

```python
config_dict = {
    "name": "Test",
    "value": 42
}

# Load from dict
parser = ConfigParser.load(config_dict)
```

### Loading Multiple Files

```python
# Load and merge multiple config files
parser = ConfigParser.load(["base.yaml", "override.yaml"])
```

## Accessing Configuration Values

### Dictionary-style Access

```python
parser = ConfigParser.load("config.yaml")

# Direct access to raw config
name = parser["name"]
debug = parser["settings"]["debug"]
```

### Using resolve()

For resolving references and expressions, use `resolve()`:

```python
# Resolve with nested keys using :: separator
debug_mode = parser.resolve("settings::debug")

# Resolve entire config
all_config = parser.resolve()

# Resolve specific section
training_config = parser.resolve("training")
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

Access nested values:

```python
db_host = parser.resolve("project::database::host")
username = parser.resolve("project::database::credentials::username")
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

Access list elements:

```python
first_color = parser.resolve("colors::0")  # "red"
matrix_row = parser.resolve("matrix::1")  # [4, 5, 6]
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

Use `check_config()` to validate your configuration:

```python
from sparkwheel import check_config, format_check_result

# Check config file
result = check_config("config.yaml")

if result.is_valid:
    print("Config is valid!")
else:
    print(format_check_result(result))
    for error in result.errors:
        print(f"  Error: {error}")

# Or manual validation
parser = ConfigParser.load("config.yaml")
required_keys = ["name", "version", "settings"]
for key in required_keys:
    if key not in parser.config:
        raise ValueError(f"Missing required key: {key}")
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
from sparkwheel import ConfigParser

# Method 1: Load multiple files at once
parser = ConfigParser.load(["base_config.yaml", "prod_config.yaml"])

# Method 2: Load then merge
parser = ConfigParser.load("base_config.yaml")
parser.merge("prod_config.yaml")

# Later configs override earlier ones
config = parser.resolve()
```

## Special Keys

Sparkwheel reserves certain keys with special meaning:

- `_target_`: Specifies a class to instantiate
- `_args_`: Positional arguments for instantiation
- `_disabled_`: Skip instantiation if true
- `_requires_`: Dependencies that must be resolved first
- `_desc_`: Documentation string

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
