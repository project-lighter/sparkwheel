"""Main configuration management API.

Sparkwheel is a YAML-based configuration system with references, expressions, and dynamic instantiation.
This module provides the main Config class for loading, managing, and resolving configurations.

## Two-Phase Processing

Sparkwheel uses a two-phase processing model to handle different reference types at appropriate times:

### Phase 1: Eager Processing (during update())
- **External file raw refs (`%file.yaml::key`)**: Expanded immediately
- **Purpose**: External files are frozen - their content won't change
- **Example**: `%base.yaml::lr` is replaced with the actual value from base.yaml

### Phase 2: Lazy Processing (during resolve())
- **Local raw refs (`%key`)**: Expanded after all composition is complete
- **Resolved References (`@`)**: Resolved on-demand to support circular dependencies
- **Expressions (`$`)**: Evaluated when needed using Python's eval()
- **Components (`_target_`)**: Instantiated only when requested
- **Purpose**: CLI overrides can affect local `%` refs, supports deferred instantiation

## Reference Types

| Symbol | Name | When Expanded | Purpose | Example |
|--------|------|---------------|---------|---------|
| `%` | Raw Reference (external) | Eager (update()) | Copy from external files | `%base.yaml::lr` |
| `%` | Raw Reference (local) | Lazy (resolve()) | Copy local config values | `%vars::lr` |
| `@` | Resolved Reference | Lazy (resolve()) | Reference config values | `@model::lr` |
| `$` | Expression | Lazy (resolve()) | Compute values dynamically | `$@lr * 2` |

## Key Methods

- **`get(id)`**: Returns raw config value (unresolved, from `_data`)
- **`resolve(id)`**: Follows references, evaluates expressions, instantiates components
- **`update(source)`**: Loads and merges configuration from file, dict, or CLI string
- **`set(id, value)`**: Sets a config value at the given path

## Important: get() vs resolve()

These methods serve different purposes:

- `get()` always returns raw values from the internal `_data` dict
  - Returns `"@model::lr"` (the string)
  - Fast, no resolution or caching
  - Always returns raw data, even after resolve() has been called

- `resolve()` follows references and instantiates objects
  - Returns `0.001` (the actual value)
  - Uses a separate resolution cache (`_resolver._resolved`)
  - Evaluates expressions, instantiates components

Example:
    ```python
    config = Config()
    config.update({"lr": 0.001, "ref": "@lr"})

    config.get("ref")      # "@lr" (always raw, from _data)
    config.resolve("ref")  # 0.001 (follows reference, from cache)
    config.get("ref")      # Still "@lr" (get never uses cache)
    ```

This separation ensures that:
1. Raw config structure is always accessible
2. Resolution happens lazily and is cached separately
3. Multiple resolve() calls are efficient (uses cache)
4. You can inspect raw references without triggering resolution

## Quick Start

```python
from sparkwheel import Config

# Load and merge configs
config = Config()
config.update("base.yaml")
config.update("experiment.yaml")

# Get raw values
lr = config.get("model::lr")  # Raw value (may be "@base::lr")

# Resolve references and instantiate
model = config.resolve("model")  # Actual instantiated model object
lr_resolved = config.resolve("model::lr")  # Resolved value (e.g., 0.001)
```

## CLI Overrides

```python
# Auto-detects override syntax
config.update("model::lr=0.001")  # Compose (merge)
config.update("=model::lr=0.001")  # Replace
config.update("~model::old_param")  # Delete
```

See Config class docstring for full API details.
"""

from pathlib import Path
from typing import Any

from .errors import get_suggestions
from .items import Component
from .loader import Loader, YamlLoader
from .locations import LocationRegistry
from .operators import (
    MergeContext,
    _apply_operators_to_value,
    _validate_delete_operator,
    apply_operators,
    validate_operators,
)
from .parser import Parser
from .path_utils import get_by_id, split_id
from .preprocessor import Preprocessor
from .resolver import Resolver
from .utils import PathLike, optional_import
from .utils.constants import ID_SEP_KEY, REMOVE_KEY, REPLACE_KEY
from .utils.exceptions import ConfigKeyError, Location, build_missing_key_error

__all__ = ["Config", "parse_overrides"]


