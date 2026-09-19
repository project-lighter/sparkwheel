# Configuration Basics

Sparkwheel separates the configuration you author from the objects your program
uses. Understanding that distinction makes inspection, sharing and edits predictable.

## Configuration File Format

A configuration contains ordinary values plus a few construction directives:

```yaml
words: [red, blue, red]
counts:
  _target_: collections.Counter
  _args_: ["@words"]
```

This is a recipe for calling `Counter(words)`. Your Python application decides
when to resolve it and what to do with the result.

## Loading Configurations

Use `update()` for files, dictionaries and CLI overrides. Later inputs compose
with earlier ones; dictionaries merge, lists extend and other values replace.

```python
from sparkwheel import Config

config = Config().update({"settings": {"limit": 3}, "words": ["red"]})
config.update({"settings": {"title": "Report"}})
config.update("settings::limit=5")
assert config.get("settings") == {"limit": 5, "title": "Report"}
```

For files, the equivalent loading pattern is
`Config().update("base.yaml").update("experiment.yaml")`.
Read [composition](operators.md) for explicit replacement and deletion.

## Accessing Configuration Values

`::` addresses dictionary keys and list indices: `settings::limit`, `words::0`.
Unresolved source containers also support ordinary Python reads such as
`config["settings"]["limit"]`.

### Using get() and resolve()

| Operation | Meaning | Can execute configured Python? |
|---|---|---|
| `config.get(path)` or `config[path]` | Read source at a path | No |
| `config.resolve(path)` | Resolve that node and its dependencies | Yes |
| `config.resolve()` | Resolve the whole configuration | Yes |
| `config.validate(Schema)` | Check source against a dataclass schema | Custom validators may execute Python |

`get()` keeps local `%` strings, `@` references, expressions and `_imports_`
declarations even after resolution. External `%file.yaml` includes are already
loaded into the source when `update()` processes them.

Resolving may import modules, evaluate expressions and call constructors. It is
not a static validation pass. Use trusted configurations, just as you would use
trusted Python modules. Partial resolution avoids unrelated runtime targets,
but configuration-wide import declarations still have setup behavior.

## Editing Configuration

Use `set()` or `update()` for every intended source change:

```python
from sparkwheel import Config

config = Config().update({"settings": {"limit": 3}, "double": "$@settings::limit * 2"})
assert config.resolve("double") == 6
config.set("settings::limit", 5)
assert config.resolve("double") == 10
```

Unfrozen raw dictionaries/lists are mutable views. Writing through
`config["settings"]["limit"]` bypasses transactional validation and cache
invalidation. Use that syntax for reads; use `set("settings::limit", value)` for
edits. Existing list indices work with `set()` too; sparse list assignment does not.

A successful edit publishes the complete candidate source and clears runtime
caches. If composition, loading or schema validation fails, the prior source and
cached identities remain intact. Multi-field `update()` calls validate together.
Custom validator side effects and file reads are outside that transaction.

## Object Lifetimes

Repeated `resolve(path)` calls reuse the same value within a resolution mode and
generation. `@` references participate in that sharing. Successful `set()` or
`update()` calls, or `resolve(lazy=False)`, start a fresh generation.

Objects already returned to your program remain the old objects. Editing the
recipe does not change a running counter, model, callback or optimizer. This
complete example demonstrates the boundary:

```python
from sparkwheel import Config

config = Config().update(
    {
        "words": ["red", "red"],
        "counts": {"_target_": "collections.Counter", "_args_": ["@words"]},
    }
)
old = config.resolve("counts")
assert config.resolve("counts") is old
config.set("words", ["blue"])
new = config.resolve("counts")
assert new is not old
assert dict(old) == {"red": 2}
assert dict(new) == {"blue": 1}
```

Different `instantiate`/`eval_expr` modes have separate caches. Retained callbacks
and generators keep their original generation; caller-owned opaque Python objects
keep ordinary identity and mutability. See [advanced contracts](advanced.md) for
the precise boundaries.

## Frozen Configs

`config.freeze()` prevents `set()` and `update()`. Frozen raw reads return detached
container snapshots, and freezing detaches views handed out earlier. Use
`config.unfreeze()` before another supported edit.

Freezing protects configuration containers. It does not freeze live resolved
objects or arbitrary Python objects supplied by the caller.

## Duplicate YAML keys

Sparkwheel rejects duplicate authored YAML keys at every mapping level and reports
both locations. Keys YAML considers equal, such as `true` and `1`, also collide.
YAML `<<` merges remain legal: explicit values override inherited ones; earlier
mappings in a merge sequence take precedence.

Compose separate files or use `update()` for deliberate changes. For migration
only, `SPARKWHEEL_STRICT_KEYS=0` restores warning/last-wins behavior;
`SPARKWHEEL_STRICT_KEYS=1` explicitly enables strict handling. A rejected file or
include leaves the previous source generation intact.

## Next Steps

[Sharing and copying](references.md) · [Composition](operators.md) ·
[Validation](schema-validation.md) · [Troubleshooting](troubleshooting.md)
