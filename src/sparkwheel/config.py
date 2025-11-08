"""Main configuration management API."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .loader import Loader
from .metadata import MetadataRegistry
from .operators import _validate_delete_operator, apply_operators
from .parser import Parser
from .path_utils import split_id
from .preprocessor import Preprocessor
from .resolver import Resolver
from .utils import PathLike, ensure_tuple, look_up_option, optional_import
from .utils.constants import DELETE_KEY, ID_SEP_KEY, MERGE_KEY
from .utils.exceptions import ConfigKeyError

__all__ = ["Config"]


class Config:
    """Configuration management with references, expressions, and instantiation.

    Main entry point for loading, managing, and resolving configurations.
    Supports YAML files with references (@), expressions ($), and dynamic
    instantiation (_target_).

    Example:
        ```python
        from sparkwheel import Config

        # Load from file
        config = Config.load("config.yaml")

        # Load from dict
        config = Config.load({"model": {"lr": 0.001}})

        # Load multiple files (merged in order)
        config = Config.load(["base.yaml", "override.yaml"])

        # Access raw values
        lr = config.get("model::lr")

        # Set values
        config.set("model::dropout", 0.1)

        # Update with additional config
        config.update("experiment.yaml")
        config.update({"model::lr": 0.01})

        # Resolve references and instantiate
        model = config.resolve("model")
        everything = config.resolve()
        ```

    Args:
        data: Initial configuration data
        globals: Pre-imported packages for expressions (e.g., {"torch": "torch"})
    """

    def __init__(self, data: dict | None = None, globals: dict[str, Any] | None = None):
        """Initialize Config (use Config.load() instead for most cases).

        Args:
            data: Initial configuration dictionary
            globals: Global variables for expression evaluation
        """
        self._data: dict = data or {}
        self._metadata = MetadataRegistry()
        self._resolver = Resolver()
        self._is_parsed = False

        # Process globals (import string module paths)
        self._globals: dict[str, Any] = {}
        if isinstance(globals, dict):
            for k, v in globals.items():
                self._globals[k] = optional_import(v)[0] if isinstance(v, str) else v

        self._loader = Loader()
        self._preprocessor = Preprocessor(self._loader, self._globals)

    @classmethod
    def load(
        cls,
        source: PathLike | Sequence[PathLike] | dict,
        globals: dict[str, Any] | None = None,
        schema: type | None = None,
    ) -> "Config":
        """Load configuration from file(s) or dict.

        Primary method for creating Config instances.

        Args:
            source: File path, list of paths, or config dict
            globals: Pre-imported packages for expressions
            schema: Optional dataclass schema for validation

        Returns:
            New Config instance

        Merge Behavior:
            Files are merged in order. Use operators to control merging:
            - +key: value  - Merge operator: merge dict/list with existing
            - ~key: null   - Delete operator: delete key
            - key: value   - Replace (default)

        Examples:
            >>> # Single file
            >>> config = Config.load("config.yaml")

            >>> # Multiple files (merged)
            >>> config = Config.load(["base.yaml", "override.yaml"])

            >>> # From dict
            >>> config = Config.load({"model": {"lr": 0.001}})

            >>> # With globals for expressions
            >>> config = Config.load("config.yaml", globals={"torch": "torch"})

            >>> # With schema validation
            >>> from dataclasses import dataclass
            >>> @dataclass
            ... class MySchema:
            ...     name: str
            ...     value: int
            >>> config = Config.load("config.yaml", schema=MySchema)
        """
        config = cls(globals=globals)

        # Handle dict input
        if isinstance(source, dict):
            config._data = source
            if schema is not None:
                config.validate(schema)
            return config

        # Handle file(s) input
        file_list = ensure_tuple(source)
        for filepath in file_list:
            loaded_data, loaded_metadata = config._loader.load_file(filepath)
            # Merge data and metadata
            config._data = apply_operators(config._data, loaded_data)
            config._metadata.merge(loaded_metadata)

        # Validate against schema if provided
        if schema is not None:
            config.validate(schema)

        return config

    @classmethod
    def from_cli(
        cls,
        source: PathLike | Sequence[PathLike] | dict,
        cli_overrides: list[str],
        globals: dict[str, Any] | None = None,
        schema: type | None = None,
    ) -> "Config":
        """Load configuration with CLI overrides applied.

        Convenience method for loading configs with command-line overrides.
        First loads the base config, then applies CLI overrides in the format
        "key::path=value", and optionally validates against a schema.

        Args:
            source: File path, list of paths, or config dict
            cli_overrides: List of override strings in format "key::path=value"
            globals: Pre-imported packages for expressions
            schema: Optional dataclass schema for validation

        Returns:
            New Config instance with CLI overrides applied

        Examples:
            >>> # Load with CLI overrides
            >>> config = Config.from_cli(
            ...     "config.yaml",
            ...     ["model::lr=0.001", "trainer::max_epochs=100"]
            ... )

            >>> # Multiple files with overrides
            >>> config = Config.from_cli(
            ...     ["base.yaml", "experiment.yaml"],
            ...     ["model::lr=0.001"]
            ... )

            >>> # With schema validation
            >>> from dataclasses import dataclass
            >>> @dataclass
            ... class TrainingConfig:
            ...     model: dict
            ...     trainer: dict
            >>> config = Config.from_cli(
            ...     "config.yaml",
            ...     ["model::lr=0.001"],
            ...     schema=TrainingConfig
            ... )

            >>> # Complex overrides
            >>> config = Config.from_cli(
            ...     "config.yaml",
            ...     [
            ...         "model::lr=0.001",
            ...         "trainer::devices=[0,1,2]",
            ...         "model::layers=[128,256,512]",
            ...         "debug=True"
            ...     ]
            ... )
        """
        from .cli import parse_overrides

        # Load base configuration
        config = cls.load(source, globals=globals, schema=schema)

        # Apply CLI overrides
        if cli_overrides:
            overrides = parse_overrides(cli_overrides)
            for key, value in overrides.items():
                config.set(key, value)

            # Re-validate after overrides if schema provided
            if schema is not None:
                config.validate(schema)

        return config

    def get(self, id: str = "", default: Any = None) -> Any:
        """Get raw config value (unresolved).

        Args:
            id: Configuration path (use :: for nesting, e.g., "model::lr")
                Empty string returns entire config
            default: Default value if id not found

        Returns:
            Raw configuration value (references not resolved)

        Example:
            >>> config = Config.load({"model": {"lr": 0.001, "ref": "@model::lr"}})
            >>> config.get("model::lr")
            0.001
            >>> config.get("model::ref")
            "@model::lr"  # Unresolved reference
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

        Example:
            >>> config = Config.load({})
            >>> config.set("model::lr", 0.001)
            >>> config.get("model::lr")
            0.001
        """
        if id == "":
            self._data = value
            self._invalidate_resolution()
            return

        keys = split_id(id)

        # Ensure root is dict
        if not isinstance(self._data, dict):
            self._data = {}

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

    def update(self, source: PathLike | dict | "Config") -> None:
        """Update configuration with changes from another source.

        Applies changes using operators for fine-grained control.
        Supports nested paths (::) and merge/delete operators (+/~).

        Args:
            source: File path, dict, or Config instance to update from

        Operators:
            - +key: value  - Merge operator: merge into existing key
            - ~key: null   - Delete operator: delete key
            - key: value   - Replace (default)

        Examples:
            >>> # Update from file
            >>> config.update("override.yaml")

            >>> # Update from dict
            >>> config.update({"+model": {"dropout": 0.1}})

            >>> # Update from another Config instance
            >>> config1 = Config.load("base.yaml")
            >>> config2 = Config.from_cli("override.yaml", ["model::lr=0.001"])
            >>> config1.update(config2)

            >>> # Nested path updates
            >>> config.update({"model::lr": 0.001, "~old_param": None})
        """
        if isinstance(source, Config):
            self._update_from_config(source)
        elif isinstance(source, dict):
            if self._uses_nested_paths(source):
                self._apply_path_updates(source)
            else:
                self._apply_structural_update(source)
        else:
            self._update_from_file(source)

    def _update_from_config(self, source: "Config") -> None:
        """Update from another Config instance."""
        self._data = apply_operators(self._data, source._data)
        self._metadata.merge(source._metadata)
        self._invalidate_resolution()

    def _uses_nested_paths(self, source: dict) -> bool:
        """Check if dict uses :: path syntax."""
        return any(ID_SEP_KEY in str(k).lstrip(MERGE_KEY).lstrip(DELETE_KEY) for k in source.keys())

    def _apply_path_updates(self, source: dict) -> None:
        """Apply nested path updates (e.g., model::lr=value, ~old::param=null)."""
        for key, value in source.items():
            if not isinstance(key, str):
                self.set(str(key), value)
                continue

            if key.startswith(MERGE_KEY):
                # Merge operator: +key
                actual_key = key[1:]
                if actual_key in self and isinstance(self[actual_key], dict) and isinstance(value, dict):
                    merged = apply_operators(self[actual_key], value)
                    self.set(actual_key, merged)
                else:
                    self.set(actual_key, value)

            elif key.startswith(DELETE_KEY):
                # Delete operator: ~key
                actual_key = key[1:]
                _validate_delete_operator(actual_key, value)

                if actual_key in self:
                    self._delete_nested_key(actual_key)
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

    def _apply_structural_update(self, source: dict) -> None:
        """Apply structural update with operators."""
        self._data = apply_operators(self._data, source)
        self._invalidate_resolution()

    def _update_from_file(self, source: PathLike) -> None:
        """Load and update from a file."""
        new_data, new_metadata = self._loader.load_file(source)
        self._data = apply_operators(self._data, new_data)
        self._metadata.merge(new_metadata)
        self._invalidate_resolution()

    def resolve(
        self,
        id: str = "",
        instantiate: bool = True,
        eval_expr: bool = True,
        lazy: bool = True,
        default: Any = None,
    ) -> Any:
        """Resolve references and return parsed config.

        Automatically parses config on first call. Resolves @ references,
        evaluates $ expressions, and instantiates _target_ components.

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

        # Stage 1: Preprocess (% macros, @:: relative IDs)
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
    def export_config_file(config: dict, filepath: PathLike, **kwargs: Any) -> None:
        """Export config to YAML file.

        Args:
            config: Config dict to export
            filepath: Target file path
            kwargs: Additional arguments for yaml.safe_dump
        """
        import yaml

        filepath_str = str(Path(filepath))
        with open(filepath_str, "w") as f:
            yaml.safe_dump(config, f, **kwargs)
