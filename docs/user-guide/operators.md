# Set, Combine, Delete

Keys set, `+` combines, `~` deletes: what you write is what you get.

## The Rules

| You write | YAML / dict | CLI | It does |
|-----------|-------------|-----|---------|
| **Set** | `key: value` | `key=value` | Replaces whatever `key` held: a dict, a list or a scalar |
| **Set deep inside** | `a::b::c: value` | `a::b::c=value` | Sets one value, leaving its neighbours alone |
| **Combine** | `+key: value` | `+key=value` | Merges a dict into a dict (all the way down), appends a list to a list |
| **Delete** | `~key` | `~key` | Removes `key` |
| **Delete items** | `~key: [0, 2]` | `~key::0` (one at a time) | Removes list indices or dict keys |

`+key` on a missing or `null` key sets it. On a scalar or a string (including `@ref`, `%ref` and `$expr`), or a dict where a list was (or the other way round), it is an error.

`null` is a value: `key: null` sets `key` to `None`. Only `~` deletes.

## Statements, Applied in Order

A YAML file, a dict passed to `update()` and a command-line override are each a list of **statements**. Every top-level key is one statement, and they are applied in order:

```yaml
# experiment.yaml: three statements
model::hidden_size: 1024   # set one value inside model
+trainer:                  # merge into trainer
  max_epochs: 50
~debug: null               # delete debug
```

A file is not deep-merged into the config. `model:` in a second file sets `model` to what the second file says; `+model:` merges into it. Within a statement, everything below the key is the value you wrote.

## Set: `key`

Setting replaces the old value, whatever its type:

```yaml
# base.yaml
model: {hidden_size: 512, dropout: 0.1}
plugins: [logger, metrics]

# override.yaml
model: {hidden_size: 1024}   # → {hidden_size: 1024}
plugins: [cache]             # → [cache]
```

A `::` path sets one value deep inside and leaves the rest alone. Missing dicts on the way are created:

```yaml
model::hidden_size: 1024     # → {hidden_size: 1024, dropout: 0.1}
plugins::0: console          # → [console, metrics]
logging::wandb::project: x   # creates logging and logging::wandb
```

## Combine: `+key`

`+key` merges a dict into a dict, all the way down:

```yaml
# base.yaml
trainer:
  max_epochs: 10
  precision: 32
  logger: {name: tb, save_dir: logs}

# override.yaml
+trainer:
  max_epochs: 50          # set
  logger: {name: wandb}   # merged → {name: wandb, save_dir: logs}

# Result:
# trainer: {max_epochs: 50, precision: 32, logger: {name: wandb, save_dir: logs}}
```

and appends a list to a list:

```yaml
# base.yaml
callbacks: [checkpoint]

# override.yaml
+callbacks: [early_stopping]   # → [checkpoint, early_stopping]
```

Inside a `+key`, dicts keep merging, while lists and scalars are set. Operators and paths work there too:

```yaml
+trainer:
  +callbacks: [lr_monitor]   # append to trainer::callbacks
  ~precision: null           # delete trainer::precision
  logger::name: wandb        # set one value deeper down
```

!!! warning "A list inside `+key` is set, not appended"
    `+trainer: {callbacks: [x]}` **sets** `trainer::callbacks` to `[x]`, dropping the callbacks that were there. To append, write `+callbacks` inside it, or the path `+trainer::callbacks: [x]`.

`+key` on a missing or `null` key sets it, so an overlay can add a key that may or may not already be there:

```yaml
+callbacks: [early_stopping]   # appends, or creates the list
```

`+` on anything else is an error that says what is there:

```text
Cannot combine 'lr': it is 0.001, and '+' adds 0.01
  💡 To replace 'lr', drop the '+'.
```

## Delete: `~key`

```yaml
~debug: null                 # delete a key (`~debug:` works too)
~model::dropout: null        # delete a nested key
~plugins::0: null            # delete one list item
~plugins: [0, 2]             # delete several list items
~dataloaders: [train, test]  # delete several dict keys
```

Several list indices are removed from the highest down, so each index refers to the list as it was. Negative indices work (`~plugins: [-1]`). Deleting a key that does not exist is an error with a did-you-mean, so a typo can't go unnoticed.

