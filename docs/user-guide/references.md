# References

Use `@` when consumers should receive the same resolved value. Use `%` when you
want to reuse a definition under another path and resolve it separately.

## Quick Comparison

| Syntax | What happens | Typical use |
|---|---|---|
| `@counts` | Resolve `counts` and share its value in this mode/generation | One dependency used by several consumers |
| `%counts` | Copy the definition, then resolve the copy normally | Another independently constructed component |
| `%base.yaml::counts` | Load a definition from a file during composition | Reusable configuration fragment |
| `$len(@words)` | Evaluate a Python expression using a resolved dependency | A small derived value |

A `%` copy of a `_target_` **does construct an object when resolved**. It is not a
way to request an unevaluated dictionary. Use `get()` to inspect source; for a
retained, selectively expanded definition, see [advanced inspection](advanced.md#retained-recipes-and-construction-scopes).

## Resolved References (`@`)

This standalone example distinguishes shared identity from a copied definition:

```python
from sparkwheel import Config

config = Config().update({
    "words": ["red", "blue", "red"],
    "counts": {"_target_": "collections.Counter", "_args_": ["@words"]},
    "shared": "@counts",
    "independent": "%counts",
})
counts = config.resolve("counts")
shared = config.resolve("shared")
independent = config.resolve("independent")
assert shared is counts
assert independent is not counts
assert independent == counts
counts["red"] += 1
assert shared["red"] == 3
assert independent["red"] == 2
assert config.get("independent") == "%counts"
```

Sharing applies to objects, containers and computed results. It is scoped to the
current resolution mode and generation, not global across all `Config` instances.
Read [object lifetimes](basics.md#object-lifetimes) before rebuilding dependencies.

## List References

Use `::` to address nested dictionary keys or a list index. For the quick-start
configuration, `@words::0` resolves to `"red"`. References are whole strings;
quote them in YAML.

## Nested References

A reference may point to another reference. Expression dependencies are resolved
when Python uses them: `$@a if True else @bad` does not evaluate `bad` in ordinary
`Config` resolution. For dynamic selection use normal indexing, such as
`$@datasets[@mode]`.

### Circular References

A requested cycle such as `a: "@b"` and `b: "@a"` raises a resolution error.
Construction scopes apply additional conservative graph checks; see
[expressions](expressions.md#combining-with-references).

## Raw References (`%`)

### Local Raw References

A local `%counts` stays in the authored source until a resolution tree is compiled.
Its copied definition therefore sees source overrides applied before that
compilation. The copy gets its own path and normal resolution cache entry.

Copying a definition does not guarantee independence of every dependency. For
example, the copied counter above still contains `@words`, so both constructors
receive the shared resolved input. Counter creates its own count state from that
input. A custom class that stores a shared mutable dependency would retain it.

### External File Raw References

Create these two files in one directory and run the Python block from that directory:

```yaml title="base.yaml"
counts:
  _target_: collections.Counter
  _args_: [[red, blue, red]]
```

```yaml title="experiment.yaml"
counts: "%base.yaml::counts"
```

```python
from sparkwheel import Config

config = Config().update("experiment.yaml")
assert config.get("counts")["_target_"] == "collections.Counter"
assert dict(config.resolve("counts")) == {"red": 2, "blue": 1}
```

External `%file.yaml::path` includes are expanded during `update()`. Their content
is a loaded snapshot; later source-file edits are not watched. Local `%path`
copies expand when resolution compiles the composed source. Nested local `%` copies
inside an external include are expanded against the included file during loading.
Remaining `@` references and expressions resolve later in the composed configuration.

### Key Distinction

`@` shares a **result**. `%` copies a **definition**. Whether the resulting objects
share their internals follows the copied definition and ordinary Python behavior.

## Two-Phase Processing Model

1. `update()` loads and composes source, expanding external `%file.yaml` includes.
2. Resolution compiles a separate tree, expands local `%path` copies, and resolves
   requested references, expressions and targets. The authored source is retained.

External file access is a loading effect. Configured imports and target execution
are separate runtime effects; neither raw copies nor lazy resolution form a sandbox.

## Next Steps

[Python authoring](instantiation.md) · [Expressions](expressions.md) ·
[Advanced ownership contracts](advanced.md)
