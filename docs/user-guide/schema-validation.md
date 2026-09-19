# Schema Validation

Use a dataclass schema when configuration values need an explicit contract.
Concrete source values are checked when edited; deferred references and expressions
are checked when resolved. A schema checks arguments and values, not whether the
application achieves its intended result.

## Quick Start

This standalone example checks and coerces a numeric option, then preserves the
previous configuration when an edit fails:

```python
from dataclasses import dataclass
from sparkwheel import Config, ValidationError


@dataclass
class ReportOptions:
    title: str
    limit: int


config = Config(schema=ReportOptions).update({"title": "Words", "limit": "3"})
assert config.get("limit") == 3
try:
    config.set("limit", "not an integer")
except ValidationError:
    pass
else:
    raise AssertionError("Expected validation to reject the edit")
assert config.get("limit") == 3
```

Supply related required fields together in one update. Each update validates its
complete staged source; successive files are not one combined transaction.

## Defining Schemas

Schemas are Python dataclasses with type hints. Nested dataclasses describe nested
mappings; annotated lists and dictionaries describe their contents. Postponed
annotations resolve in the defining module. Unresolved annotation names produce
an error rather than silently disabling checks.

Dataclass defaults make fields optional for validation; they are **not inserted**
into authored source or constructor arguments. Type-only validation does not call
default factories. A target's Python signature determines runtime defaults.
Custom validators instantiate the schema, so its defaults, `default_factory` and
`__post_init__` may execute.

### Optional Fields

`int | None` permits a null value. It does not itself provide a default or make a
missing field optional. Write `limit: int | None = None` when omission is allowed.
`None` and `MISSING` have different meanings; see below.

## Type Coercion

`Config(schema=Schema, coerce=True)` normalizes compatible concrete values during
transactional edits and resolved argument values during resolution. `coerce=True`
is the default; use `coerce=False` for type checking without normalization.

| Conversion | Boundary |
|---|---|
| Numeric text → int/float | Must parse as the requested numeric type |
| Integral float → int | Fractional values such as `3.14` are rejected |
| int → float | Must be exactly representable |
| Recognized text → bool | true/false, yes/no, 1/0, ignoring case and surrounding whitespace |
| Integer 0/1 → bool | Other integers are not accepted by this conversion |
| int/float/bool → str | Arbitrary objects and containers are not stringified |

Booleans do not satisfy numeric schema fields. Coercion recurses through annotated
containers and dataclasses; dictionary keys are checked without coercion. An
already-valid union alternative wins, so `int | str` preserves `"002"` as text.
Ambiguous coercion, such as `"2"` to `int | float`, raises `ValidationError`.

`config.validate(Schema)` and standalone `validate(mapping, Schema)` check source
without coercing it or executing configured targets/expressions. Custom validators
can still execute Python.

## Custom Validation

Use `@validator` for domain constraints beyond types:

```python
from dataclasses import dataclass
from sparkwheel import Config, ValidationError, validator


@dataclass
class ReportOptions:
    limit: int

    @validator
    def positive_limit(self):
        if self.limit <= 0:
            raise ValueError("limit must be positive")


config = Config(schema=ReportOptions).update({"limit": 3})
try:
    config.set("limit", 0)
except ValidationError:
    pass
else:
    raise AssertionError("Expected the positive-limit check to fail")
assert config.get("limit") == 3
```

Validators run after type checking. Construction metadata such as `_target_` and
lenient extra keys are excluded from the schema instance initializer. Setup failures
and unexpected validator exceptions become contextual `ValidationError` with their
original cause, including inside unions. Prefer pure checks: source rollback
cannot undo external effects. Nested argument dictionaries remain dictionaries;
schemas do not recursively instantiate nested dataclasses for validator methods.

## Discriminated Unions

A shared `Literal` field can select a variant. This complete example chooses a
limited report without accepting fields from another branch:

```python
from dataclasses import dataclass
from typing import Literal
from sparkwheel import Config


@dataclass
class AllWords:
    kind: Literal["all"]


@dataclass
class TopWords:
    kind: Literal["top"]
    limit: int


@dataclass
class Options:
    report: AllWords | TopWords


config = Config(schema=Options).update({"report": {"kind": "top", "limit": 3}})
assert config.resolve("report") == {"kind": "top", "limit": 3}
```

A missing or invalid discriminator fails validation. A deferred discriminator
postpones branch checks until resolution identifies the branch. Strictness and
missing-value policies also apply within the selected branch.

## Strict vs Lenient Mode

`strict=True` rejects unexpected keys and is the default. Set `strict=False` when
you intentionally permit fields outside the schema; it does not turn off checks
for fields the schema does describe. Both policies apply recursively.

## MISSING Sentinel

Use an explicit sentinel when a required value will be supplied later:

```python
from dataclasses import dataclass
from sparkwheel import Config, MISSING


@dataclass
class Options:
    limit: int


config = Config(schema=Options, allow_missing=True).update({"limit": MISSING})
config.set("limit", 3)
config.validate(Options)
```

The final explicit `validate()` uses its normal completeness policy and rejects a
remaining `MISSING`. `None` is different: it must satisfy the declared type.

## With Sparkwheel Features

Schemas on `_target_` nodes describe **constructor arguments**, not the class of
the constructed result. This standalone example validates a deferred argument
before passing it to `dict`:

```python
from dataclasses import dataclass
from sparkwheel import Config


@dataclass
class Arguments:
    limit: int


config = Config(schema=Arguments).update({"_target_": "builtins.dict", "limit": "$2 + 1"})
assert config.get("limit") == "$2 + 1"
assert config.resolve() == {"limit": 3}
```

Nested components and aliases are checked through their resolved argument mappings
while constructors receive native objects. Shared container/component identities
are preserved. An alias cannot coerce an already-built object's argument mapping
into a different schema. Expression coercion changes the runtime value while
preserving the authored expression string.

## Validation Timing

| Operation | What is checked |
|---|---|
| `set()` / `update()` with a schema | Staged source; unresolved `@`, `$`, `%` remain deferred |
| `resolve(path)` | That node, ordinary dependencies and any needed union discriminator |
| `resolve()` | Complete resolved argument tree, including root cross-field checks |
| `config.validate(Schema)` | Current source, without coercion or configured resolution |

Partial resolution does not construct unrelated nodes merely to run a root
cross-field validator. A successful partial check is not validation of the whole
application. Invalid resolved arguments fail before their target is called, but
dependencies, imports and expressions may already have executed; resolution does
not roll back those effects.

`instantiate=False` still checks resolved arguments. `eval_expr=False` keeps
expression wrappers and postpones resolved-value checks. `retain()` explicitly
rejects attached schemas; use schema-aware `Config.resolve()` for those configs.

## Frozen Configs

Freeze after configuring when later source edits should fail. Frozen reads remain
available, but runtime objects and opaque Python inputs are not deeply frozen.
See [configuration lifetimes](basics.md#frozen-configs).

## Error Messages

`ValidationError` identifies the field and expected/actual value or type. Source
locations and native causes help distinguish a type mismatch from a validator's
own failure. See [troubleshooting](troubleshooting.md) for a staged diagnosis.

## Next Steps

[Configuration model](basics.md) · [Python authoring](instantiation.md) ·
[Quick reference](quick-reference.md)
