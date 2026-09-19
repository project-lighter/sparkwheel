# Composition & Operators

Use composition to change an experiment or environment without copying its whole
configuration. Apply inputs in order with `config.update(...)`.

## Composition Decision Flow

| Update | Existing value | Result |
|---|---|---|
| Ordinary key with a dictionary | Dictionary | Merge recursively |
| Ordinary key with a list | List | Append the new entries |
| Ordinary key with another value/type | Any | Replace with the new value |
| `=key` | Any | Replace the whole selected value |
| `~key: null` or CLI `~key` | Existing key/index | Delete it |
| `~key: [items]` | List or dictionary | Delete listed indices or keys |

Deleting a missing key is an error. In YAML, operators are prefixes on keys;
in Python dictionaries, quote the complete key string. Operators are not Python
assignment syntax.

## Composition by Default

This standalone example shows dictionary merging and list extension:

```python
from sparkwheel import Config

config = Config().update({
    "report": {"title": "Words", "limit": 3},
    "words": ["red", "blue"],
})
config.update({"report": {"limit": 5}, "words": ["green"]})
assert config.get("report") == {"title": "Words", "limit": 5}
assert config.get("words") == ["red", "blue", "green"]
```

Files behave the same way. The [quick start](../getting-started/quickstart.md#experiment-without-copying)
provides a complete file-overlay example.

## The `=` Operator: Explicit Replace

Continuing the example above:

```python
config.update({"=report": {"title": "New"}, "=words": ["blue"]})
assert config.get("report") == {"title": "New"}
assert config.get("words") == ["blue"]
```

Use replacement when switching a component's entire definition, clearing inherited
arguments, or replacing a list. Merely changing `_target_` in a merged mapping
leaves its other arguments in place; they may be invalid for the new target.

The YAML form is:

```yaml
=report:
  title: New
=words: [blue]
```

A leading `=` on a CLI override does the same thing:
`config.update("=words=[blue]")`. See [CLI syntax](cli.md#override-syntax).

## Editing Nested Paths

`::` paths traverse existing dictionaries and list indices. Use a top-level path
key to update a list element; a dictionary placed inside an incoming list is an
ordinary appended item, not an index-edit directive.

```python
from sparkwheel import Config

config = Config().update({"layers": [{"width": 8}, {"width": 16}]})
config.update({"layers::0::width": 4})
config.set("layers::1::width", 32)
assert config.get("layers") == [{"width": 4}, {"width": 32}]
```

The corresponding YAML overlay is `layers::0::width: 4`. Missing dictionary paths
can be created; out-of-range list indices and traversal through scalars fail.
Extend a list through ordinary composition instead of sparse assignment.

## The `~` Operator: Delete

### Delete Entire Keys

Both `config.update({"~report": None})` and `config.update("~report")` remove
`report`. The key must exist. Nested deletion uses a path such as `~report::limit`,
or a structural update such as `{"report": {"~limit": None}}`.

### Delete from Lists

Single-index deletion is supported. Batch deletion is useful when several indices
refer to the same original list:

```python
from sparkwheel import Config

config = Config().update({"words": ["red", "blue", "green", "yellow"]})
config.update("~words::1")
assert config.get("words") == ["red", "green", "yellow"]
config.update({"~words": [0, 2]})
assert config.get("words") == ["green"]
```

Negative indices are supported. A batch such as `{"~words": [0, -1]}` removes the
first and last entries of the list as it existed before that batch, without index
shift changing the meaning. Sequential calls each operate on the current list.

### Delete from Dicts

A batch on a dictionary names keys rather than indices. For example,
`{"~report": ["title", "limit"]}` deletes those two keys inside `report` while
keeping the report mapping. `{"~report": None}` deletes the entire mapping.

## Atomic Edits

An `update()` call is one source transaction. Composition, external loading or
schema failure preserves the previous source and runtime cache. Use one update
for related fields that must validate together. Successful changes start a new
resolution generation; already-returned objects remain unchanged.

Read [the configuration model](basics.md#editing-configuration) for mutation and
lifetime rules, and [troubleshooting](troubleshooting.md) for unexpected merges.
