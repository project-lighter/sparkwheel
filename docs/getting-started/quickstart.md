# Quick Start

Build a word counter from configuration, inspect its definition, then change its
input. This complete example uses only Sparkwheel and Python's standard library.
First complete [installation](installation.md) and keep that environment active.

## Your First Config

The ordinary Python version is:

```python
from collections import Counter

counts = Counter(["red", "blue", "red"])
print(dict(counts))  # {'red': 2, 'blue': 1}
```

To select the input through configuration, create a new example directory:

```bash
mkdir sparkwheel-demo
cd sparkwheel-demo
```

Create these two files in that directory.

```yaml title="config.yaml"
words: [red, blue, red]
counts:
  _target_: collections.Counter
  _args_: ["@words"]
```

```python title="run.py"
import sys
from sparkwheel import Config

config = Config().update("config.yaml")
for override in sys.argv[1:]:
    config.update(override)

print("Definition:", config.get("counts")["_target_"])
counts = config.resolve("counts")
print("Counts:", dict(counts))
```

Run from `sparkwheel-demo`:

```bash
python run.py
```

Expected output:

```text
Definition: collections.Counter
Counts: {'red': 2, 'blue': 1}
```

`_target_` names the Python class to call. `_args_` supplies positional arguments.
`@words` supplies the resolved value of the `words` node. `get()` reads the
configuration; `resolve()` constructs the counter. Nothing is written to disk by
this program.

## CLI Overrides

From the same directory, replace the input list:

```bash
python run.py '=words=[green, green, red]'
```

Expected output:

```text
Definition: collections.Counter
Counts: {'green': 2, 'red': 1}
```

The leading `=` means **replace**. Without it, list composition appends entries.
Single quotes keep the override together as one shell argument. Values are parsed
as YAML; see [CLI overrides](../user-guide/cli.md) for booleans, nulls and mappings.

## Experiment Without Copying

Create an overlay beside the other files:

```yaml title="extra.yaml"
words: [green]
```

The same program accepts a file path as well as an override:

```bash
python run.py extra.yaml
```

Expected counts are `{'red': 2, 'blue': 1, 'green': 1}`. The definition line stays
`Definition: collections.Counter`. Dictionaries merge and lists extend by default;
[composition](../user-guide/operators.md) explains how to replace or delete them.

## Next Steps

- Read the [configuration model](../user-guide/basics.md) before editing objects
  after construction.
- Use [`@` and `%`](../user-guide/references.md) to choose shared objects versus
  copied definitions.
- Replace the standard-library target with [your own Python class](../user-guide/instantiation.md).
- If a command fails, start with [troubleshooting](../user-guide/troubleshooting.md).