## Components

A component is a dict with a `_target_`. Setting it to a dict **without** a `_target_` would drop its class, which is almost always a missing `+`, so it is an error:

```yaml
# base.yaml
trainer:
  _target_: pytorch_lightning.Trainer
  max_epochs: 10
  accelerator: gpu

# override.yaml
trainer:
  max_epochs: 50
```

```text
'trainer' replaces the component 'pytorch_lightning.Trainer' and drops '_target_', 'accelerator'
  💡 To change only these keys, write '+trainer' instead of 'trainer', or set them one by one ('trainer::max_epochs').
```

What you can write instead, one of:

| You write | Result |
|---|---|
| `+trainer: {max_epochs: 50}` | changes some arguments, keeps the rest |
| `trainer::max_epochs: 50` | the same, one value |
| `trainer: {_target_: my_project.FastTrainer, max_epochs: 50}` | swaps the class: the old arguments go |
| `trainer: "@other_trainer"` | sets a reference, a string or null: fine |

`+trainer: {_target_: my_project.FastTrainer}` swaps the class and keeps the old arguments.

## Layering Files

Each file after the first is a set of changes to what came before:

```yaml
# base.yaml
_imports_: {math: math}
model:
  _target_: my_project.Net
  hidden_size: 512
  dropout: 0.1
callbacks: [checkpoint]
debug: true

# experiment.yaml
+_imports_: {os: os}           # add an import
+model: {hidden_size: 1024}    # merge into the component
+callbacks: [early_stopping]   # append
~debug: null                   # delete
```

```python
config = Config().update("base.yaml").update("experiment.yaml")
```

!!! warning "`_imports_` is a key like any other"
    An overlay's `_imports_:` replaces the base's imports. Write `+_imports_:` to add to them.

## In Python

`update()` takes the same statements as a dict:

```python
config.update({"model::hidden_size": 1024})  # set one value
config.update({"+trainer": {"max_epochs": 50}})  # merge
config.update({"+callbacks": ["early_stopping"]})  # append
config.update({"~debug": None, "~plugins": [0, 2]})  # delete
config.update(other_config)  # another Config's top-level keys, as statements
```

`config.set("model::hidden_size", 1024)` is a plain assignment: no operators, no checks, missing dicts on the path are created.

## Common Mistakes

| You wrote | What happens | Write instead |
|-----------|--------------|---------------|
| `model: {lr: 0.01}` to change one value | `model` becomes `{lr: 0.01}` (or an error, if it is a component) | `model::lr: 0.01` or `+model: {lr: 0.01}` |
| `+trainer: {callbacks: [x]}` to add a callback | `callbacks` is set to `[x]` | `+trainer::callbacks: [x]` |
| `model: {+layers: [x]}` | Error: `'model' is set, so '+layers' inside it has nothing to combine with` | `+model: {+layers: [x]}` |
| `key: null` to remove a key | `key` is `None` | `~key: null` |
| `=model: {...}` (Sparkwheel < 0.1) | Error: the `=` operator was removed | `model: {...}` |

## Comparison with Hydra

| | Hydra | Sparkwheel |
|---|-------|------------|
| A later config's dict | Deep-merged | Set; `+key` deep-merges |
| A later config's list | Replaced | Set; `+key` appends |
| CLI `key=value` | Overrides an existing key | Same, with a did-you-mean for typos |
| CLI `+key=value` | Adds a new key (error if it exists) | Combines: merges, appends, or adds a new key |
| CLI `++key=value` | Adds or overrides | Not needed: `+key` adds or combines |
| Delete | `~key` on the CLI | `~key` in YAML, dicts and the CLI; list items by index |
| Operators in YAML files | No (the defaults list has `override`) | Yes |
| Config groups, defaults list, multirun | Yes | No: load the files you want, in order |

Hydra composes configs through its defaults list and merges them deeply. Sparkwheel applies each file as written, so a key in a later file means exactly what it says, and merging is something you ask for with `+`.

## Next Steps

- **[CLI Overrides](cli.md)** - The same statements on the command line
- **[Configuration Basics](basics.md)** - Core config management
- **[Advanced Features](advanced.md)** - Macros and power features
