# Changelog

All notable changes to Sparkwheel are documented here. Breaking changes come with a one-line migration.

## Unreleased

### Breaking changes

- `resolve()` no longer rewrites the config: `get()` and exports after `resolve()` keep `_imports_`, local `%` references and relative `@::` references as written.
  Migration: read expanded values with `config.resolve("key")` instead of `config.get("key")` after resolving.
- `=key` and `~key` inside a newly added subtree (dict update, override string or YAML file) are applied instead of being stored as literal keys, and `~key` there raises because the key does not exist.
  Migration: to store a key that literally starts with `=` or `~`, use `config.set(...)`.

### Fixed

- `resolve(..., instantiate=False)` no longer makes a later `resolve()` return `Component` wrappers (and vice versa): each mode has its own cache.
- A component with a literal `_disabled_: true` no longer builds its arguments (no side effects from a disabled component's nested components or expressions).
