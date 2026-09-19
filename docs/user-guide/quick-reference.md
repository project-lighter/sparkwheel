# Quick Reference

A lookup page for syntax and entrypoints. Start with the
[quick start](../getting-started/quickstart.md) for a complete program.

## Core Syntax

| Syntax | Meaning |
|---|---|
| `@path` | Share the resolved value at a path within a mode/generation |
| `%path` | Copy a local definition, then resolve the copy normally |
| `%file.yaml::path` | Load a definition from an external file during composition |
| `$expression` | Evaluate a Python expression |
| `parent::child`, `items::0` | Dictionary path, list index |
| `_target_: module.Class` | Call an importable class or function |
| `_args_: [a, b]` | Positional arguments; ordinary keys become keyword arguments |
| `_disabled_: true` | Skip runtime target construction; preserve its source |
| `_mode_: callable` | Return the callable or a partial with resolved arguments |
| `_imports_: {alias: module}` | Root expression-import declaration |

`@` shares a result; `%` copies a recipe, which may still contain shared `@`
dependencies. See [references](references.md) for identity examples.

## Composition

| Input | Behavior |
|---|---|
| Dictionary + dictionary | Recursive merge |
| List + list | Append incoming entries |
| `=key: value` | Replace the whole selected value |
| `~key: null` | Delete a key or indexed path |
| `~list: [0, 2]` | Delete indices from the original list for that batch |
| `~mapping: [a, b]` | Delete keys inside a mapping |
| `layers::0::width: 4` | Update an existing list element through a top-level path key |

[Composition rules](operators.md) include missing paths, batch deletion and atomic
failure behavior. Duplicate authored YAML keys are rejected by default.

## CLI Overrides

`config.update(input_string)` detects files and overrides. Values use YAML types.
Quote the entire override for the shell, and retain inner YAML quotes when a value
must stay text.

| Argument | Effect |
|---|---|
| `'limit=3'` | Integer assignment |
| `'enabled=true'` | Boolean assignment |
| `'label="true"'` | String assignment |
| `'=words=[blue]'` | List replacement |
| `'~words::0'` | Single-index deletion |

Read the [CLI guide](cli.md) for a complete integration and type boundaries.

## Python API

These entrypoints cover normal application code:

| API | Purpose |
|---|---|
| `Config().update(source)` | Compose a file, mapping, Config or override; return the Config |
| `config.get(path)` / `config[path]` | Read authored source without configured execution |
| `config.set(path, value)` | Transactionally set a value; returns `None` |
| `config.resolve(path)` | Resolve that node and dependencies; may execute Python |
| `config.resolve()` | Resolve the complete tree |
| `Config(schema=Schema, ...)` | Attach dataclass validation and optional coercion policy |
| `config.validate(Schema)` | Validate source explicitly without coercion |
| `config.freeze()` / `unfreeze()` / `is_frozen()` | Control supported source edits |
| `Config.export_config_file(config.get(), path)` | Write serializable source to YAML |
| `parse_overrides(arguments)` | Parse override strings separately from application |
| `validate(mapping, Schema)` / `validator` / `MISSING` | Standalone schema tools |
| `config.locations.get(path)` | Inspect recorded source location when available |

For integrations, `config.retain()` produces a retained definition with
`definition()` and `scope()`; see [advanced contracts](advanced.md).
The [generated API reference](../reference/index.md) also exposes low-level
wrappers, resolver machinery and private helpers. Their visibility is useful for
reading the implementation; they are not required authoring interfaces or a
blanket promise of stable extension contracts. Prefer the entrypoints above.

## Resolution Order

References resolve on access. Python expressions access the branches Python
selects in ordinary `Config` resolution. Retained scopes additionally preflight
explicit graph references. Circular dependencies raise errors; see
[expressions](expressions.md) for lazy-branch and import details.

## Performance Tips

Repeated resolution in one `(instantiate, eval_expr)` mode reuses cached values.
Successful supported source edits or `resolve(lazy=False)` reset all modes.
Already-returned objects, lambdas and generators retain their original generation.
Use `get()` for source inspection; disabled processing modes are not a static or
security boundary.

## Common Gotchas

- Use `set()`/`update()` for edits; raw nested writes bypass cache invalidation.
- Use `=` when replacing a list or whole component recipe.
- A copied `_target_` definition still instantiates when resolved.
- Schema checks do not prove application behavior; partial resolution is partial validation.
- Caller-owned Python objects are not deeply frozen or made serializable.

The [troubleshooting guide](troubleshooting.md) maps symptoms to the next useful
check. [Advanced contracts](advanced.md) retain the precise integration boundaries.
