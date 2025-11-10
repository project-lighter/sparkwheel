# CLI Overrides

Override configuration parameters from the command line without modifying config files.

## Basic Usage

```python
# main.py
from sparkwheel import ConfigParser, parse_args
import sys

# Load base config
parser = ConfigParser.load("config.yaml")

# Parse command-line arguments
cli_overrides = parse_args(sys.argv[1:])

# Apply overrides
parser.update(cli_overrides)

# Now use the config
model = parser.resolve("model")
```

Run with overrides:

```bash
python main.py model.lr=0.01 training.batch_size=64
```

## Automatic Type Inference

Sparkwheel automatically detects the type of each CLI argument:

### Numbers

```bash
# Integers
python main.py epochs=100 seed=42

# Floats
python main.py learning_rate=0.001 dropout=0.5

# Scientific notation
python main.py lr=1e-4 weight_decay=1e-5
```

### Booleans

```bash
# True values
python main.py debug=true use_gpu=True enabled=yes

# False values
python main.py debug=false use_gpu=False enabled=no

# Case insensitive
python main.py DEBUG=True UsE_GpU=FALSE
```

### Strings

```bash
# Simple strings (no quotes needed)
python main.py name=experiment_1 device=cuda

# Strings with spaces (use quotes)
python main.py name="My Experiment" description="Initial run"

# Strings that look like other types (use quotes)
python main.py version="1.0" label="true"
```

### Lists

```bash
# Number lists
python main.py layers=[64,128,256] shape=[224,224]

# String lists
python main.py devices=["cuda:0","cuda:1"] files=["a.txt","b.txt"]

# Mixed lists
python main.py mixed=[1,"two",3.0,true]

# Nested lists
python main.py matrix=[[1,2],[3,4]]
```

### Dictionaries

```bash
# Simple dicts (unquoted keys allowed)
python main.py optimizer={lr:0.01,momentum:0.9}

# Quoted keys (standard JSON)
python main.py optimizer={"lr":0.01,"momentum":0.9}

# Nested dicts
python main.py model={layers:3,config:{hidden:512,dropout:0.1}}

# Dict with various types
python main.py settings={debug:true,timeout:30,name:"test"}
```

### Null Values

```bash
# Null/None
python main.py optional_param=null cleanup=none
```

## Nested Keys

Use `.` or `::` to set nested config values:

```bash
# These are equivalent:
python main.py model.optimizer.lr=0.01
python main.py model::optimizer::lr=0.01
```

```python
# In your config:
{
  "model": {
    "optimizer": {
      "lr": 0.01  # <- Set by CLI
    }
  }
}
```

## Merge and Delete Directives

### Merge Directive (`+`)

Merge into existing dict instead of replacing:

```bash
# Without +: replaces entire optimizer dict
python main.py optimizer={lr:0.01}

# With +: merges into optimizer, preserving other keys
python main.py +optimizer={lr:0.01}
```

```python
# config.yaml
optimizer:
  type: "adam"
  lr: 0.001
  betas: [0.9, 0.999]

# After: python main.py +optimizer={lr:0.01}
# optimizer:
#   type: "adam"      (preserved)
#   lr: 0.01          (updated)
#   betas: [0.9, 0.999]  (preserved)
```

**Note:** The `+` directive validates that the key exists and types match (both dicts or both lists for list appending). This catches configuration errors early. See [Merging Guide](merging.md) for list merging examples.

### Delete Directive (`~`)

Remove a configuration key:

```bash
# Delete a key
python main.py ~model.dropout

# Delete multiple keys
python main.py ~model.dropout ~training.debug_mode
```

**Note:** The `~` directive validates that the key exists before deletion. If you try to delete a non-existent key, you'll get an error with a helpful suggestion. This catches typos and config ordering issues early.

## Complete Example

```python
# train.py
from sparkwheel import ConfigParser, parse_args
import sys

def main():
    # Load base config
    parser = ConfigParser.load("configs/base.yaml")

    # Parse CLI overrides
    cli_args = parse_args(sys.argv[1:])

    # Apply overrides
    parser.update(cli_args)

    # Resolve and use config
    config = parser.resolve()

    # Your training code here
    print(f"Training with config: {config}")
    train(config)

if __name__ == "__main__":
    main()
```

Usage examples:

```bash
# Basic override
python train.py model.hidden_size=1024

# Multiple overrides
python train.py model.hidden_size=1024 training.lr=0.01 training.epochs=100

# Complex overrides
python train.py \
  model.layers=[512,512,256] \
  optimizer={type:"sgd",lr:0.1,momentum:0.9} \
  training.batch_size=128

# Merge into existing dict
python train.py +optimizer={lr:0.01}

# Remove keys
python train.py ~model.dropout ~training.debug

# Mix and match
python train.py \
  +model={hidden_size:1024} \
  training.lr=0.001 \
  ~training.old_param
```

## Advanced Patterns

### Experiment Launcher

```python
# experiment.py
from sparkwheel import ConfigParser, parse_args
import sys

def run_experiment(name, **overrides):
    # Load experiment config
    parser = ConfigParser.load(f"experiments/{name}.yaml")

    # Apply programmatic overrides
    parser.update(overrides)

    # Apply CLI overrides
    if len(sys.argv) > 2:
        cli_overrides = parse_args(sys.argv[2:])
        parser.update(cli_overrides)

    config = parser.resolve()
    # Run experiment...

if __name__ == "__main__":
    exp_name = sys.argv[1]
    run_experiment(exp_name)
```

