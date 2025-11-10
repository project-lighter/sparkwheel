# Configuration Diffing

Compare configurations to understand what changed between versions, experiments, or environments.

## Basic Usage

```python
from sparkwheel import diff_configs, format_diff_tree

# Compare two config files
diff = diff_configs("config_v1.yaml", "config_v2.yaml")

# Check if there are differences
if diff.has_changes():
    print(f"Changes detected: {diff.summary()}")
    print(format_diff_tree(diff))
else:
    print("Configs are identical")
```

## Output Formats

Sparkwheel provides three output formats for diffs:

### Tree Format (Default)

Human-readable tree structure showing changes by section:

```python
from sparkwheel import format_diff_tree

output = format_diff_tree(diff, name1="v1.yaml", name2="v2.yaml")
print(output)
```

Output:

```
Configuration Diff: v1.yaml → v2.yaml

model
  ✗ hidden_size: 512 → 1024
  + dropout: 0.1 (added)
  - old_param: 123 (removed)

optimizer
  ✗ lr: 0.001 → 0.01

Summary:
  2 changed, 1 added, 1 removed
```

### Unified Format (Git-style)

Git-style unified diff format:

```python
from sparkwheel import format_diff_unified

output = format_diff_unified(diff, name1="v1.yaml", name2="v2.yaml")
print(output)
```

Output:

```
--- v1.yaml
+++ v2.yaml
@@ model @@
- hidden_size: 512
+ hidden_size: 1024
+ dropout: 0.1
- old_param: 123

@@ optimizer @@
- lr: 0.001
+ lr: 0.01
```

### JSON Format (Machine-readable)

JSON format for programmatic processing:

```python
from sparkwheel import format_diff_json
import json

output = format_diff_json(diff)
parsed = json.loads(output)

print(parsed["summary"])  # "2 changed, 1 added, 1 removed"
print(parsed["added"])    # {"model::dropout": 0.1}
print(parsed["changed"])  # {"model::hidden_size": {"old": 512, "new": 1024}, ...}
```

## Semantic Diff

Compare configs based on their resolved values, not syntax:

```yaml
# config1.yaml
base_lr: 0.001
model:
  lr: "@base_lr"

# config2.yaml
model:
  lr: 0.001
```

```python
from sparkwheel import diff_configs

# Syntactic diff - shows differences in syntax
diff_syntax = diff_configs("config1.yaml", "config2.yaml", resolve=False)
print(diff_syntax.has_changes())  # True - different syntax

# Semantic diff - compares resolved values
diff_semantic = diff_configs("config1.yaml", "config2.yaml", resolve=True)
print(diff_semantic.has_changes())  # False - same resolved values!
```

This is useful for:
- **Refactoring**: Verify that refactored configs produce the same result
- **Expressions**: Compare configs using different expressions that evaluate to the same value
- **References**: Check if different reference structures resolve to the same values

### Example: Expression Equivalence

```yaml
# config1.yaml
model:
  size: "$256 * 2"

# config2.yaml
model:
  size: 512
```

```python
diff = diff_configs("config1.yaml", "config2.yaml", resolve=True)
assert not diff.has_changes()  # Both resolve to 512
```

## Ignoring Keys

Ignore certain keys when comparing (useful for metadata):

```python
diff = diff_configs(
    "config_v1.yaml",
    "config_v2.yaml",
    ignore_keys=["timestamp", "version", "metadata"]
)
```

## Comparing Dicts

Compare configuration dictionaries directly:

```python
config1 = {
    "model": {"hidden_size": 512, "dropout": 0.1},
    "training": {"lr": 0.001}
}

config2 = {
    "model": {"hidden_size": 1024, "dropout": 0.1},
    "training": {"lr": 0.001, "epochs": 100}
}

diff = diff_configs(config1, config2)
print(diff.summary())  # "1 changed, 1 added"
```

## ConfigDiff Object

The `diff_configs()` function returns a `ConfigDiff` object:

```python
from sparkwheel import diff_configs

diff = diff_configs("v1.yaml", "v2.yaml")

# Access individual changes
print(diff.added)      # Dict of added keys
print(diff.removed)    # Dict of removed keys
print(diff.changed)    # Dict of changed keys (key -> (old, new))
print(diff.unchanged)  # Dict of unchanged keys

# Summary methods
print(diff.has_changes())  # bool
print(diff.summary())      # Human-readable summary string
```

## Practical Examples

### Track Experiment Changes

```python
from sparkwheel import diff_configs, format_diff_tree

# Compare current experiment to baseline
diff = diff_configs("experiments/baseline.yaml", "experiments/exp_042.yaml")

if diff.has_changes():
    print("Experiment changes from baseline:")
    print(format_diff_tree(diff))

    # Log to experiment tracking
    log_experiment_diff(diff)
```

### Verify Production Config

```python
from sparkwheel import diff_configs, format_diff_unified

# Compare staging to production
diff = diff_configs(
    "environments/staging.yaml",
    "environments/production.yaml"
)

if diff.has_changes():
    print("WARNING: Production differs from staging!")
    print(format_diff_unified(diff))

    # Require confirmation
    confirm = input("Deploy anyway? (yes/no): ")
    if confirm.lower() != "yes":
        exit(1)
```

