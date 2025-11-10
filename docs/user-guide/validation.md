# Configuration Validation

Validate your configurations to catch errors before runtime.

## Basic Usage

```python
from sparkwheel import check_config, format_check_result

# Check a config file
result = check_config("config.yaml")

if result.is_valid:
    print("✓ Config is valid!")
else:
    print(format_check_result(result))
```

## What Gets Checked

Sparkwheel performs comprehensive validation:

1. **YAML Syntax** - Valid YAML structure
2. **Reference Resolution** - All `@references` can be resolved
3. **Circular Dependencies** - No circular reference chains
4. **Expression Evaluation** - All `$expressions` are valid Python
5. **Component Instantiation** - All `_target_` references are valid

## CheckResult Object

The `check_config()` function returns a `CheckResult` object:

```python
result = check_config("config.yaml")

# Validation status
print(result.is_valid)  # bool

# Error and warning lists
print(result.errors)    # List of error messages
print(result.warnings)  # List of warning messages

# Statistics
print(result.num_references)   # Number of @references found
print(result.num_expressions)  # Number of $expressions found
print(result.num_components)   # Number of components (_target_)

# Config IDs
print(result.config_ids)  # List of all config IDs

# Summary
print(result.summary())  # Human-readable summary
```

## Output Formatting

### format_check_result()

Human-readable formatted output:

```python
from sparkwheel import check_config, format_check_result

result = check_config("config.yaml")
print(format_check_result(result, verbose=True))
```

Output:

```
✓ Checking config.yaml

  ✓ YAML syntax valid
  ✓ All references resolved (12 references)
  ✓ No circular dependencies
  ✓ All expressions valid (5 expressions)
  ✓ No instantiation errors (3 components)

Check passed!
```

With errors:

```
✗ Checking config.yaml

  ✓ YAML syntax valid
  ✗ Reference resolution failed (2 errors)
      Reference resolution failed: Config ID 'nonexistent' not found
      Reference resolution failed: Config ID 'model::invalid' not found
  ✓ No circular dependencies
  ✓ All expressions valid

Check failed: 2 errors
```

## Strict Mode

In strict mode, warnings are treated as errors:

```python
# Default: warnings are warnings
result = check_config("config.yaml", strict=False)
if result.warnings:
    print("Warnings:", result.warnings)

# Strict: warnings become errors
result = check_config("config.yaml", strict=True)
if not result.is_valid:
    print("Validation failed!")
```

Use strict mode for:
- **Production configs** - No warnings allowed
- **CI/CD pipelines** - Fail fast on any issues
- **Critical systems** - Maximum validation

## Check Specific Paths

Validate only a specific section of the config:

```python
# Check only the model section
result = check_config("config.yaml", check_path="model")

# Check nested section
result = check_config("config.yaml", check_path="training::optimizer")
```

This is useful for:
- **Partial validation** - Only check what you're using
- **Performance** - Faster checks for large configs
- **Modular testing** - Test individual components

## List Config IDs

Get a list of all configuration IDs:

```python
from sparkwheel import list_config_ids, format_config_ids

# Get grouped IDs (dict by section)
ids = list_config_ids("config.yaml", group_by_section=True)

# Get flat list
ids = list_config_ids("config.yaml", group_by_section=False)

# Format for display
print(format_config_ids(ids))
```

Output:

```
Configuration IDs in config.yaml:

model
  model::hidden_size
  model::num_layers
  model::activation

training
  training::lr
  training::epochs
  training::batch_size

Total: 7 configuration items
```

## Common Validation Errors

### Missing References

```yaml
# config.yaml
model:
  lr: "@nonexistent_lr"
```

```python
result = check_config("config.yaml")
# Error: Reference resolution failed: Config ID 'nonexistent_lr' not found
```

### Circular References

```yaml
# config.yaml
a: "@b"
b: "@c"
c: "@a"
```

```python
result = check_config("config.yaml")
# Warning: Circular reference detected
```