```bash
# Run with name and CLI overrides
python experiment.py resnet50 model.depth=101 training.lr=0.01
```

### Grid Search

```python
# grid_search.py
from sparkwheel import ConfigParser, parse_args
from itertools import product

def grid_search():
    parser = ConfigParser.load("config.yaml")

    # Define grid
    lrs = [0.001, 0.01, 0.1]
    batch_sizes = [32, 64, 128]

    for lr, bs in product(lrs, batch_sizes):
        # Clone parser for each run
        run_parser = ConfigParser.load(parser.config)
        run_parser.update({
            "training::lr": lr,
            "training::batch_size": bs
        })

        # Apply any CLI overrides
        cli_overrides = parse_args(sys.argv[1:])
        run_parser.update(cli_overrides)

        config = run_parser.resolve()
        train(config)

# Allow CLI to override grid search params
grid_search()
```

```bash
python grid_search.py model.hidden_size=512  # Applies to all runs
```

### Config Inheritance

```python
# inherit.py
from sparkwheel import ConfigParser, parse_args
import sys

def load_with_inheritance(base_name, *override_names):
    # Load base
    configs = [f"configs/{base_name}.yaml"]

    # Add override configs
    configs.extend(f"configs/{name}.yaml" for name in override_names)

    parser = ConfigParser.load(configs)

    # Apply CLI overrides
    cli_overrides = parse_args(sys.argv[1:])
    parser.update(cli_overrides)

    return parser

if __name__ == "__main__":
    parser = load_with_inheritance("base", "large_model", "gpu_settings")
```

```bash
python inherit.py training.epochs=200 +model={layers:6}
```

## Type Inference Rules

Sparkwheel uses the following rules for type inference (in order):

1. **JSON parsing**: Try to parse as JSON
2. **Dict with unquoted keys**: Fix syntax like `{a:1}` → `{"a":1}` and parse
3. **Boolean keywords**: `true`, `false`, `yes`, `no` (case insensitive)
4. **Null keywords**: `null`, `none` (case insensitive)
5. **String**: If all else fails, treat as string

### Edge Cases

```bash
# These are parsed as expected:
python main.py value=123           # int: 123
python main.py value=1.23          # float: 1.23
python main.py value=true          # bool: True
python main.py value="true"        # str: "true"
python main.py value=[1,2,3]       # list: [1, 2, 3]
python main.py value={a:1}         # dict: {"a": 1}

# Special cases:
python main.py value=             # str: "" (empty string)
python main.py value==            # str: "=" (literal =)
python main.py value="[1,2,3]"    # str: "[1,2,3]" (not parsed as list)
```

## Best Practices

### 1. Use CLI for Experiment Variations

Keep base config in files, use CLI for experiment-specific changes:

```bash
# Base experiment
python train.py

# Vary learning rate
python train.py training.lr=0.01

# Ablation study
python train.py ~model.dropout ~model.batch_norm
```

### 2. Document CLI Parameters

Add help text to your script:

```python
# train.py
"""
Train a model with the given configuration.

Common CLI overrides:
  model.hidden_size=N       - Model hidden size
  training.lr=X             - Learning rate
  training.epochs=N         - Number of epochs
  +optimizer={key:value}    - Merge optimizer settings
  ~model.dropout            - Disable dropout

Example:
  python train.py model.hidden_size=1024 training.lr=0.01
"""
```

### 3. Validate Overrides

Add validation after applying CLI overrides:

```python
from sparkwheel import ConfigParser, parse_args, check_config

parser = ConfigParser.load("config.yaml")
cli_overrides = parse_args(sys.argv[1:])
parser.update(cli_overrides)

# Validate the final config
result = check_config(parser.config)
if not result.is_valid:
    print("Invalid configuration after CLI overrides:")
    for error in result.errors:
        print(f"  - {error}")
    sys.exit(1)

config = parser.resolve()
```

### 4. Use Shell Scripts for Complex Overrides

For frequently used complex overrides:

```bash
# experiments/high_lr.sh
#!/bin/bash
python train.py \
  +optimizer={lr:0.1,momentum:0.95} \
  training.warmup_steps=1000 \
  training.epochs=200 \
  "$@"  # Pass additional args
```

```bash
./experiments/high_lr.sh model.hidden_size=512
```

## Integration with Other Tools

### Weights & Biases

```python
import wandb
from sparkwheel import ConfigParser, parse_args

parser = ConfigParser.load("config.yaml")
cli_overrides = parse_args(sys.argv[1:])
parser.update(cli_overrides)

config = parser.resolve()

# Log config to W&B
wandb.init(project="my-project", config=config)
```

### Hydra Migration

If you're migrating from Hydra, the CLI syntax is similar:

```bash
# Hydra style
python train.py model.lr=0.01 +model.dropout=0.1

# Sparkwheel (same!)
python train.py model.lr=0.01 +model.dropout=0.1
```

## Next Steps

- [Merging Guide](merging.md) - Learn about +/~ directives
- [Config Diffing](diffing.md) - Compare configurations
- [Validation](validation.md) - Check configs for errors
- [Advanced Features](advanced.md) - Power user techniques
