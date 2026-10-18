# Troubleshooting

A Sparkwheel error starts with what went wrong, points at the line of your YAML file (or the command-line override) that caused it, and ends with a 💡 hint. The messages below are real: the test suite checks them. The examples use this `model.py` next to `config.yaml`:

```python title="model.py"
class Model:
    def __init__(self, learning_rate, num_classes=10):
        self.learning_rate = learning_rate
        self.num_classes = num_classes
```

!!! tip "See every problem at once"
    `config.check()` finds all of these mistakes in one go, without building anything. See [the last section](#see-every-problem-at-once).

## A reference to a key that does not exist

```yaml title="config.yaml"
num_classes: 10
model:
  _target_: model.Model
  learning_rate: 0.001
  num_classes: "@num_clases"
```

```text
Reference '@num_clases' not found in configuration

[config.yaml:5 → model::num_classes]:
       3 │   _target_: model.Model
       4 │   learning_rate: 0.001
  →    5 │   num_classes: "@num_clases"

  💡 Did you mean one of these?
    - num_classes ✓ (90% match)
```

Fix the spelling. Nested keys are referenced with `::`, e.g. `@model::num_classes`.

## An override names a key that does not exist

```yaml title="config.yaml"
trainer:
  max_epochs: 10
```

```bash
python train.py config.yaml trainer::max_epoch=5
```

```text
'trainer::max_epoch' does not exist

[override → trainer::max_epoch]:
  → trainer::max_epoch=5

  💡 Did you mean 'max_epochs'? To add a new key, put it in a YAML file.
```

Overrides change keys that exist (or add an argument to a `_target_` component), so a typo can't silently add a key that nothing reads. To add a new key, put it in a YAML file.

Here `trainer` has no `_target_`. When it does, the override is taken as a new argument and the typo is reported when `trainer` is built (or by `config.check()`): `'pkg.Trainer' got an unexpected argument 'max_epoch'`, with the same did-you-mean.

## An override uses `.` instead of `::`

```yaml title="config.yaml"
model:
  _target_: model.Model
  learning_rate: 0.001
```

```bash
python train.py config.yaml model.learning_rate=0.01
```

```text
'model.learning_rate' does not exist

[override → model.learning_rate]:
  → model.learning_rate=0.01

  💡 Nested keys are separated by '::'. Did you mean 'model::learning_rate'?
```

## A component gets an argument it does not accept

```yaml title="config.yaml"
model:
  _target_: model.Model
  learnin_rate: 0.001
```

```text
'model.Model' got an unexpected argument 'learnin_rate'

[config.yaml:3 → model::learnin_rate]:
       1 │ model:
       2 │   _target_: model.Model
  →    3 │   learnin_rate: 0.001

  💡 Did you mean 'learning_rate'? Accepted arguments: learning_rate, num_classes
```

The error points at the argument, or at the override that added it.

## A component is missing an argument

```yaml title="config.yaml"
model:
  _target_: model.Model
  num_classes: 5
```

```text
'model.Model' missing a required argument: 'learning_rate'

[config.yaml:1 → model]:
  →    1 │ model:
       2 │   _target_: model.Model
       3 │   num_classes: 5

  💡 Accepted arguments: learning_rate, num_classes
```

To pass the missing arguments later, in Python, use `_mode_: callable`: the component is then a `functools.partial`.

## A `_target_` cannot be found

```yaml title="config.yaml"
model:
  _target_: model.Modle
  learning_rate: 0.001
```

```text
Cannot locate class or function: 'model.Modle'

[config.yaml:2 → model::_target_]:
       1 │ model:
  →    2 │   _target_: model.Modle
       3 │   learning_rate: 0.001

  💡 Did you mean 'model.Model'?
```

`_target_` is a full import path (`package.module.Class`) that Python can import from where you run.

## A name in an expression is not defined

```yaml title="config.yaml"
samples: 1000
steps: "$math.ceil(@samples / 32)"
```

```text
Failed to evaluate expression '$math.ceil(@samples / 32)': NameError: name 'math' is not defined

[config.yaml:2 → steps]:
       1 │ samples: 1000
  →    2 │ steps: "$math.ceil(@samples / 32)"

  💡 To use the module `math`, import it in the config (`_imports_: {math: math}`); for the config value `math`, write `@math`.
```

## A key appears twice in a YAML file

```yaml title="config.yaml"
learning_rate: 0.001
batch_size: 32
learning_rate: 0.01
```

```text
found duplicate key 'learning_rate' (first defined on line 1)
  in "config.yaml", line 3, column 1
```

Keep one of the two. To change a value for one run, use a command-line override or a second YAML file.

## A reference is not quoted

```yaml title="config.yaml"
num_classes: 10
classes: @num_classes
```

```text
while scanning for the next token
found character '@' that cannot start any token. Quote a value that starts with @: "@key"
  in "config.yaml", line 2, column 10
```

In YAML, `@` and `%` cannot start a plain value. Write `classes: "@num_classes"`.

## See every problem at once

`config.check()` validates the whole config without building anything and lists every problem it finds. Call it after the last `update()`:

```yaml title="config.yaml"
num_classes: 10
model:
  _target_: model.Model
  learnin_rate: 0.001
  num_classes: "@num_clases"
head:
  _target_: model.Modle
```

```text
Config check found 3 problems:
- config.yaml:5 → model::num_classes: Reference '@num_clases' not found in configuration
  Did you mean one of these?
      - num_classes ✓ (90% match)
- config.yaml:4 → model::learnin_rate: 'model.Model' got an unexpected argument 'learnin_rate'
  Did you mean 'learning_rate'? Accepted arguments: learning_rate, num_classes
- config.yaml:7 → head::_target_: Cannot locate class or function: 'model.Modle'
  Did you mean 'model.Model'?
```

Disabled components are skipped. A missing argument is reported for a component that is built right away, not for one with `_mode_: callable`, which gets the rest of its arguments later.
