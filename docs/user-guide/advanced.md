# Advanced Features

This reference is for integrations that manage construction and object ownership.
Ordinary applications can use `Config.update()` and `Config.resolve()` with their
own Python classes. Start with the [configuration model](basics.md) if you only
need to load, inspect or edit a configuration.

## Source inspection and resolution generations

`get()` and subscript access read source without configured imports, targets or
expressions. Resolution compiles a separate working tree. Local `%` strings,
relative references and `_imports_` remain in source after resolution; external
`%file.yaml` includes are loaded snapshots from `update()`.

Successful `set()`/`update()` calls invalidate all runtime modes. Objects already
returned to the application are not rewritten. Unfrozen source-container views
remain mutable, so write through the supported edit APIs to invalidate caches.
Frozen reads return detached containers. Opaque Python leaves keep identity and
mutability; neither freezing nor retention deeply snapshots those objects.

Migration: code that formerly read expanded local `%` values from `get()` after
resolution must use `resolve(path)` when it wants the runtime value. Source
inspection and runtime access now stay distinct.

## Resolution modes and object sharing

Caches are separate for each `(instantiate, eval_expr)` pair. Switching modes
cannot return the representation cached by another mode; switching back reuses
that mode's existing values. Within one mode, repeated resolution and `@`
references share identity.

```python
from sparkwheel import Config

config = Config().update({"object": {"_target_": "builtins.dict", "value": 8}})
definition = config.resolve("object", instantiate=False)
instance = config.resolve("object")
assert instance == {"value": 8}
assert config.resolve("object") is instance
assert config.resolve("object", instantiate=False) is definition
```

`instantiate=False` returns `Component` wrappers; `eval_expr=False` returns
`Expression` wrappers. References inside wrappers still resolve in the selected
mode. Different modes may construct separate objects or evaluate expressions
separately. These options are not static inspection: configured imports may run,
and either enabled option may execute Python.

Successful source edits or `resolve(lazy=False)` start a fresh generation for all
modes. Published lambdas/generators retain their original definitions, imports,
schema policy and runtime cache; calling them later does not switch to edited
source. Caller-owned opaque objects retain their normal mutability.

For low-level resolver users, `Resolver.get_item()` retains its registered Item
definition even after `get_item(resolve=True)`. Use `resolve()` for runtime values.

## Retained recipes and construction scopes

A retained recipe captures source containers, locations and caller-provided import
bindings without copying runtime caches. Create one with `config.retain()`, then
create independent runtime scopes when an integration needs different ownership
or construction boundaries. This requires no additional YAML syntax.

The following standalone example builds a state object in one scope and explicitly
supplies it to a second scope:

```python
from sparkwheel import Config

config = Config().update(
    {
        "state": {"_target_": "builtins.dict", "value": 1},
        "consumer": {"_target_": "builtins.dict", "state": "@state"},
    }
)
recipe = config.retain()
state_scope = recipe.scope(blocked_paths={"consumer"})
state = state_scope.resolve("state")
consumer_scope = recipe.scope(bindings={"state": state})
consumer = consumer_scope.resolve("consumer")
assert consumer["state"] is state
assert recipe.scope().resolve("state") is not state
assert set(consumer_scope.materialized_components()) == {"consumer"}
```

Creating a recipe or scope executes no configured imports or targets. Resolving a
scope uses a fresh namespace/cache. `@` shares within that scope; local `%` copies
are independent recipes. New scopes share only explicit bindings or caller-owned
opaque inputs. Retention is not a serializer.

### Inspect a retained definition

`recipe.definition(path="")` returns a detached source-container snapshot of one
node. It follows only the local `%` chain needed to select that node; it does not
expand children, execute imports, resolve `@`, evaluate expressions or construct
targets. Missing paths raise `ConfigKeyError`; opaque leaves retain identity.

Use `Config.update()` to load external includes before retaining. Unexpanded
external includes supplied through direct `Config(data=...)` do not become later
scope file reads. Prefer `update()` for normal authoring; direct constructor data
bypasses the normal loading/validation path.

### Bindings and blocked paths

Bindings are authoritative **exact source paths**, checked before their definitions
or dependencies are traversed. A bound parent suppresses its subtree when resolving
that parent or an ancestor. Explicitly resolving an unbound descendant still
builds that descendant's source recipe; it does not read an attribute from the
bound object. Binding `model` and `model::network`, for example, still permits
resolving an unbound `model::optimizer` from its definition.