### Pre-commit Hook

```python
#!/usr/bin/env python
# .git/hooks/pre-commit

from sparkwheel import diff_configs, format_diff_tree
import sys

# Check if critical config changed
diff = diff_configs(
    "configs/production.yaml",  # HEAD version
    "configs/production.yaml.new"  # Staged version
)

# Check for critical changes
critical_keys = ["database::host", "api::secret_key", "security"]
critical_changes = [
    key for key in diff.changed.keys()
    if any(critical in key for critical in critical_keys)
]

if critical_changes:
    print("ERROR: Critical production config changes detected!")
    print(format_diff_tree(diff))
    print("\nCritical keys changed:", critical_changes)
    print("Please review carefully and use --no-verify if intentional.")
    sys.exit(1)
```

### Config Migration Tool

```python
from sparkwheel import diff_configs, format_diff_json
import json

def migrate_config(old_path, new_path, migration_log_path):
    """Migrate config and log changes."""
    diff = diff_configs(old_path, new_path)

    # Save migration log
    with open(migration_log_path, 'w') as f:
        f.write(format_diff_json(diff))

    # Generate migration report
    print(f"Migration complete!")
    print(f"  Added: {len(diff.added)} keys")
    print(f"  Removed: {len(diff.removed)} keys")
    print(f"  Changed: {len(diff.changed)} keys")

    # Warn about removed keys
    if diff.removed:
        print("\nWARNING: The following keys were removed:")
        for key in diff.removed:
            print(f"  - {key}")

migrate_config("config_v1.yaml", "config_v2.yaml", "migration.json")
```

### Regression Testing

```python
from sparkwheel import diff_configs

def test_config_stability():
    """Ensure config refactoring doesn't change resolved values."""
    # Compare old and new config implementations
    diff = diff_configs(
        "configs/old_structure.yaml",
        "configs/new_structure.yaml",
        resolve=True  # Semantic comparison
    )

    # Should have no differences after resolution
    assert not diff.has_changes(), (
        f"Config refactoring changed resolved values!\n"
        f"Changes: {diff.summary()}"
    )
```

### CI/CD Pipeline

```yaml
# .github/workflows/config-check.yml
name: Config Check

on: [pull_request]

jobs:
  check-config:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Check config changes
        run: |
          python scripts/check_config_diff.py \
            --base origin/main \
            --head HEAD \
            --critical-keys database,secrets,api
```

```python
# scripts/check_config_diff.py
import argparse
from sparkwheel import diff_configs, format_diff_tree

parser = argparse.ArgumentParser()
parser.add_argument("--base", required=True)
parser.add_argument("--head", required=True)
parser.add_argument("--critical-keys", required=True)
args = parser.parse_args()

# Get configs from git
# ... (implementation details)

diff = diff_configs(base_config, head_config)

# Check for critical changes
critical = args.critical_keys.split(",")
has_critical = any(
    any(key in change for key in critical)
    for change in diff.changed.keys()
)

if has_critical:
    print("⚠️  Critical configuration changes detected!")
    print(format_diff_tree(diff))
    exit(1)

print("✓ No critical config changes")
```

## Show Unchanged Keys

Display unchanged keys in tree format:

```python
output = format_diff_tree(diff, show_unchanged=True)
```

Output:

```
Configuration Diff: v1.yaml → v2.yaml

model
  ✓ _target_: "torch.nn.Linear" (unchanged)
  ✗ hidden_size: 512 → 1024
  ✓ activation: "relu" (unchanged)

Summary:
  1 changed
```

## Best Practices

### 1. Use Semantic Diff for Refactoring

When refactoring configs, use semantic diff to ensure equivalent behavior:

```python
# Verify refactoring didn't change behavior
diff = diff_configs("old.yaml", "new.yaml", resolve=True)
assert not diff.has_changes(), "Refactoring changed behavior!"
```

### 2. Ignore Metadata

Always ignore metadata fields when comparing:

```python
diff = diff_configs(
    "config1.yaml",
    "config2.yaml",
    ignore_keys=["_metadata_", "timestamp", "version", "user", "hostname"]
)
```

### 3. Review Diffs Before Deployment

Always review config diffs before deploying:

```python
def deploy(env):
    current = load_current_config(env)
    new = load_new_config(env)

    diff = diff_configs(current, new)

    if diff.has_changes():
        print(format_diff_unified(diff))
        confirm = input(f"Deploy to {env}? (yes/no): ")
        if confirm != "yes":
            return

    perform_deployment(env, new)
```

### 4. Track Config History

Save config diffs in version control:

```python
from sparkwheel import diff_configs, format_diff_json
from datetime import datetime

# Compare to previous version
diff = diff_configs("v1.yaml", "v2.yaml")

# Save diff log
timestamp = datetime.now().isoformat()
with open(f"config_diffs/{timestamp}.json", "w") as f:
    f.write(format_diff_json(diff))
```

## Next Steps

- [Validation](validation.md) - Check configs for errors
- [Merging Guide](merging.md) - Learn about config merging
- [CLI Overrides](cli.md) - Override configs from command line
- [Advanced Features](advanced.md) - Power user techniques
