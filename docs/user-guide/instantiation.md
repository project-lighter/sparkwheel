# Instantiation

Keep application behavior in ordinary Python classes and functions. Sparkwheel
calls them with configured arguments; they do not need a Sparkwheel base class,
decorator or factory.

## Basic Instantiation

The [quick start](../getting-started/quickstart.md) calls `collections.Counter`.
This next complete example uses your own class. With the installed environment
active, create a separate `custom-report` directory and put all three files below
inside it.

```python title="reports.py"
from collections import Counter


class WordReport:
    def __init__(self, words, title="Word counts"):
        self.words = list(words)
        self.title = title

    def render(self):
        counts = Counter(self.words)
        entries = ", ".join(f"{word}={count}" for word, count in sorted(counts.items()))
        return f"{self.title}: {entries}"
```

```yaml title="config.yaml"
words: [red, blue, red]
report:
  _target_: reports.WordReport
  words: "@words"
  title: Example
```

```python title="run.py"
from sparkwheel import Config
from reports import WordReport

# Ordinary Python and configured construction call the same class.
plain = WordReport(["red", "blue", "red"], title="Example")
config = Config().update("config.yaml")
configured = config.resolve("report")
assert type(configured) is WordReport
assert configured.render() == plain.render()
print(configured.render())
```

Run from `custom-report`:

```bash
python run.py
```

Expected output is `Example: blue=1, red=2`. Python can import `reports` because
`run.py` and `reports.py` are together. In a larger application, install your
package into the same environment and use its full import path.

## The `_target_` Key

`_target_` is the full import path of a class or function. Other ordinary keys
become keyword arguments. A function target returns the function's result.
No automatic project discovery is performed.

In Python-authored dictionaries, `_target_` may also be the callable itself. From
the custom example directory, this works without a string import path:

```python
from sparkwheel import Config
from reports import WordReport

config = Config().update(
    {
        "report": {"_target_": WordReport, "words": ["blue"], "title": "Python"},
    }
)
assert config.resolve("report").render() == "Python: blue=1"
```

Use serializable import paths when the source must be exported as standalone
YAML. Caller-owned Python objects keep normal identity and mutability; storing
one in a config does not turn it into a portable recipe.

## Positional Arguments with `_args_`

`_args_` must be a list. Each entry becomes one positional argument, and ordinary
keys supply keyword arguments. This definition calls `Counter(["red", "red"])`:

```yaml
counts:
  _target_: collections.Counter
  _args_: [[red, red]]
```

Nested `_target_` definitions construct nested objects. Use `@path` when a
constructor must receive an existing shared object; use `%path` for a separately
resolved copied definition. See [references](references.md).

## Special Keys

### `_mode_` - Instantiation Modes

| Mode | Result |
|---|---|
| `default` | Call the target with resolved arguments |
| `callable` | Return the target, or a `functools.partial` when arguments are supplied |
| `debug` | Call the target under `pdb` |

`callable` is optional advanced control, useful when an API explicitly expects a
callable. It is not required for ordinary authoring. Arguments still resolve
before the callable/partial is returned.

### `_disabled_` - Skip Instantiation

`_disabled_: true` skips a target and its runtime argument dependencies. Inline
disabled components are removed from resolved parent lists/dicts. Resolving the
disabled path directly, or referring to it with `@`, returns `None`. The source
remains available for later re-enabling.

The guard accepts booleans, case-insensitive `"true"`/`"false"` strings, or a
resolved dynamic value. A dynamic guard runs its own dependencies first. A true
guard skips nested targets, argument expressions, unused `@` dependencies and
import statements inside its payload. Explicitly resolving a child path still
resolves that child's definition independently of the parent guard.

With `instantiate=False`, a disabled node returns a `Component` wrapper containing
its untouched payload. With `eval_expr=False`, an unresolved guard also returns a
wrapper instead of guessing its truth value. These modes have separate caches.

This is a runtime construction boundary: root `_imports_` declarations belong to
compilation, external `%file.yaml` includes load during `update()`, and ordinary
`Config` still expands/checks local copy syntax during compilation. A disabled
node does not bypass those stages. Retained scopes have stricter preflight rules,
described in [advanced contracts](advanced.md#retained-recipes-and-construction-scopes).

Migration: older versions could execute payload dependencies before checking the
guard. Put intentionally required setup outside disabled payloads.

### Other Special Keys

`_target_`, `_args_`, `_mode_` and `_disabled_` are construction metadata rather
than constructor keyword arguments. `_imports_` is a root configuration declaration
for expression imports; see [expressions](expressions.md#importing-modules).

## When a Constructor Fails

Check the native constructor signature and resolved arguments. Missing targets
raise `TargetNotFoundError`; exceptions raised while calling a target are wrapped
in `InstantiationError`. The original exception remains in the `__cause__` chain,
which may include another Sparkwheel wrapper. Follow the chain to the native
error or read the complete traceback; Sparkwheel does not repair application inputs.

[Validation](schema-validation.md) can check configured arguments before a target
is called. [Troubleshooting](troubleshooting.md) explains how to inspect source
without accidentally constructing the whole application.
