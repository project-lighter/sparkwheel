# Troubleshooting

Start with the smallest failing input and the operation that failed. Loading,
source validation and object construction are different stages.

## Inspect Before Executing

In the quick-start directory, this reads and prints the composed source without
constructing the counter:

```python
from sparkwheel import Config

config = Config().update("config.yaml")
print(config.get())
print(config.get("counts"))
```

`get()` preserves references and expressions. External `%file.yaml` includes have
already been loaded during `update()`. This inspection shows definitions, not
whether imports, constructors or application behavior will succeed.

When you intend to construct a component, resolve its specific path first:
`config.resolve("counts")`. Resolving the root builds the whole requested runtime
tree and may trigger unrelated application work. Neither `instantiate=False` nor
`eval_expr=False` alone makes resolution static; imports and enabled processing
can still execute Python.

## Choose the Next Check

| Symptom | Check | Next action |
|---|---|---|
| File not found | Working directory and supplied filename | Use the intended file path; run the example from its stated directory |
| Duplicate YAML key | Both locations in the error | Keep one definition, or compose separate files deliberately |
| Missing reference | Exact `::` path in the composed source | Correct the path or load the definition before resolution |
| Cannot locate target | Full import path and active Python environment | Import the same module directly with that Python |
| Constructor error | Native exception cause and constructor signature | Correct the arguments; use `=component` when replacing an inherited recipe |
| Unexpected list entries | List composition versus replacement | Use `=list` to replace, or indexed deletion to remove entries |
| An edit seems ignored | Raw nested writes or an already-returned object | Use `set()`/`update()` and explicitly obtain the new generation |
| Shared state changes elsewhere | `@` references and mutable constructor inputs | Use `%` for a copied definition and review any nested `@` dependencies |
| String becomes boolean/null | YAML override parsing | Preserve inner YAML quotes for values intended as text |
| A schema accepts a deferred value | Raw versus resolved validation stage | Resolve the intended node when execution is appropriate |

## Check Your Python Module

For the [custom report example](instantiation.md), run from `custom-report` with
the installed environment active:

```bash
python -c "from reports import WordReport; print(WordReport(['blue']).render())"
```

Expected output is `Word counts: blue=1`. If this fails, fix the Python import or
class first. Sparkwheel does not search arbitrary project directories for targets.

A target lookup failure raises `TargetNotFoundError`. A failure while calling it
raises `InstantiationError`; the native error remains in its `__cause__` chain.
There may be another Sparkwheel wrapper before the native error, so follow the
whole chain or read the complete traceback. Expression failures similarly retain
their cause through `EvaluationError`. Use the native error to distinguish a
configuration mistake from a failure in application code.

## Unexpected Debugger or Missing Expression Result

`SPARKWHEEL_DEBUG=1` enables interactive debugging. The flag is read when Sparkwheel
is imported; set it before starting Python, and restart after changing it.
Construction calls `breakpoint()`, while expressions run through `pdb.run()` and
return `None` instead of their normal result. This is debugger behavior, not
verbose logging. Leave the flag unset or `0` for ordinary or unattended execution.

An individual component can also request `_mode_: debug` or `_debug_: true`;
check those settings if a debugger appears with the environment flag disabled.
`get()` remains source inspection and does not trigger configured construction or
expression debugging.

## Validate at the Right Stage

`Config(schema=Schema)` checks concrete source values during edits and resolved
arguments before calling their target. Deferred values cannot be fully checked
without resolution. `config.validate(Schema)` checks source without executing
configured targets or expressions, but custom validators themselves are Python
and may have effects.

Partial resolution does not run unrelated root cross-field checks. See
[validation timing](schema-validation.md#validation-timing) before interpreting a
successful check as validation of the entire application.

## Report a Reproducible Issue

Include the package version and import path, the smallest relevant Python/YAML
example, the exact operation, the full exception and its cause, and the expected
result. Redact secrets and private data. State whether the problem occurs during
loading, raw validation or resolution, and whether a source edit preceded it.

[Configuration model](basics.md) · [Composition](operators.md) ·
[Advanced contracts](advanced.md)
