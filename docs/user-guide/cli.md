# CLI Overrides

Sparkwheel accepts input strings; your application owns its command line. The
[quick-start program](../getting-started/quickstart.md) is a complete working CLI.
Its integration is simply:

```python
for value in sys.argv[1:]:
    config.update(value)
```

This fragment belongs after creating the config and loading the base file.
It supports file overlays and overrides in their supplied order. Use argparse,
Click or another CLI library when the application needs its own options; pass
only the configuration inputs to `update()`.

## Auto-Detection Pattern

- A string containing `=` is parsed as an override.
- A string beginning with `~` is a delete override, even without `=`.
- Other strings are file paths.

There is no `--key value` configuration syntax. A filename containing `=` or
starting with `~` is ambiguous as a string; pass a `pathlib.Path` when loading it
through Python.

## Override Syntax

| Input | Meaning |
|---|---|
| `report::title=Example` | Set a nested value |
| `words=[green]` | Append to an existing list |
| `=words=[green]` | Replace the list |
| `=report={title: Example}` | Replace the whole mapping |
| `~report::limit` | Delete one key |
| `~words::0` | Delete one list entry |

Quote complete overrides containing spaces or shell punctuation. From the
quick-start directory, these are complete commands:

```bash
python run.py 'words=[green]'
python run.py '=words=[green, green]'
```

Their counts are respectively `{'red': 2, 'blue': 1, 'green': 1}` and
`{'green': 2}`. In both cases the program also prints the unchanged target name.

## Value Types

Override values use **YAML parsing**, not Python `ast.literal_eval`:

| Input value | Parsed value |
|---|---|
| `3`, `0.5` | Integer, float |
| `true`, `false` | Boolean |
| `yes`, `no`, `on`, `off` | Boolean under the current YAML parser |
| `null`, `~` | `None` |
| `[red, blue]` | List of strings |
| `{limit: 3}` | Dictionary |
| `None` | The string `"None"` |

To preserve a YAML-looking value as text, preserve the inner quotes through the
shell: `config.update('label="true"')` stores a string. The equivalent shell
argument is `'label="true"'`. Shell quoting and YAML quoting solve different
problems: the outer quotes keep one argument; the inner quotes control its type.

## Advanced: Manual Override Parsing

Use `parse_overrides()` when parsing and application must be separate:

```python
from sparkwheel import Config, parse_overrides

overrides = parse_overrides(["limit=3", "enabled=true", "=words=[blue]", "~old"])
assert overrides == {"limit": 3, "enabled": True, "=words": ["blue"], "~old": None}
config = Config().update({"old": 1, "words": ["red"]})
config.update(overrides)
assert config.get("words") == ["blue"]
assert config.get("old") is None
```

The parser handles overrides, not filenames. Avoid maintaining a second parser
with different boolean, null or operator rules.

## Schema Validation

A schema-enabled config validates each complete `update()` transaction. Deferred
references and expressions are checked when resolved. Compose a complete initial
mapping when required fields are needed together; see
[validation timing](schema-validation.md#validation-timing).

## Next Steps

[Composition](operators.md) · [Troubleshooting](troubleshooting.md) ·
[Quick reference](quick-reference.md)