### Invalid Expressions

```yaml
# config.yaml
model:
  size: "$undefined_variable"
```

```python
result = check_config("config.yaml")
# Error: Expression evaluation failed: name 'undefined_variable' is not defined
```

### Invalid YAML

```yaml
# config.yaml
model:
  layers: [1, 2, 3  # Missing closing bracket
```

```python
result = check_config("config.yaml")
# Error: YAML syntax error: ...
```

## Practical Examples

### Pre-commit Hook

```python
#!/usr/bin/env python
# .git/hooks/pre-commit

from sparkwheel import check_config, format_check_result
import sys
import glob

# Check all config files
config_files = glob.glob("configs/**/*.yaml", recursive=True)

failed = []
for config_file in config_files:
    result = check_config(config_file, strict=True)
    if not result.is_valid:
        failed.append((config_file, result))

if failed:
    print("❌ Config validation failed!\n")
    for config_file, result in failed:
        print(format_check_result(result, filepath=config_file))
        print()
    sys.exit(1)

print("✓ All configs valid")
```

### CI/CD Pipeline

```yaml
# .github/workflows/validate.yml
name: Validate Configs

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Validate configs
        run: |
          python scripts/validate_all_configs.py
```

```python
# scripts/validate_all_configs.py
from sparkwheel import check_config
import sys
from pathlib import Path

configs = Path("configs").rglob("*.yaml")
failed = []

for config_file in configs:
    result = check_config(str(config_file), strict=True)
    if not result.is_valid:
        failed.append(config_file)
        print(f"✗ {config_file}")
        for error in result.errors:
            print(f"    {error}")
    else:
        print(f"✓ {config_file}")

if failed:
    print(f"\n❌ {len(failed)} config(s) failed validation")
    sys.exit(1)

print(f"\n✓ All configs valid")
```

### Runtime Validation

```python
from sparkwheel import ConfigParser, check_config

def load_validated_config(path):
    """Load config with validation."""
    # Check first
    result = check_config(path, strict=True)

    if not result.is_valid:
        raise ValueError(f"Invalid config: {result.summary()}")

    # Load if valid
    return ConfigParser.load(path)

# Usage
try:
    parser = load_validated_config("config.yaml")
except ValueError as e:
    print(f"Config validation failed: {e}")
    exit(1)
```

### Validate After CLI Overrides

```python
from sparkwheel import ConfigParser, parse_args, check_config
import sys

# Load base config
parser = ConfigParser.load("config.yaml")

# Apply CLI overrides
cli_overrides = parse_args(sys.argv[1:])
parser.update(cli_overrides)

# Validate final config
result = check_config(parser.config)

if not result.is_valid:
    print("Error: Config invalid after CLI overrides!")
    print(format_check_result(result))
    for error in result.errors:
        print(f"  - {error}")
    sys.exit(1)

# Proceed with validated config
config = parser.resolve()
```

### Validate Before Deployment

```python
from sparkwheel import check_config, format_check_result

def validate_for_deployment(env):
    """Validate config before deployment."""
    config_path = f"environments/{env}.yaml"

    # Strict validation for production
    strict = (env == "production")
    result = check_config(config_path, strict=strict)

    if not result.is_valid:
        print(f"❌ {env} config validation failed!")
        print(format_check_result(result, filepath=config_path, verbose=True))
        return False

    print(f"✓ {env} config is valid")
    print(f"  - {result.num_references} references")
    print(f"  - {result.num_expressions} expressions")
    print(f"  - {result.num_components} components")
    return True

# Check before deploy
if not validate_for_deployment("production"):
    print("Aborting deployment")
    exit(1)
```

### Config Test Suite

