# Expressions

Execute Python code directly in your configuration files using the `$` prefix.

## Basic Expressions

```yaml
# Simple math
result: "$2 + 2"  # 4
square: "$10 ** 2"  # 100

# String operations
message: "$'Hello, ' + 'World!'"

# Lists
numbers: "$[1, 2, 3, 4, 5]"
squares: "$[x**2 for x in range(5)]"
```

## Combining with References

Expressions can use references:

```yaml
training:
  batch_size: 32
  total_samples: 10000
  steps_per_epoch: "$@training::total_samples // @training::batch_size"
```

## Importing Modules

Import Python libraries in expressions:

```yaml
# Math operations
pi: "$import math; math.pi"
sqrt_2: "$import math; math.sqrt(2)"

# Check for GPU
device: "$import torch; 'cuda' if torch.cuda.is_available() else 'cpu'"

# Get environment variable
db_host: "$import os; os.getenv('DB_HOST', 'localhost')"
```

## Complex Expressions

### Multi-line Logic

```yaml
learning_rate: "$
  0.001 if @training::batch_size < 64
  else 0.0001 if @training::batch_size < 128
  else 0.00001
"
```

### List Comprehensions

```yaml
# Generate range
values: "$list(range(10))"

# Transform data
scaled: "$[x / 255.0 for x in @raw_values]"

# Filter
evens: "$[x for x in @numbers if x % 2 == 0]"
```

### Function Definitions

```yaml
# Define and call function
processed: "$
  (lambda x: x ** 2 + 2 * x + 1)(@input_value)
"
```

## Calling Object Methods

Reference object methods when instantiation is involved:

```yaml
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10

optimizer:
  _target_: torch.optim.Adam
  lr: 0.001
  params: "$@model.parameters()"  # Call model's parameters() method
```

## Expression Scope

### Global Scope

Imports are added to global scope:

```yaml
setup: "$import numpy as np"  # np is now available globally

data:
  array: "$np.array([1, 2, 3])"  # Can use np here
```

### Local Variables

Access config values as variables:

```yaml
value_a: 10
value_b: 20
sum: "$value_a + value_b"  # Error: use @value_a instead
```

Use references (`@`) to access config values.

## Common Patterns

### Environment Detection

```yaml
config:
  is_production: "$import os; os.getenv('ENV') == 'production'"
  debug: "$not @config::is_production"
```

### Conditional Paths

```yaml
paths:
  base: "/data"
  train: "$@paths::base + '/train' if @mode == 'train' else @paths::base + '/val'"
```

### Dynamic Imports

```yaml
backend: "torch"

tensor_fn: "$
  __import__('torch').tensor if @backend == 'torch'
  else __import__('tensorflow').constant
"
```

### Calculate Derived Values

```yaml
model:
  input_shape: [3, 224, 224]
  input_size: "$@model::input_shape[0] * @model::input_shape[1] * @model::input_shape[2]"
```

## Error Handling

### Syntax Errors

```yaml
# Bad: Python syntax error
result: "$2 +"  # SyntaxError
```

### Runtime Errors

```yaml
# Bad: NameError
result: "$undefined_variable"  # Will raise error

# Good: Use references
value: 10
result: "$@value * 2"
```

### Safe Evaluation

Check before using:

```yaml
# Check if module exists
has_torch: "$
  try:
      import torch
      True
  except ImportError:
      False
"

device: "$'cuda' if @has_torch and torch.cuda.is_available() else 'cpu'"
```

## Best Practices

### 1. Keep Expressions Simple

```yaml
# Good
steps: "$@samples // @batch_size"

# Avoid
steps: "$
  sum([1 for _ in range(@samples)]) //
  (lambda x: x if x > 0 else 1)(@batch_size)
"
```

### 2. Use Comments

```yaml
# Calculate learning rate based on batch size
# Formula from paper: lr = base_lr * sqrt(batch_size)
learning_rate: "$0.001 * (@training::batch_size ** 0.5)"
```

### 3. Validate Expressions

```python
# In your Python code
from sparkwheel import ConfigParser

parser = ConfigParser()
try:
    config = parser.read_config("config.yaml")
except SyntaxError as e:
    print(f"Expression syntax error: {e}")
except Exception as e:
    print(f"Expression evaluation error: {e}")
```

## Security Considerations

!!! warning "Expression Safety"
    Expressions execute arbitrary Python code. Only load configurations from trusted sources.

    ```yaml
    # Dangerous if config is from untrusted source!
    dangerous: "$__import__('os').system('rm -rf /')"
    ```

    Always validate configuration sources in production.

## Next Steps

- [Instantiation](instantiation.md) - Create objects with expressions
- [Advanced Features](advanced.md) - Complex expression patterns
- [Examples](../examples/deep-learning.md) - Real-world expression usage
