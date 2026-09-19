# Expressions

Use `$` for a small Python expression whose value depends on configuration. Keep
control flow, exception handling and substantial application logic in
[ordinary Python](instantiation.md).

## Basic Expressions

This complete example evaluates arithmetic and a derived count:

```python
from sparkwheel import Config

config = Config().update({
    "words": ["red", "blue", "red"],
    "total": "$len(@words)",
    "double": "$@total * 2",
})
assert config.resolve("total") == 3
assert config.resolve("double") == 6
```

The YAML equivalent of the derived node is `total: "$len(@words)"`.
Lists, comprehensions, conditional expressions and lambdas follow Python's rules.
Assignment and arbitrary statement blocks such as `try/except` are not supported.

## Combining with References

Python resolves expression references when their values are used. In ordinary
`Config` resolution, `$@a if True else @bad` uses `a` without evaluating or
constructing `bad`. The same applies to `and`, `or`, comprehensions, lambdas and
generators. Whole-value `@path` references preserve shared identity in the selected
resolution mode.

Quoted strings, raw strings, triple-quoted strings and comments preserve literal
`@` text. `$'me@example.com'` returns the email address. Python matrix multiplication
remains an operator. Whole-value references such as `"@learning-rate"` can address
hyphenated keys; expression references use the `@word::path` grammar. For a
punctuated nested key use indexing, such as `$@settings["learning-rate"]`.

F-string literal text is preserved, including `@`, but configuration references
inside f-string replacement fields are not supported. Use
`$"value={}".format(@value)` instead.

Retained construction scopes conservatively check explicit references before
execution, including unselected branches. Missing or blocked paths and static
cycles can therefore fail in a scope even when ordinary lazy execution would not
visit them. This distinction is described in [advanced contracts](advanced.md).

## Importing Modules

Declare reusable expression imports at the configuration root. This is a complete
standalone example:

```python
from sparkwheel import Config

config = Config().update({
    "_imports_": {"math": "math"},
    "rounded": "$math.ceil(2.4)",
})
assert config.get("rounded") == "$math.ceil(2.4)"
assert config.resolve("rounded") == 3
```

Alternatively, prefix an expression with imports:

```yaml
rounded: "$import math; math.ceil(2.4)"
home: "$import os; os.getenv('HOME', '')"
```

An import prefix may contain one or more `import`/`from` statements followed by
one final Python expression. All aliases follow native Python import rules; the
final expression supplies the result. A bare import returns its first imported
binding. Arbitrary assignments or statement blocks are not part of this form.

Import declarations are made available to the generation before ordinary
expression evaluation. A trailing expression runs only when its node is requested
or used as a dependency. Root `_imports_` declarations are setup, not lazy target
construction. See [disabled payloads](instantiation.md#_disabled_-skip-instantiation)
for their more specific runtime boundary.

Migration: older versions could discard aliases or the expression after an import.
All listed aliases now import, and the final expression executes when requested;
its failures are not hidden.

## Expression Scope

Configuration keys are accessed with `@`, not injected as Python variables.
`$value_a + value_b` does not read those config keys; use `$@value_a + @value_b`.
Imported aliases are available within the configuration generation.

Returned lambdas and generators retain the generation that built them. After a
successful source edit or `resolve(lazy=False)`, an older callable still uses its
original definitions, imports, schema policy and runtime cache. This is not a
deep snapshot of arbitrary caller-owned Python objects.

Within a retained scope, an expression's lexical reference paths reserve binding
authority after it publishes a result, including references in unselected
branches. Adding a binding that touches an unresolved reserved path requires a
fresh scope. Resolving that path normally and binding the same resulting identity
is allowed. No inspection of arbitrary returned object graphs is promised.

## Calling Object Methods

Expressions may call methods of resolved objects. For the quick-start definition,
`$@counts.most_common(1)` calls the counter's method. That operation can have the
same side effects as a native Python call. Use a Python helper when a method chain
or condition becomes difficult to read.

## Error Handling

Expression parsing/evaluation failures raise contextual `EvaluationError` with
the original exception as their cause. Lazy dependency and schema failures retain
their structured error types. Read the cause and referenced path; do not replace
all errors with a silent default.

For optional imports or exception recovery, put `try/except` in a Python module
and call that helper from configuration. The [custom Python example](instantiation.md)
shows how to make such a module importable.

## Security Considerations

Expressions and targets execute Python code. Use trusted configurations; lazy
branches, disabled components and `eval_expr=False` are not sandboxing mechanisms.
Configuration imports may execute even when expression evaluation is disabled.

Migration for 0.1: expressions no longer eagerly construct every `@` dependency.
Move side effects that must always occur into explicitly requested nodes. Root
imports and composition-time external file loading retain their setup behavior.

## Next Steps

[Source versus execution](basics.md#accessing-configuration-values) ·
[Troubleshooting](troubleshooting.md) · [Advanced ownership](advanced.md)