```python
# tests/test_configs.py
import pytest
from sparkwheel import check_config
from pathlib import Path

# Get all config files
CONFIG_DIR = Path("configs")
CONFIG_FILES = list(CONFIG_DIR.rglob("*.yaml"))

@pytest.mark.parametrize("config_file", CONFIG_FILES)
def test_config_valid(config_file):
    """Test that all config files are valid."""
    result = check_config(str(config_file), strict=True)
    assert result.is_valid, f"Config validation failed:\n{result.summary()}"

@pytest.mark.parametrize("config_file", CONFIG_FILES)
def test_no_circular_dependencies(config_file):
    """Test that no configs have circular dependencies."""
    result = check_config(str(config_file))
    circular_warnings = [w for w in result.warnings if "circular" in w.lower()]
    assert not circular_warnings, f"Circular dependencies found: {circular_warnings}"

def test_production_config_strict():
    """Production config must pass strict validation."""
    result = check_config("environments/production.yaml", strict=True)
    assert result.is_valid, "Production config failed strict validation"
```

### Bulk Validation Report

```python
from sparkwheel import check_config
from pathlib import Path
import json

def validate_all_configs(config_dir):
    """Generate validation report for all configs."""
    results = {}

    for config_file in Path(config_dir).rglob("*.yaml"):
        result = check_config(str(config_file))
        results[str(config_file)] = {
            "valid": result.is_valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "references": result.num_references,
            "expressions": result.num_expressions,
            "components": result.num_components,
        }

    # Save report
    with open("validation_report.json", "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    total = len(results)
    valid = sum(1 for r in results.values() if r["valid"])
    print(f"Validation Report: {valid}/{total} configs valid")

    return all(r["valid"] for r in results.values())

if __name__ == "__main__":
    success = validate_all_configs("configs")
    exit(0 if success else 1)
```

## Best Practices

### 1. Validate in CI/CD

Always validate configs in your CI/CD pipeline:

```yaml
# .github/workflows/ci.yml
- name: Validate configs
  run: python -m sparkwheel.check configs/**/*.yaml
```

### 2. Use Strict Mode for Production

Production configs should have zero tolerance for issues:

```python
result = check_config("production.yaml", strict=True)
assert result.is_valid, "Production config must be perfect"
```

### 3. Validate After Modifications

Check config validity after programmatic modifications:

```python
parser = ConfigParser.load("base.yaml")
parser.update({"model::hidden_size": 2048})

# Validate changes
result = check_config(parser.config)
assert result.is_valid, "Modifications broke config"
```

### 4. Document Validation Requirements

Add validation requirements to your docs:

```python
"""
Configuration Requirements:
- All configs must pass check_config() validation
- Production configs must pass strict=True validation
- No circular dependencies allowed
- All references must resolve
- All expressions must be valid Python
"""
```

### 5. Provide Helpful Error Messages

When validation fails, show helpful output:

```python
result = check_config("config.yaml")
if not result.is_valid:
    print("Config validation failed!")
    print(format_check_result(result, verbose=True))
    print("\nPlease fix the errors above and try again.")
    exit(1)
```

## Integration with Other Tools

### pytest

```python
@pytest.fixture
def validated_config():
    """Fixture that provides validated config."""
    result = check_config("test_config.yaml")
    assert result.is_valid
    return ConfigParser.load("test_config.yaml")

def test_model(validated_config):
    model = validated_config.resolve("model")
    assert model is not None
```

### Click CLI

```python
import click
from sparkwheel import check_config, format_check_result

@click.command()
@click.argument("config_file")
@click.option("--strict", is_flag=True)
def validate(config_file, strict):
    """Validate a configuration file."""
    result = check_config(config_file, strict=strict)

    click.echo(format_check_result(result, filepath=config_file, verbose=True))

    if not result.is_valid:
        raise click.ClickException("Validation failed")

    click.echo("✓ Config is valid")

if __name__ == "__main__":
    validate()
```

## Next Steps

- [Merging Guide](merging.md) - Learn about config merging
- [CLI Overrides](cli.md) - Override configs from command line
- [Config Diffing](diffing.md) - Compare configurations
- [Advanced Features](advanced.md) - Power user techniques