class Config:
    """Configuration management with continuous validation, coercion, resolved references, and instantiation.

    Main entry point for loading, managing, and resolving configurations.
    Supports YAML files with resolved references (@), raw references (%), expressions ($),
    and dynamic instantiation (_target_).

    Example:
        ```python
        from sparkwheel import Config

        # Create and load from file
        config = Config(schema=MySchema)
        config.update("config.yaml")

        # Or chain multiple sources
        config = Config(schema=MySchema)
        config.update("base.yaml")
        config.update("override.yaml")
        config.update({"model::lr": 0.001})

        # Access raw values
        lr = config.get("model::lr")

        # Set values (validates automatically if schema provided)
        config.set("model::dropout", 0.1)

        # Freeze to prevent modifications
        config.freeze()

        # Resolve references and instantiate
        model = config.resolve("model")
        everything = config.resolve()
        ```

    Args:
        imports: Pre-imported packages for expressions (e.g., {"torch": "torch"})
        schema: Dataclass schema for continuous validation
        coerce: Auto-convert compatible types (default: True)
        strict: Reject fields not in schema (default: True)
        allow_missing: Allow MISSING sentinel values (default: False)
    """

    def __init__(
        self,
        data: dict[str, Any] | None = None,  # Internal/testing use only
        *,  # Rest are keyword-only
        imports: dict[str, Any] | None = None,
        schema: type | None = None,
        coerce: bool = True,
        strict: bool = True,
        allow_missing: bool = False,
    ):
        """Initialize Config container.

        Normally starts empty - use update() to load data.

        Args:
            data: Initial data (internal/testing use only, not validated)
            imports: Pre-imported packages for expression evaluation
            schema: Dataclass schema for continuous validation
            coerce: Auto-convert compatible types
            strict: Reject fields not in schema
            allow_missing: Allow MISSING sentinel values

        Examples:
            >>> config = Config(schema=MySchema)
            >>> config.update("config.yaml")

            >>> # Chaining
            >>> config = Config(schema=MySchema).update("config.yaml")
        """
        self._data: dict[str, Any] = data or {}  # Start with provided data or empty
        self._locations = LocationRegistry()
        self._resolver = Resolver()
        self._is_parsed = False
        self._frozen = False  # Set via freeze() method later

        # Schema validation state
        self._schema: type | None = schema
        self._coerce: bool = coerce
        self._strict: bool = strict
        self._allow_missing: bool = allow_missing

        # Process imports (import string module paths)
        self._imports: dict[str, Any] = {}
        if isinstance(imports, dict):
            for k, v in imports.items():
                self._imports[k] = optional_import(v)[0] if isinstance(v, str) else v

        self._loader = Loader()
        self._preprocessor = Preprocessor(self._loader, self._imports)

    def get(self, id: str = "", default: Any = None) -> Any:
        """Get raw config value (unresolved).

        IMPORTANT: This method ALWAYS returns raw values from the internal `_data` dict,
        even after resolve() has been called. It never uses the resolution cache.

        - Returns `@` references as strings (e.g., "@model::lr")
        - Returns `$` expressions as strings (e.g., "$@lr * 2")
        - Returns external `%file.yaml::key` references already expanded (during update());
          local `%key` references and `_imports_` stay as written, even after resolve()
        - Fast, no resolution overhead

        Use this when you need to:
        - Inspect the raw config structure
        - Check what references exist
        - Access config before resolution
        - Avoid triggering expensive instantiation

        Args:
            id: Configuration path (use :: for nesting, e.g., "model::lr")
                Empty string returns entire config
            default: Default value if id not found

        Returns:
            Raw configuration value from _data (@, $ and local % unresolved)

        Examples:
            >>> # Basic usage
            >>> config = Config()
            >>> config.update({"lr": 0.001, "ref": "@lr"})
            >>> config.get("lr")
            0.001
            >>> config.get("ref")
            "@lr"  # Raw @ reference string

            >>> # get() vs resolve() comparison
            >>> config = Config()
            >>> config.update({
            ...     "lr": 0.001,
            ...     "doubled": "$@lr * 2",
            ...     "ref": "@lr"
            ... })
            >>> config.get("doubled")
            "$@lr * 2"  # Raw expression string
            >>> config.resolve("doubled")
            0.002  # Evaluated result
            >>> config.get("doubled")  # Still raw after resolve()!
            "$@lr * 2"

            >>> # With default value
            >>> config.get("nonexistent", default=999)
            999
        """
        try:
            return self._get_by_id(id)
        except (KeyError, IndexError, TypeError):
            return default

    def set(self, id: str, value: Any) -> None:
        """Set config value, creating paths as needed.

        Args:
            id: Configuration path (use :: for nesting)
            value: Value to set

        Raises:
            FrozenConfigError: If config is frozen
            ConfigKeyError: If the path goes through a value that is not a mapping or list

        Example:
            >>> config = Config()
            >>> config.set("model::lr", 0.001)
            >>> config.get("model::lr")
            0.001
        """
        from .utils.exceptions import FrozenConfigError

        # Check frozen state
        if self._frozen:
            raise FrozenConfigError("Cannot modify frozen config", field_path=id)

        if id == "":
            self._data = value
            self._invalidate_resolution()
            return

        keys = split_id(id)

        # Ensure root is dict
        if not isinstance(self._data, dict):
            self._data = {}  # type: ignore[unreachable]

        # Walk dicts and lists, creating missing (or null) mappings on the way
        current: Any = self._data
        for depth, k in enumerate(keys[:-1]):
            if isinstance(current, list):
                current = current[int(k)]
                continue
            if current.get(k) is None:
                current[k] = {}
            elif not isinstance(current[k], (dict, list)):
                prefix = ID_SEP_KEY.join(keys[: depth + 1])
                raise ConfigKeyError(f"Cannot set '{id}': '{prefix}' is {current[k]!r}, not a mapping")
            current = current[k]

        # Set final value
        current[int(keys[-1]) if isinstance(current, list) else keys[-1]] = value
        self._invalidate_resolution()

    def validate(self, schema: type) -> None:
        """Validate configuration against a dataclass schema.

        Args:
            schema: Dataclass type defining the expected structure and types

        Raises:
            ValidationError: If configuration doesn't match schema
            TypeError: If schema is not a dataclass

        Example:
            >>> from dataclasses import dataclass
            >>> @dataclass
            ... class ModelConfig:
            ...     hidden_size: int
            ...     dropout: float
            >>> config = Config().update({"hidden_size": 512, "dropout": 0.1})
            >>> config.validate(ModelConfig)  # Passes
            >>> bad_config = Config().update({"hidden_size": "not an int"})
            >>> bad_config.validate(ModelConfig)  # Raises ValidationError
        """
        from .schema import validate as validate_schema

        validate_schema(self._data, schema, metadata=self._locations)

    def freeze(self) -> None:
        """Freeze config to prevent further modifications.

        After freezing:
        - set() raises FrozenConfigError
        - update() raises FrozenConfigError
        - resolve() still works (read-only)
        - get() still works (read-only)

        Example:
            >>> config = Config(schema=MySchema).update("config.yaml")
            >>> config.freeze()
            >>> config.set("model::lr", 0.001)  # Raises FrozenConfigError
        """
        self._frozen = True

    def unfreeze(self) -> None:
        """Unfreeze config to allow modifications."""
        self._frozen = False

    def is_frozen(self) -> bool:
        """Check if config is frozen.

        Returns:
            True if frozen, False otherwise
        """
        return self._frozen

    @property
    def locations(self) -> LocationRegistry:
        """Get the location registry for this config.

        Returns:
            LocationRegistry tracking file locations of config keys

        Example:
            >>> config = Config().update("config.yaml")
            >>> location = config.locations.get("model::lr")
            >>> print(f"{location.filepath}:{location.line}")
        """
        return self._locations

    def update(self, source: PathLike | dict[str, Any] | "Config" | str) -> "Config":
        """Update configuration with changes from another source.

        Auto-detects strings as either file paths or CLI overrides:
        - Strings with '=' are parsed as overrides (e.g., "key=value", "=key=value", "~key")
        - Strings without '=' are treated as file paths
        - Dicts and Config instances work as before

        Args:
            source: File path, override string, dict, or Config instance to update from

        Returns:
            self (for chaining)

        Operators:
            - key=value      - Compose (default): merge dict or extend list
            - =key=value     - Replace operator: completely replace value
            - ~key           - Remove operator: delete key (errors if missing)

        Examples:
            >>> # Update from file
            >>> config.update("base.yaml")

            >>> # Update from override string (auto-detected)
            >>> config.update("model::lr=0.001")

            >>> # Chain multiple updates (mixed files and overrides)
            >>> config = (Config(schema=MySchema)
            ...           .update("base.yaml")
            ...           .update("exp.yaml")
            ...           .update("optimizer::lr=0.01")
            ...           .update("=model={'_target_': 'MyModel'}")
            ...           .update("~debug"))

            >>> # Update from dict
            >>> config.update({"model": {"dropout": 0.1}})

            >>> # Update from another Config instance
            >>> config1 = Config()
            >>> config2 = Config().update({"model::lr": 0.001})
            >>> config1.update(config2)

            >>> # CLI integration pattern (just loop!)
            >>> for item in cli_args:
            ...     config.update(item)
        """
        from .utils.exceptions import FrozenConfigError

        if self._frozen:
            raise FrozenConfigError("Cannot update frozen config")

        if isinstance(source, Config):
            self._update_from_config(source)
        elif isinstance(source, dict):
            if self._uses_nested_paths(source):
                self._apply_path_updates(source)
            else:
                self._apply_structural_update(source)
        elif isinstance(source, str) and ("=" in source or source.startswith("~")):
            # Auto-detect override string (key=value, =key=value, ~key)
            self._update_from_override_string(source)
        else:
            self._update_from_file(source)

        # Phase 1: Eagerly expand ONLY external file raw references (%file.yaml::key)
        # Local refs (%key) are kept as strings - they'll be expanded in _parse() after
        # all composition is complete. This allows CLI overrides to affect local refs.
        # External files are frozen (their content won't change), so eager expansion is safe.
        self._data = self._preprocessor.process_raw_refs(
            self._data, self._data, id="", locations=self._locations, external_only=True
        )

        # Validate after raw ref expansion if schema exists
        # This validates the final structure, not intermediate raw reference strings
        if self._schema:
            from .schema import validate as validate_schema

            validate_schema(
                self._data,
                self._schema,
                metadata=self._locations,
                allow_missing=self._allow_missing,
                strict=self._strict,
            )

        return self  # Enable chaining

    def _update_from_config(self, source: "Config") -> None:
        """Update from another Config instance."""
        context = MergeContext(locations=source.locations)
        self._data = apply_operators(self._data, source._data, context=context)
        self._locations.merge(source.locations)
        self._invalidate_resolution()

    def _uses_nested_paths(self, source: dict[str, Any]) -> bool:
        """Check if dict uses :: path syntax."""
        return any(ID_SEP_KEY in str(k).lstrip(REPLACE_KEY).lstrip(REMOVE_KEY) for k in source.keys())

    def _apply_path_updates(self, source: dict[str, Any]) -> None:
        """Apply nested path updates (e.g., model::lr=value, =model=replace, ~old::param=null)."""
        for key, value in source.items():
            if not isinstance(key, str):
                key = str(key)  # type: ignore[unreachable]

            if key.startswith(REPLACE_KEY):
                # Replace operator: =key (explicit override)
                actual_key = key[1:]
                self.set(actual_key, _apply_operators_to_value(value, MergeContext(self._locations, actual_key)))

            elif key.startswith(REMOVE_KEY):
                # Delete operator: ~key
                actual_key = key[1:]
                _validate_delete_operator(actual_key, value)

                if actual_key not in self:
                    # Try to find source location for the key being deleted
                    source_location = self._locations.get(actual_key) if self._locations else None

                    # For nested keys, get available keys from the parent container
                    available_keys: list[str] = []
                    parent_key_name: str | None = None
                    error_key = actual_key  # The key to show in error message

                    if ID_SEP_KEY in actual_key:
                        # Nested key like "model::lr"
                        parent_path, child_key = actual_key.rsplit(ID_SEP_KEY, 1)
                        parent_key_name = parent_path
                        error_key = child_key  # Show only the child key in nested errors
                        try:
                            parent = self._get_by_id(parent_path)
                            if isinstance(parent, dict):
                                available_keys = list(parent.keys())
                        except (KeyError, IndexError, TypeError):
                            # Parent doesn't exist, fall back to top-level
                            available_keys = list(self._data.keys()) if isinstance(self._data, dict) else []
                    else:
                        # Top-level key
                        available_keys = list(self._data.keys()) if isinstance(self._data, dict) else []

                    raise build_missing_key_error(error_key, available_keys, source_location, parent_key=parent_key_name)
                self._delete_nested_key(actual_key)

            else:
                # Default: compose (merge dict or extend list)
                if key in self and isinstance(self[key], dict) and isinstance(value, dict):
                    context = MergeContext(locations=self._locations, current_path=key)
                    merged = apply_operators(self[key], value, context=context)
                    self.set(key, merged)
                elif key in self and isinstance(self[key], list) and isinstance(value, list):
                    self.set(key, self[key] + _apply_operators_to_value(value, MergeContext(self._locations, key)))
                else:
                    # Normal set (handles nested paths with ::)
                    self.set(key, _apply_operators_to_value(value, MergeContext(self._locations, key)))

    def _delete_nested_key(self, key: str) -> None:
        """Delete a key, supporting nested paths with ::."""
        if ID_SEP_KEY in key:
            keys = split_id(key)
            parent_id = ID_SEP_KEY.join(keys[:-1])
            parent = self[parent_id] if parent_id else self._data
            if isinstance(parent, dict) and keys[-1] in parent:
                del parent[keys[-1]]
        else:
            # Top-level key
            if isinstance(self._data, dict) and key in self._data:
                del self._data[key]
        self._invalidate_resolution()

    def _apply_structural_update(self, source: dict[str, Any]) -> None:
        """Apply structural update with operators."""
        validate_operators(source)
        context = MergeContext(locations=self._locations)
        self._data = apply_operators(self._data, source, context=context)
        self._invalidate_resolution()

    def _update_from_file(self, source: PathLike) -> None:
        """Load and update from a file."""
        new_data, new_metadata = self._loader.load_file(source)
        validate_operators(new_data)

        # Check if loaded data uses :: path syntax
        if self._uses_nested_paths(new_data):
            # Expand nested paths using path updates
            self._locations.merge(new_metadata)
            self._apply_path_updates(new_data)
        else:
            # Normal structural update
            context = MergeContext(locations=new_metadata)
            self._data = apply_operators(self._data, new_data, context=context)
            self._locations.merge(new_metadata)

        self._invalidate_resolution()

    def _update_from_override_string(self, override: str) -> None:
        """Parse and apply a single override string (e.g., 'key=value', '=key=value', '~key')."""
        for key, value in parse_overrides([override]).items():
            path = key.removeprefix(REPLACE_KEY)
            if not key.startswith(REMOVE_KEY):
                self._check_override_path(path, value, override, merge=key == path)
            before = self.get(path) if key == path else None  # what a compose override merges into
            self._apply_path_updates({key: value})
            if not key.startswith(REMOVE_KEY):
                self._register_override(path, value, before, override)

    def _check_override_path(self, path: str, value: Any, override: str, merge: bool) -> None:
        """Overrides set keys that exist; the only new keys allowed are a component's arguments and special keys.

        A typo would otherwise silently add a key that nothing reads.
        """
        keys = split_id(path)
        node: Any = self._data
        for depth, key in enumerate(keys):
            try:
                node = node[int(key)] if isinstance(node, list) else node[key]
                continue
            except (KeyError, IndexError, ValueError, TypeError):
                pass
            location = Location(filepath="", line=0, id=path, override=override)
            if not isinstance(node, (dict, list)):
                parent = ID_SEP_KEY.join(keys[:depth])
                raise ConfigKeyError(
                    f"Cannot override '{path}': '{parent}' is {node!r}, not a mapping",
                    source_location=location,
                    suggestion=f"To replace the value, override '{parent}' itself.",
                )
            if depth == len(keys) - 1 and depth > 0 and isinstance(node, dict):
                if Component.is_instantiable(node) or key in Component.non_arg_keys:
                    return  # a new argument (checked against the target's signature when built) or special key
            missing = ID_SEP_KEY.join(keys[: depth + 1])
            close = get_suggestions(key, [str(k) for k in node], max_suggestions=1) if isinstance(node, dict) else []
            hint = f"Did you mean '{close[0][0]}'? " if close else ""
            raise ConfigKeyError(
                f"Cannot override '{path}': '{missing}' does not exist" if missing != path else f"'{path}' does not exist",
                source_location=location,
                suggestion=f"{hint}To add a new key, put it in your YAML file or in an extra YAML file listed on the command line.",
            )
        if merge and isinstance(node, dict) and isinstance(value, dict):
            for key, child in value.items():
                key = str(key)
                if not key.startswith(REMOVE_KEY):
                    child_path = f"{path}{ID_SEP_KEY}{key.removeprefix(REPLACE_KEY)}"
                    self._check_override_path(child_path, child, override, merge=not key.startswith(REPLACE_KEY))

    def _register_override(self, path: str, value: Any, before: Any, override: str) -> None:
        """Make errors about `path` and the values under it point at the override that set them."""
        merges = isinstance(before, dict) and isinstance(value, dict)
        extends = isinstance(before, list) and isinstance(value, list)
        if not (merges or extends):
            self._locations.register(path, Location(filepath="", line=0, id=path, override=override))
        if isinstance(value, dict):
            for key, child in value.items():
                key = str(key)
                if not key.startswith(REMOVE_KEY):
                    child_path = f"{path}{ID_SEP_KEY}{key.removeprefix(REPLACE_KEY)}"
                    child_before = before.get(key) if merges and not key.startswith(REPLACE_KEY) else None
                    self._register_override(child_path, child, child_before, override)
        elif isinstance(value, list):
            start = len(before) if extends else 0
            for index, child in enumerate(value, start):
                self._register_override(f"{path}{ID_SEP_KEY}{index}", child, None, override)

    def resolve(
        self,
        id: str = "",
        instantiate: bool = True,
        eval_expr: bool = True,
        lazy: bool = True,
        default: Any = None,
    ) -> Any:
        """Resolve references, evaluate expressions, and instantiate components.

        This is the main method for getting fully resolved config values. It:
        1. Follows `@` references to their target values
        2. Evaluates `$` expressions using Python eval()
        3. Instantiates components with `_target_` keys
        4. Caches results in a separate resolution cache (`_resolver._resolved`)

        Unlike get(), which always returns raw `_data`, resolve() performs full processing
        and uses a separate cache for efficiency.

        Processing stages:
        - `%` raw references: Already expanded during update() (eager)
        - `@` resolved references: Resolved now (lazy, supports circular deps)
        - `$` expressions: Evaluated now (lazy)
        - `_target_` components: Instantiated now (lazy)

        Args:
            id: Config path to resolve (empty string for entire config)
            instantiate: Whether to instantiate components with _target_ (default: True)
            eval_expr: Whether to evaluate $ expressions (default: True)
            lazy: Whether to use cached resolution (default: True)
            default: Default value if id not found (returns default.get_config() if Item)

        Returns:
            Resolved value (could be primitive, object, or complex structure)

        Examples:
            >>> # Basic reference resolution
            >>> config = Config()
            >>> config.update({
            ...     "lr": 0.001,
            ...     "ref": "@lr"
            ... })
            >>> config.get("ref")
            "@lr"  # Raw string
            >>> config.resolve("ref")
            0.001  # Followed reference

            >>> # Expression evaluation
            >>> config = Config()
            >>> config.update({
            ...     "lr": 0.001,
            ...     "doubled": "$@lr * 2"
            ... })
            >>> config.resolve("doubled")
            0.002

            >>> # Component instantiation
            >>> config = Config()
            >>> config.update({
            ...     "optimizer": {
            ...         "_target_": "torch.optim.Adam",
            ...         "lr": 0.001
            ...     }
            ... })
            >>> optimizer = config.resolve("optimizer")
            >>> type(optimizer).__name__
            'Adam'

            >>> # Disable instantiation (useful for inspection)
            >>> config.resolve("optimizer", instantiate=False)
            {'_target_': 'torch.optim.Adam', 'lr': 0.001}

            >>> # With default value
            >>> config.resolve("nonexistent", default=None)
            None
        """
        # Parse if needed
        if not self._is_parsed or not lazy:
            self._parse()

        # Resolve and return
        try:
            return self._resolver.resolve(id=id, instantiate=instantiate, eval_expr=eval_expr)
        except (KeyError, ConfigKeyError):
            if default is not None:
                # If default is an Item, return its config
                from .items import Item

                if isinstance(default, Item):
                    return default.get_config()
                return default
            raise

    def check(self) -> None:
        """Find mistakes in the config without building anything.

        Checks that `@` references exist, `_target_`s can be imported, components' arguments match their
        target's signature (missing arguments are allowed) and `$` expressions compile. Components with a
        `_disabled_` that is not literally false are skipped. Nothing is instantiated or evaluated, so
        `check()` is cheap to call before a run.

        Raises:
            ValidationError: Listing every problem found, each with its file:line or CLI override.

        Example:
            >>> config = Config().update("config.yaml").update("model::lr=0.1")
            >>> config.check()  # raises if anything is wrong, before any object is built
        """
        from .schema import ValidationError

        if not self._is_parsed:
            self._parse()
        problems = self._resolver.find_problems()
        if not problems:
            return
        lines = [f"Config check found {len(problems)} problem{'s' if len(problems) > 1 else ''}:"]
        for problem in problems:
            where = problem.source_location
            prefix = f"{where} → {where.id}: " if where and where.id else f"{where}: " if where else ""
            lines.append(f"- {prefix}{problem._original_message}")
            if problem.suggestion:
                lines.append("  " + problem.suggestion.replace("\n", "\n  "))
        raise ValidationError("\n".join(lines))

    def _parse(self, reset: bool = True) -> None:
        """Parse config tree and prepare for resolution.

        Internal method called automatically by resolve().

        Two-phase raw reference expansion:
        - Phase 1 (update): External file refs expanded eagerly
        - Phase 2 (here): Local refs expanded now, after all composition

        Args:
            reset: Whether to reset the resolver before parsing (default: True)
        """
        # Reset resolver if requested
        if reset:
            self._resolver.reset()

        # Work on a copy: get() and exports keep `_imports_`, local `%` refs and relative `@::` refs
        data = _copy_containers(self._data)

        # Process _imports_ key if present in config data
        # This allows YAML-based imports that become available to all expressions
        self._process_imports_key(data)

        # Phase 2: Expand local raw references (%key) now that all composition is complete
        # CLI overrides have been applied, so local refs will see final values
        data = self._preprocessor.process_raw_refs(data, data, id="", locations=self._locations, external_only=False)

        # Stage 1: Preprocess (@:: relative resolved IDs)
        data = self._preprocessor.process(data, data, id="")

        # Stage 2: Parse config tree to create Items
        parser = Parser(globals=self._imports, metadata=self._locations)
        items = parser.parse(data)

        # Stage 3: Add items to resolver
        self._resolver.add_items(items)

        self._is_parsed = True

    def _process_imports_key(self, data: dict[str, Any]) -> None:
        """Process _imports_ key from the copy of the config data being parsed.

        The _imports_ key allows declaring imports directly in YAML:

        ```yaml
        _imports_:
          torch: torch
          np: numpy
          Path: pathlib.Path

        model:
          device: "$torch.device('cuda')"
        ```

        These imports become available to all expressions in the config.
        The _imports_ key is removed from the parsed copy, so it never becomes a config item.
        """
        imports_key = "_imports_"
        if imports_key not in data:
            return

        imports_config = data.pop(imports_key)
        if not isinstance(imports_config, dict):
            return

        # Process each import
        for name, module_path in imports_config.items():
            if isinstance(module_path, str):
                # Handle dotted paths like "pathlib.Path" or "collections.Counter"
                # Split into module and attribute if needed
                if "." in module_path:
                    parts = module_path.rsplit(".", 1)
                    # First try as a module (e.g., "os.path")
                    module_obj, success = optional_import(module_path)
                    if not success:
                        # Try as module.attribute (e.g., "pathlib.Path")
                        module_obj, success = optional_import(parts[0], name=parts[1])
                    self._imports[name] = module_obj
                else:
                    # Simple module name like "json"
                    self._imports[name] = optional_import(module_path)[0]
            else:
                # Already a module or callable
                self._imports[name] = module_path

    def _get_by_id(self, id: str) -> Any:
        """Get config value by ID path.

        Args:
            id: ID path (e.g., "model::lr")

        Returns:
            Config value at that path

        Raises:
            KeyError: If path not found (includes available keys in message)
            TypeError: If trying to index a non-dict/list value
        """
        return get_by_id(self._data, id)

    def _invalidate_resolution(self) -> None:
        """Invalidate cached resolution (called when config changes)."""
        self._is_parsed = False
        self._resolver.reset()

    def __getitem__(self, id: str) -> Any:
        """Get config value by ID (subscript access).

        Args:
            id: Configuration path

        Returns:
            Config value at that path

        Example:
            >>> config = Config().update({"model": {"lr": 0.001}})
            >>> config["model::lr"]
            0.001
        """
        return self._get_by_id(id)

    def __setitem__(self, id: str, value: Any) -> None:
        """Set config value by ID (subscript access).

        Args:
            id: Configuration path
            value: Value to set

        Example:
            >>> config = Config().update({})
            >>> config["model::lr"] = 0.001
        """
        self.set(id, value)

    def __contains__(self, id: str) -> bool:
        """Check if ID exists in config.

        Args:
            id: ID path to check

        Returns:
            True if exists, False otherwise
        """
        try:
            self._get_by_id(id)
            return True
        except (KeyError, IndexError, TypeError):
            return False

    def __repr__(self) -> str:
        """String representation of config."""
        return f"Config({self._data})"

    @staticmethod
    def export_config_file(config: dict[str, Any], filepath: PathLike, **kwargs: Any) -> None:
        """Export config to YAML file.

        Args:
            config: Config dict to export
            filepath: Target file path
            kwargs: Additional arguments for yaml.safe_dump
        """
        import yaml  # type: ignore[import-untyped]

        filepath_str = str(Path(filepath))
        with open(filepath_str, "w") as f:
            yaml.safe_dump(config, f, **kwargs)