Blocked paths prohibit their nodes and descendants. Explicit reachable references
are checked before imports or construction; bound subtrees are pruned. Binding a
parent and blocking a descendant is valid. Binding at or below a blocked path
fails. This is graph checking, not static analysis of arbitrary Python code.

`scope.bind(path, value)` adds a binding for a valid source path. Rebinding the same
identity is allowed. A different identity cannot replace a value already resolved
or consumed by a cached ancestor: create a fresh scope. Import declarations are
not runtime binding paths. Scope list paths use non-negative canonical indices.

After an expression publishes a result, all its lexical reference paths reserve
binding authority, including references Python did not visit. A new binding that
touches an unresolved reserved path requires a fresh scope. Resolving the path
normally and binding the same resulting identity is allowed. This preserves
delayed values without inspecting arbitrary returned object graphs.

### Guards and preflight

A statically true `_disabled_` guard, including an exact literal guard binding,
prunes its payload before preflight. The guard itself remains subject to bindings
and blocks. Dynamic guards retain conservative preflight: a blocked argument fails
before the guard executes even if the guard would later disable the node.
Ordinary `Config` has no declared block set and evaluates a dynamic guard first.

Scopes conservatively check explicit expression references, including unselected
branches. Missing paths, blocked paths and static cycles can fail before runtime
branch selection. Neither scopes nor disabled nodes sandbox arbitrary Python.

### Construction inventory and limits

`scope.materialized_components()` returns a defensive mapping from `_target_`
paths to objects constructed in that scope. It excludes supplied bindings,
disabled components, expressions and iterator outputs, including iterators returned
by a target. The mapped objects remain live; editing the returned dictionary does
not change bookkeeping. This inventory records construction, not subsequent use
or application correctness.

Attached schemas are explicitly unsupported by `retain()`; use schema-aware
`Config.resolve()` instead. A scope must not silently discard a schema policy.
Ordinary `Config.resolve()` retains its own cache and ownership behavior.

## Atomic edits and container paths

`set()` and `update()` stage the whole edit, check its raw schema and publish only
on success. Edit, loading or validation failure preserves prior source, locations,
expression namespace and cached identities. Custom validator effects and file reads
are outside the transaction. Opaque inputs retain identity.

Paths respect dictionaries and existing list indices. Traversing a scalar or an
out-of-range list index fails. Missing dictionary paths can be created. Single
indexed deletion and batch deletion are both supported; see
[composition](operators.md#editing-nested-paths).

## Frozen Configs

`freeze()` detaches source containers from earlier views and blocks supported
edits. Frozen reads produce detached ordinary dictionaries/lists suitable for
source export. Opaque leaves and runtime objects are not deeply frozen. Use
`unfreeze()` followed by `set()`/`update()` for later source changes.

## Imports for Expressions

`_imports_` declares serializable root imports. It remains in `get()` and source
export but is omitted from the resolved runtime dictionary. After an edit,
resolution gets a fresh namespace: removed YAML imports and `$import ...` aliases
do not remain available. Imports supplied through `Config(imports=...)` remain
available across generations; string import paths passed to that constructor are
loaded at construction time.

This complete example exports source for replay:

```python
from sparkwheel import Config

config = Config().update({"_imports_": {"math": "math"}, "rounded": "$math.ceil(2.4)"})
assert config.resolve("rounded") == 3
Config.export_config_file(config.get(), "snapshot.yaml")
replayed = Config().update("snapshot.yaml")
assert replayed.resolve("rounded") == 3
```

The output `snapshot.yaml` preserves configuration data, not Python module state
or arbitrary prebuilt objects. Use import paths in `_imports_` rather than only
caller-supplied bindings when a standalone YAML export needs those imports.

## Relative ID References

`@::name` moves from the current value path to its parent and selects `name`.
Each extra `::` moves one more level up. For example:

```yaml
group:
  value: 3
  same: "@::value"        # @group::value
  nested:
    same: "@::::value"    # @group::value
```

Going above the root is an error. The same relative path machinery supports `%`
copies. Prefer absolute paths when they make ownership clearer.

## MISSING Sentinel

`MISSING` represents a required value not yet supplied; `None` is a value that must
be permitted by the field's type. See [schema validation](schema-validation.md#missing-sentinel)
for incremental configuration and completeness checking.

## Enhanced Error Messages

Source locations and native exception causes are part of useful diagnostics.
[The troubleshooting guide](troubleshooting.md) provides a staged workflow rather
than recommending full resolution as a static check.

For normal entrypoints versus lower-level implementation machinery, use the
[public API map](quick-reference.md#python-api).
