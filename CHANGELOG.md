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

### Fixed

- `resolve(..., instantiate=False)` no longer makes a later `resolve()` return `Component` wrappers (and vice versa): each mode has its own cache.
- A component with a literal `_disabled_: true` no longer builds its arguments (no side effects from a disabled component's nested components or expressions).
- YAML merge keys (`<<: *base`) work in config files.
- Error messages stand alone: a failed `$` expression shows the expression as written plus the Python error (`AttributeError: ...`), syntax errors in `$` expressions carry the file and line, a `NameError` suggests `_imports_`, an unknown `_target_` module names the part that cannot be imported, a missing `@` reference points at the key that holds it, and a missing id points at its nearest existing parent instead of the first key in the file. The doubled "💡 💡" is gone.
- An expression containing the word `import` (e.g. `$@a['import']`) is no longer mistaken for an import statement.
- Loading a config path that contains `..` no longer warns about "path traversal attacks".
