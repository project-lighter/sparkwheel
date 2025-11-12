# References

References allow you to link configuration values together using the `@` symbol, eliminating duplication and making configs more maintainable.

## Basic References

Use `@` followed by the key path with `::` as separator:

```yaml
# config.yaml
dataset:
  path: "/data/images"
  num_classes: 10
  batch_size: 32

model:
  num_outputs: "@dataset::num_classes"

training:
  batch: "@dataset::batch_size"
```

## Reference Syntax

### Nested References

Use `::` as separator for nested keys:

```yaml
value: "@section::subsection::key"
```

### List References

Reference list elements by index:

```yaml
transforms:
  - resize
  - normalize
  - augment

# Reference by index (0-based)
first_transform: "@transforms::0"  # "resize"
last_transform: "@transforms::2"   # "augment"
```

### Nested References

References can reference other references:

```yaml
base:
  value: 100

derived:
  double: "$@base::value * 2"

final:
  quad: "$@derived::double * 2"  # Resolves to 400
```

## Reference Resolution

### Resolution Order

Sparkwheel resolves references in dependency order:

```yaml
a: 10
b: "@a"  # Resolved first
c: "$@a + @b"  # Resolved after a and b
```

### Circular References

Circular references will raise an error:

```yaml
# This will fail!
a: "@b"
b: "@a"
```

## Advanced Reference Patterns

### Conditional References

```yaml
environment: "production"

database:
  prod_host: "prod.db.example.com"
  dev_host: "localhost"
  host: "$@database::prod_host if @environment == 'production' else @database::dev_host"
```

### Dynamic References

```yaml
datasets:
  train: "/data/train"
  test: "/data/test"
  val: "/data/val"

mode: "train"
current_dataset: "$@datasets::@mode"  # Dynamically select based on mode
```

### Reference with Default

Use expressions for defaults:

```yaml
settings:
  timeout: "$@custom_timeout if '@custom_timeout' in locals() else 30"
```

## External File References (Macros)

Use `%` to reference **raw YAML values** from other files:

```yaml
# base.yaml
defaults:
  learning_rate: 0.001
  batch_size: 32

# experiment.yaml
training:
  lr: "%base.yaml::defaults::learning_rate"
  batch: "%base.yaml::defaults::batch_size"
```

**Key Distinction:**
- `@reference` - Gets the **resolved/instantiated object** from the current config
- `%file.yaml::key` - Gets the **raw YAML definition** from another file (not instantiated)

See [Advanced Features](advanced.md) for more on macros.

## Best Practices

### 1. Use References for Duplication

```yaml
# Good - single source of truth
model_config:
  hidden_size: 512

encoder:
  size: "@model_config::hidden_size"

decoder:
  size: "@model_config::hidden_size"

# Avoid - duplicated values
encoder:
  size: 512
decoder:
  size: 512
```

### 2. Name References Clearly

```yaml
# Good
num_classes: 10
model_output_size: "@num_classes"

# Less clear
classes: 10
size: "@classes"
```

### 3. Document Complex References

```yaml
dataset:
  samples: 10000
  batch_size: 32

training:
  # Calculate steps per epoch
  steps: "$@dataset::samples // @dataset::batch_size"
```

## Next Steps

- [Expressions](expressions.md) - Execute Python code in configs
- [Instantiation](instantiation.md) - Create objects with references
- [Advanced Features](advanced.md) - Complex reference patterns