def _copy_containers(value: Any) -> Any:
    """Copy dicts and lists recursively; leaves (which may be arbitrary Python objects) are shared."""
    if isinstance(value, dict):
        return {k: _copy_containers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_copy_containers(v) for v in value]
    return value


def parse_overrides(args: list[str]) -> dict[str, Any]:
    """Parse CLI argument overrides with automatic type inference.

    Supports only key=value syntax with operator prefixes.
    Values are parsed with the same YAML rules as config files (safe loading, plus floats like ``1e-3``), ensuring
    CLI overrides behave identically to values in YAML config files.

    Args:
        args: List of argument strings to parse (e.g., from argparse)

    Returns:
        Dictionary of parsed key-value pairs with inferred types.
        Keys may have operator prefixes (=key for replace, ~key for delete).

    Operators:
        - key=value    - Normal assignment (composes/merges)
        - =key=value   - Replace operator (completely replaces key)
        - ~key         - Delete operator (removes key)

    Examples:
        >>> # Basic overrides (compose/merge)
        >>> parse_overrides(["model::lr=0.001", "debug=true"])
        {"model::lr": 0.001, "debug": True}

        >>> # With operators
        >>> parse_overrides(["=model={_target_: ResNet}", "~old_param"])
        {"=model": {'_target_': 'ResNet'}, "~old_param": None}

        >>> # Nested paths with operators
        >>> parse_overrides(["=optimizer::lr=0.01", "~model::old_param"])
        {"=optimizer::lr": 0.01, "~model::old_param": None}

    Note:
        - The '=' character serves dual purpose:
          - In 'key=value' → assignment operator (CLI syntax)
          - In '=key=value' → replace operator prefix (config operator)
        - Values use YAML syntax: ``true``/``false``, ``yes``/``no``, ``on``/``off``
          for booleans, ``null`` or ``~`` for None, ``{key: value}`` for dicts.
        - Python's ``None`` is parsed as the string ``"None"`` (use ``null`` instead).
    """
    import yaml

    overrides: dict[str, Any] = {}

    for arg in args:
        # Handle delete operator: ~key
        if arg.startswith("~"):
            key = arg  # Keep the ~ prefix
            overrides[key] = None
            continue

        # Handle replace operator: =key=value
        if arg.startswith("=") and "=" in arg[1:]:
            # Remove the = prefix, then split on first =
            rest = arg[1:]  # Remove leading =
            key, value = rest.split("=", 1)
            key = "=" + key  # Add back the = prefix to the key
            try:
                value = yaml.load(value, Loader=YamlLoader)
            except yaml.YAMLError:
                pass  # Keep as string
            overrides[key] = value
            continue

        # Handle normal assignment: key=value
        if "=" in arg:
            key, value = arg.split("=", 1)
            try:
                value = yaml.load(value, Loader=YamlLoader)
            except yaml.YAMLError:
                pass  # Keep as string
            overrides[key] = value
            continue

    return overrides
