"""Main configuration management API."""

from pathlib import Path
from typing import Any

from .loader import Loader
from .metadata import MetadataRegistry
from .operators import _validate_delete_operator, apply_operators, validate_operators
from .parser import Parser
from .path_utils import split_id
from .preprocessor import Preprocessor
from .resolver import Resolver
from .utils import PathLike, look_up_option, optional_import
from .utils.constants import ID_SEP_KEY, REMOVE_KEY, REPLACE_KEY
from .utils.exceptions import ConfigKeyError

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
        config = Config(schema=MySchema).update("config.yaml")

        # Or chain multiple sources
        config = (Config(schema=MySchema)
                  .update("base.yaml")
                  .update("override.yaml")
                  .update({"model::lr": 0.001}))

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
        globals: Pre-imported packages for expressions (e.g., {"torch": "torch"})
        schema: Dataclass schema for continuous validation
        coerce: Auto-convert compatible types (default: True)
        strict: Reject fields not in schema (default: True)
        allow_missing: Allow MISSING sentinel values (default: False)
    """

    def __init__(
        self,
        data: dict[str, Any] | None = None,  # Internal/testing use only
        *,  # Rest are keyword-only
        globals: dict[str, Any] | None = None,
        schema: type | None = None,
        coerce: bool = True,
        strict: bool = True,
        allow_missing: bool = False,
    ):
        """Initialize Config container.

        Normally starts empty - use update() to load data.

        Args:
            data: Initial data (internal/testing use only, not validated)
            globals: Pre-imported packages for expression evaluation
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
        self._metadata = MetadataRegistry()
        self._resolver = Resolver()
        self._is_parsed = False
        self._frozen = False  # Set via freeze() method later

        # Schema validation state
        self._schema: type | None = schema
        self._coerce: bool = coerce
        self._strict: bool = strict
        self._allow_missing: bool = allow_missing

        # Process globals (import string module paths)
        self._globals: dict[str, Any] = {}
        if isinstance(globals, dict):
            for k, v in globals.items():
                self._globals[k] = optional_import(v)[0] if isinstance(v, str) else v

        self._loader = Loader()
        self._preprocessor = Preprocessor(self._loader, self._globals)

    def get(self, id: str = "", default: Any = None) -> Any:
        """Get raw config value (unresolved).

        Args:
            id: Configuration path (use :: for nesting, e.g., "model::lr")
                Empty string returns entire config
            default: Default value if id not found

        Returns:
            Raw configuration value (resolved references not resolved, raw references not expanded)

        Example:
            >>> config = Config.load({"model": {"lr": 0.001, "ref": "@model::lr"}})
            >>> config.get("model::lr")
            0.001
            >>> config.get("model::ref")
            "@model::lr"  # Unresolved resolved reference
        """
        try:
            return self._get_by_id(id)
        except (KeyError, IndexError, ValueError):
            return default

    def set(self, id: str, value: Any) -> None:
        """Set config value, creating paths as needed.

        Args:
            id: Configuration path (use :: for nesting)
            value: Value to set

        Raises:
            FrozenConfigError: If config is frozen

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

        # Create missing intermediate paths
        current = self._data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            elif not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        # Set final value
        current[keys[-1]] = value
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
            >>> config = Config.load({"hidden_size": 512, "dropout": 0.1})
            >>> config.validate(ModelConfig)  # Passes
            >>> bad_config = Config.load({"hidden_size": "not an int"})
            >>> bad_config.validate(ModelConfig)  # Raises ValidationError
        """
        from .schema import validate as validate_schema

        validate_schema(self._data, schema, metadata=self._metadata)

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
            - ~key           - Remove operator: delete key (idempotent)

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

        # Validate after update if schema exists
        if self._schema:
            from .schema import validate as validate_schema

            validate_schema(
                self._data,
                self._schema,
                metadata=self._metadata,
                allow_missing=self._allow_missing,
                strict=self._strict,
            )

        return self  # Enable chaining

    def _update_from_config(self, source: "Config") -> None:
        """Update from another Config instance."""
        self._data = apply_operators(self._data, source._data)
        self._metadata.merge(source._metadata)
        self._invalidate_resolution()

    def _uses_nested_paths(self, source: dict[str, Any]) -> bool:
        """Check if dict uses :: path syntax."""
        return any(ID_SEP_KEY in str(k).lstrip(REPLACE_KEY).lstrip(REMOVE_KEY) for k in source.keys())

    def _apply_path_updates(self, source: dict[str, Any]) -> None:
        """Apply nested path updates (e.g., model::lr=value, =model=replace, ~old::param=null)."""
        for key, value in source.items():
            if not isinstance(key, str):
                self.set(str(key), value)  # type: ignore[unreachable]
                continue

            if key.startswith(REPLACE_KEY):
                # Replace operator: =key (explicit override)
                actual_key = key[1:]
                self.set(actual_key, value)

            elif key.startswith(REMOVE_KEY):
                # Delete operator: ~key (idempotent)
                actual_key = key[1:]
                _validate_delete_operator(actual_key, value)

                if actual_key in self:
                    self._delete_nested_key(actual_key)

            else:
                # Default: compose (merge dict or extend list)
                if key in self and isinstance(self[key], dict) and isinstance(value, dict):
                    merged = apply_operators(self[key], value)
                    self.set(key, merged)
                elif key in self and isinstance(self[key], list) and isinstance(value, list):
                    self.set(key, self[key] + value)
                else:
                    # Normal set (handles nested paths with ::)
                    self.set(key, value)

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
        self._data = apply_operators(self._data, source)
        self._invalidate_resolution()

    def _update_from_file(self, source: PathLike) -> None:
        """Load and update from a file."""
        new_data, new_metadata = self._loader.load_file(source)
        validate_operators(new_data)
        self._data = apply_operators(self._data, new_data)
        self._metadata.merge(new_metadata)
        self._invalidate_resolution()

    def _update_from_override_string(self, override: str) -> None:
        """Parse and apply a single override string (e.g., 'key=value', '=key=value', '~key')."""
        overrides_dict = parse_overrides([override])
        self._apply_path_updates(overrides_dict)

    def resolve(
        self,
        id: str = "",
        instantiate: bool = True,
        eval_expr: bool = True,
        lazy: bool = True,
        default: Any = None,
    ) -> Any:
        """Resolve resolved references (@) and return parsed config.

        Automatically parses config on first call. Resolves @ resolved references (follows
        them to get instantiated/evaluated values), evaluates $ expressions, and
        instantiates _target_ components. Note: % raw references are expanded during
        preprocessing (before this stage).

        Args:
            id: Config path to resolve (empty string for entire config)
            instantiate: Whether to instantiate components with _target_
            eval_expr: Whether to evaluate $ expressions
            lazy: Whether to use cached resolution
            default: Default value if id not found (returns default.get_config() if Item)

        Returns:
            Resolved value (instantiated objects, evaluated expressions, etc.)

        Example:
            >>> config = Config.load({
            ...     "lr": 0.001,
            ...     "doubled": "$@lr * 2",
            ...     "optimizer": {
            ...         "_target_": "torch.optim.Adam",
            ...         "lr": "@lr"
            ...     }
            ... })
            >>> config.resolve("lr")
            0.001
            >>> config.resolve("doubled")
            0.002
            >>> optimizer = config.resolve("optimizer")
            >>> type(optimizer).__name__
            'Adam'
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

    def _parse(self, reset: bool = True) -> None:
        """Parse config tree and prepare for resolution.

        Internal method called automatically by resolve().

        Args:
            reset: Whether to reset the resolver before parsing (default: True)
        """
        # Reset resolver if requested
        if reset:
            self._resolver.reset()

        # Stage 1: Preprocess (% raw references, @:: relative resolved IDs)
        self._data = self._preprocessor.process(self._data, self._data, id="")

        # Stage 2: Parse config tree to create Items
        parser = Parser(globals=self._globals, metadata=self._metadata)
        items = parser.parse(self._data)

        # Stage 3: Add items to resolver
        self._resolver.add_items(items)

        self._is_parsed = True

    def _get_by_id(self, id: str) -> Any:
        """Get config value by ID path.

        Args:
            id: ID path (e.g., "model::lr")

        Returns:
            Config value at that path

        Raises:
            KeyError: If path not found
        """
        if id == "":
            return self._data

        config = self._data
        for k in split_id(id):
            if not isinstance(config, (dict, list)):
                raise ValueError(f"Config must be dict or list for key `{k}`, but got {type(config)}: {config}")
            try:
                config = look_up_option(k, config, print_all_options=False) if isinstance(config, dict) else config[int(k)]
            except ValueError as e:
                raise KeyError(f"Key not found: {k}") from e

        return config

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
            >>> config = Config.load({"model": {"lr": 0.001}})
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
            >>> config = Config.load({})
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
        except (KeyError, IndexError, ValueError):
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


def parse_overrides(args: list[str]) -> dict[str, Any]:
    """Parse CLI argument overrides with automatic type inference.

    Supports only key=value syntax with operator prefixes.
    Types are automatically inferred using ast.literal_eval().

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
        >>> parse_overrides(["model::lr=0.001", "debug=True"])
        {"model::lr": 0.001, "debug": True}

        >>> # With operators
        >>> parse_overrides(["=model={'_target_': 'ResNet'}", "~old_param"])
        {"=model": {'_target_': 'ResNet'}, "~old_param": None}

        >>> # Nested paths with operators
        >>> parse_overrides(["=optimizer::lr=0.01", "~model::old_param"])
        {"=optimizer::lr": 0.01, "~model::old_param": None}

    Note:
        The '=' character serves dual purpose:
        - In 'key=value' → assignment operator (CLI syntax)
        - In '=key=value' → replace operator prefix (config operator)
    """
    import ast

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
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass  # Keep as string
            overrides[key] = value
            continue

        # Handle normal assignment: key=value
        if "=" in arg:
            key, value = arg.split("=", 1)
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass  # Keep as string
            overrides[key] = value
            continue

    return overrides
