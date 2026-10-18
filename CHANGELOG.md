# Changelog

All notable changes to Sparkwheel are documented here. Breaking changes come with a one-line migration.

## Unreleased

### Breaking changes

- `resolve()` no longer rewrites the config: `get()` and exports after `resolve()` keep `_imports_`, local `%` references and relative `@::` references as written.
  Migration: read expanded values with `config.resolve("key")` instead of `config.get("key")` after resolving.
- `=key` and `~key` inside a newly added subtree (dict update, override string or YAML file) are applied instead of being stored as literal keys, and `~key` there raises because the key does not exist.
  Migration: to store a key that literally starts with `=` or `~`, use `config.set(...)`.
- A YAML file that repeats a key now raises `yaml.YAMLError` naming both lines (before, the last value silently won; `SPARKWHEEL_STRICT_KEYS` never took effect and is gone).
  Migration: delete the duplicate key.
- Floats written with an exponent and no dot (`1e-3`, `1E5`, `+1e3`) load as floats in YAML files and override values (YAML 1.2), not strings.
  Migration: quote the value (`"1e-3"`) if you need the string.
- Removed `sparkwheel.utils.check_key_duplicates` and `sparkwheel.utils.CheckKeyDuplicatesYamlLoader` (unused).
  Migration: use `sparkwheel.loader.YamlLoader` to read YAML the way Sparkwheel does.
- Override strings (`key=value` passed to `update()`) can no longer add keys, so a typo no longer silently adds a key that nothing reads. They may set any existing key, or add one argument or special key (`_disabled_`, `_mode_`, ...) directly under a `_target_` component. Anything else raises `ConfigKeyError` with a did-you-mean. Dict updates and YAML files add keys as before.
  Migration: put new keys in your YAML file, or in an extra YAML file listed on the command line.
- Setting a path through a value that is not a mapping (`model::dim::x=1` or `config.set("model::dim::x", 1)` when `dim` is `4`) raises `ConfigKeyError` instead of silently replacing the value with a dict.
  Migration: set the parent key itself (`=model::dim={x: 1}`).
- A schema field typed `int` or `float` rejects `True`/`False`.
  Migration: write a number (`1`), or type the field `bool`.
- `@validator` methods run even when the config has component keys (`_target_`) or, with `strict=False`, extra fields; an error raised while creating the dataclass for them (e.g. in `__post_init__`) is reported as a `ValidationError` instead of skipping the validators. Nested dataclass fields are passed to `__post_init__` and validators as instances, not dicts.
  Migration: fix the validator or `__post_init__` that now reports an error.
- `Resolver.get_item(id, resolve=True)` returns the item as written, since resolving no longer rewrites it.
  Migration: use `config.resolve(id)` for the resolved value.
- Removed `sparkwheel.coercion` (it was never called). `Config(coerce=...)` still works but warns with a `DeprecationWarning`: values were never converted, and still are not.
  Migration: remove the `coerce=` argument.

### Added

- `Config.check()` finds mistakes without building anything: missing references, `_target_`s that cannot be found or whose module fails to import, arguments the target does not accept and `$` expressions that do not compile. It raises one `ValidationError` listing every problem with its file:line or override. Disabled components are skipped.
- A wrong argument name raises `'pkg.Model' got an unexpected argument 'learnin_rate'` with a did-you-mean, the accepted arguments, and the line (or override) of that argument; a missing argument is reported the same way. A `TypeError` raised inside the target itself is passed through unchanged. With `_mode_: callable`, argument names are checked when the partial is created instead of when it is called.
- An override with a dotted key (`model.lr=0.1`) suggests the `::` path (`model::lr`).
- `Location.override`: the CLI override text (`model::lr=0.1`) that set a value. Errors about a value set by an override show ``[override → model::lr]`` and the override itself instead of a YAML line that is no longer in effect.

### Fixed

- `resolve(..., instantiate=False)` no longer makes a later `resolve()` return `Component` wrappers (and vice versa): each mode has its own cache.
- A component with a literal `_disabled_: true` no longer builds its arguments, whether it is resolved directly or as part of its parent (e.g. a disabled callback inside `trainer`): its nested components are not built, its expressions are not evaluated and its references need not exist.
- YAML merge keys (`<<: *base`) work in config files.
- Error messages stand alone: a failed `$` expression shows the expression as written plus the Python error (`AttributeError: ...`), syntax errors in `$` expressions carry the file and line, a `NameError` suggests `_imports_`, an unknown `_target_` module names the part that cannot be imported, a missing `@` reference points at the key that holds it, and a missing id points at its nearest existing parent instead of the first key in the file. The doubled "💡 💡" is gone.
- An expression containing the word `import` (e.g. `$@a['import']`) is no longer mistaken for an import statement.
- `@` references work anywhere in a `$` expression (`$not@a`, `$1 in@a`); an `@` inside a string literal or comment, or used as the matrix-multiplication operator (`a @ b`), is no longer treated as a reference. References inside f-string replacement fields (`$f"lr={@lr:.2e}"`, `$f'{@lr}'`) work on every Python version.
- A whole-value reference that is not a valid id (`@model.lr`) raises a `ConfigKeyError` with a did-you-mean instead of a bare `KeyError`.
- A `_target_` that cannot be found points at the `_target_` line (or override), not at the component.
- Loading a config path that contains `..` no longer warns about "path traversal attacks".
- `set()` and overrides can go through list items (`model::layers::1::dim=8`); an index that is not in the list raises `ConfigKeyError`.
- Schemas from modules that use `from __future__ import annotations` validate instead of crashing with `TypeError: isinstance() arg 2 must be a type`.

### Documentation

- New [Troubleshooting](docs/user-guide/troubleshooting.md) page with the real messages of the most common errors (checked by the test suite).
- The quick reference's examples are fixed (a `?:` ternary, `~key: true`, dotted overrides, coercion) and run by the test suite; the docs no longer teach parsing overrides by hand or claim that `set()` validates.
- Docs are published from release tags only, so the site matches the released version.
