"""Main configuration management API."""

from __future__ import annotations

import re
from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from .loader import Loader
from .merger import merge_configs
from .metadata import MetadataRegistry
from .parser import Parser
from .resolver import Resolver
from .utils import PathLike, ensure_tuple, look_up_option, optional_import
from .utils.constants import DELETE_KEY, ID_REF_KEY, ID_SEP_KEY, MACRO_KEY, MERGE_KEY
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

        # Merge additional config
        config.merge("experiment.yaml")
        config.merge({"model::lr": 0.01})

        # Resolve references and instantiate
        model = config.resolve("model")
        everything = config.resolve()
        ```

    Args:
        data: Initial configuration data
        globals: Pre-imported packages for expressions (e.g., {"torch": "torch"})
    """

    # Patterns for file path parsing
    suffixes = ("yaml", "yml")
    suffix_match = r".*\." + f"({'|'.join(suffixes)})"
    path_match = f"({suffix_match}$)"
    path_match_compiled = re.compile(path_match, re.IGNORECASE)
    split_path_compiled = re.compile(f"({suffix_match}(?=(?:{ID_SEP_KEY}.*)|$))", re.IGNORECASE)
    # Match relative ID prefixes: @::, @::::, %::, etc.
    relative_id_prefix = re.compile(rf"(?:{ID_REF_KEY}|{MACRO_KEY}){ID_SEP_KEY}+")

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
            Files are merged in order. Use +/~ prefixes to control merging:
            - +key: value  - MERGE dict/list with existing
            - ~key: null   - DELETE key
            - key: value   - REPLACE (default)

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
            config._data = merge_configs(config._data, loaded_data)
            config._metadata.merge(loaded_metadata)

        # Validate against schema if provided
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

        keys = self.split_id(id)

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

    def merge(self, source: PathLike | dict) -> None:
        """Merge additional configuration.

        Handles both structural merging (files/dicts) and key-value updates with
        support for nested paths (::) and directives (+/~).

        Args:
            source: File path or dict to merge

        Directives:
            - +key: value  - Merge into existing key
            - ~key: null   - Delete key
            - key: value   - Replace (default)

        Examples:
            >>> # Merge from file
            >>> config.merge("override.yaml")

            >>> # Structural merge
            >>> config.merge({"+model": {"dropout": 0.1}})

            >>> # Nested path updates
            >>> config.merge({"model::lr": 0.001, "~old_param": None})
        """
        if isinstance(source, dict):
            # Check if any keys use nested path syntax or are just directives
            has_nested_paths = any(
                ID_SEP_KEY in str(k).lstrip(MERGE_KEY).lstrip(DELETE_KEY)
                for k in source.keys()
            )

            if has_nested_paths:
                # Handle as key-value updates with nested path support
                for key, value in source.items():
                    if isinstance(key, str):
                        if key.startswith(MERGE_KEY):
                            # Merge directive: +key
                            actual_key = key[1:]
                            if actual_key in self and isinstance(self[actual_key], dict) and isinstance(value, dict):
                                merged = merge_configs(self[actual_key], value)
                                self.set(actual_key, merged)
                            else:
                                self.set(actual_key, value)
                        elif key.startswith(DELETE_KEY):
                            # Delete directive: ~key
                            actual_key = key[1:]
                            if actual_key in self:
                                # Delete from parent
                                if ID_SEP_KEY in actual_key:
                                    keys = self.split_id(actual_key)
                                    parent_id = ID_SEP_KEY.join(keys[:-1])
                                    parent = self[parent_id] if parent_id else self._data
                                    if isinstance(parent, dict) and keys[-1] in parent:
                                        del parent[keys[-1]]
                                else:
                                    # Top-level key
                                    if isinstance(self._data, dict) and actual_key in self._data:
                                        del self._data[actual_key]
                                self._invalidate_resolution()
                        else:
                            # Normal set (handles nested paths with ::)
                            self.set(key, value)
                    else:
                        # Non-string key - just set normally
                        self.set(str(key), value)
            else:
                # Structural merge using merge_configs
                self._data = merge_configs(self._data, source)
                self._invalidate_resolution()
        else:
            # File path - always structural merge
            new_data, new_metadata = self._loader.load_file(source)
            self._data = merge_configs(self._data, new_data)
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

        # Resolve macros and relative IDs first
        self._resolve_macros_and_relative_ids()

        # Parse config tree to create Items
        parser = Parser(globals=self._globals, metadata=self._metadata)
        items = parser.parse(self._data)

        # Add items to resolver
        self._resolver.add_items(items)

        self._is_parsed = True

    def _resolve_macros_and_relative_ids(self) -> None:
        """Resolve macro references (%) and relative IDs (@::, @::::).

        Macros allow referencing config from other files: %file.yaml::key
        Relative IDs allow relative references: @:: (same level), @:::: (parent level)
        """
        self._data = self._do_resolve_macros(self._data, id="")

    def _do_resolve_macros(
        self,
        config: Any,
        id: str = "",
        _macro_stack: set[str] | None = None,
    ) -> Any:
        """Recursively resolve macros and relative IDs.

        Args:
            config: Config to process
            id: Current ID path
            _macro_stack: Set of macros being resolved (for cycle detection)

        Returns:
            Config with macros and relative IDs resolved
        """
        if _macro_stack is None:
            _macro_stack = set()

        # Recursively process nested structures
        if isinstance(config, dict):
            for k in list(config.keys()):
                sub_id = f"{id}{ID_SEP_KEY}{k}" if id else str(k)
                config[k] = self._do_resolve_macros(config[k], sub_id, _macro_stack)
        elif isinstance(config, list):
            for idx in range(len(config)):
                sub_id = f"{id}{ID_SEP_KEY}{idx}" if id else str(idx)
                config[idx] = self._do_resolve_macros(config[idx], sub_id, _macro_stack)

        # Process string values
        if isinstance(config, str):
            # Resolve relative IDs (@::, @::::)
            config = self.resolve_relative_ids(id, config)

            # Resolve macros (%id, %file.yaml::id)
            if config.startswith(MACRO_KEY):
                # Check for circular references
                if config in _macro_stack:
                    raise ValueError(
                        f"Circular macro reference detected: {config} is already being resolved. "
                        f"Macro chain: {' -> '.join(sorted(_macro_stack))} -> {config}"
                    )

                path, ids = self.split_path_id(config[len(MACRO_KEY) :])
                _macro_stack.add(config)

                try:
                    if not path:
                        # Local macro reference
                        loaded_config = self._data
                    else:
                        # External file macro reference
                        loaded_config, _ = self._loader.load_file(path)

                    # Create temporary Config to resolve the macro content
                    temp_config = Config(data=loaded_config, globals=self._globals)
                    result = temp_config._get_by_id(ids)
                    result = temp_config._do_resolve_macros(result, ids, _macro_stack)

                    # Deep copy to ensure independence
                    return deepcopy(result)
                finally:
                    _macro_stack.discard(config)

        return config

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
        for k in self.split_id(id):
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

    # Utility class methods (from old ConfigParser)

    @classmethod
    def split_path_id(cls, src: str) -> tuple[str, str]:
        """Split string into file path and config ID.

        Args:
            src: String like "config.yaml::model::lr"

        Returns:
            Tuple of (filepath, config_id)
        """
        src = cls.normalize_id(src)
        result = cls.split_path_compiled.findall(src)

        if not result:
            return "", src  # Pure ID, no path

        path_name = result[0][0]
        _, ids = src.rsplit(path_name, 1)
        return path_name, ids[len(ID_SEP_KEY) :] if ids.startswith(ID_SEP_KEY) else ""

    @classmethod
    def resolve_relative_ids(cls, id: str, value: str) -> str:
        """Resolve relative ID references (@::, @::::) to absolute IDs.

        Args:
            id: Current config ID path
            value: String value that may contain relative references

        Returns:
            String with relative references resolved to absolute

        Example:
            >>> # In context of "model::optimizer"
            >>> Config.resolve_relative_ids("model::optimizer", "@::lr")
            "@model::lr"
            >>> Config.resolve_relative_ids("model::optimizer", "@::::lr")
            "@lr"
        """
        value = cls.normalize_id(value)
        prefixes = sorted(set().union(cls.relative_id_prefix.findall(value)), reverse=True)
        current_id = id.split(ID_SEP_KEY)

        for p in prefixes:
            sym = ID_REF_KEY if ID_REF_KEY in p else MACRO_KEY
            length = p[len(sym) :].count(ID_SEP_KEY)

            if length > len(current_id):
                raise ValueError(f"Relative ID in `{value}` is out of range of config content")

            if length == len(current_id):
                new = ""  # Root level
            else:
                new = ID_SEP_KEY.join(current_id[:-length]) + ID_SEP_KEY

            value = value.replace(p, sym + new)

        return value

    @classmethod
    def split_id(cls, id: str | int) -> list[str]:
        """Split ID string by separator.

        Args:
            id: ID to split

        Returns:
            List of ID components
        """
        return cls.normalize_id(id).split(ID_SEP_KEY)

    @classmethod
    def normalize_id(cls, id: str | int) -> str:
        """Normalize ID to string.

        Args:
            id: ID to normalize

        Returns:
            String ID
        """
        return str(id)

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
