"""Resolve references between Items."""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from typing import Any

from .items import Component, Expression, Item
from .path_utils import normalize_id, replace_references, scan_references
from .utils import allow_missing_reference, look_up_option
from .utils.constants import ID_REF_KEY, ID_SEP_KEY
from .utils.exceptions import CircularReferenceError, ConfigKeyError

__all__ = ["Resolver"]


class Resolver:
    """Resolve references between Items.

    Manages Items and resolves reference strings (starting with @) by
    substituting them with their corresponding resolved values.

    Example:
        ```python
        from sparkwheel import Item, Component, Resolver

        resolver = Resolver()

        # Add items
        resolver.add_item(Item(config=0.001, id="lr"))
        resolver.add_item(Item(config={"lr": "@lr"}, id="config"))

        # Resolve
        result = resolver.resolve("config")
        print(result)  # {"lr": 0.001}
        ```

    References can use :: separator for nested access:
    - Dictionary keys: @config::key::subkey
    - List indices: @list::0::subitem
    """

    _vars = "__local_refs"  # Variable name for resolved refs in expression evaluation
    sep = ID_SEP_KEY  # Separator for nested key access
    ref = ID_REF_KEY  # Reference prefix (@)
    allow_missing_reference = allow_missing_reference
    max_resolution_depth = 100  # Prevent DoS from deeply nested references

    def __init__(self, items: list[Item] | None = None):
        """Initialize resolver with optional items.

        Args:
            items: Optional list of Items to add during initialization
        """
        self._items: dict[str, Item] = {}
        self._resolved: dict[str, Any] = {}

        if items:
            for item in items:
                self.add_item(item)

    def reset(self) -> None:
        """Clear all items and resolved content."""
        self._items = {}
        self._resolved = {}

    def is_resolved(self) -> bool:
        """Check if any items have been resolved."""
        return bool(self._resolved)

    def add_item(self, item: Item) -> None:
        """Add a Item to resolve.

        Args:
            item: Item to add
        """
        id = item.get_id()
        if id in self._items:
            warnings.warn(
                f"Duplicate config item ID '{id}' detected. "
                f"The new item will be ignored and the existing item will be kept. "
                f"This may indicate a configuration error.",
                UserWarning,
                stacklevel=2,
            )
            return
        self._items[id] = item

    def add_items(self, items: list[Item]) -> None:
        """Add multiple Items at once.

        Args:
            items: List of Items to add
        """
        for item in items:
            self.add_item(item)

    def get_item(self, id: str, resolve: bool = False, **kwargs: Any) -> Item | None:
        """Get Item by id, optionally resolved.

        Args:
            id: ID of the config item
            resolve: Whether to resolve the item (default: False)
            **kwargs: Additional arguments for resolution

        Returns:
            Item if found, None otherwise (or resolved value if resolve=True)
        """
        id = self.normalize_id(id)
        if resolve and id not in self._resolved:
            self._resolve_one_item(id=id, **kwargs)
        return self._items.get(id)

    def resolve(
        self,
        id: str = "",
        instantiate: bool = True,
        eval_expr: bool = True,
        default: Any = None,
    ) -> Any:
        """Resolve a config item and return the result.

        Resolves all references, instantiates components (if requested), and
        evaluates expressions (if requested). Results are cached for efficiency.

        Args:
            id: ID of item to resolve (empty string for root)
            instantiate: Whether to instantiate components with _target_
            eval_expr: Whether to evaluate expressions starting with $
            default: Default value if id not found

        Returns:
            Resolved value (instantiated object, evaluated result, or raw value)

        Raises:
            ConfigKeyError: If id not found and no default provided
            CircularReferenceError: If circular reference detected
        """
        return self._resolve_one_item(id=id, instantiate=instantiate, eval_expr=eval_expr, default=default)

    def _resolve_one_item(
        self,
        id: str,
        waiting_list: set[str] | None = None,
        _depth: int = 0,
        instantiate: bool = True,
        eval_expr: bool = True,
        default: Any = None,
    ) -> Any:
        """Internal recursive resolution implementation.

        Args:
            id: ID to resolve
            waiting_list: Set of IDs currently being resolved (for cycle detection)
            _depth: Current recursion depth (for DoS prevention)
            instantiate: Whether to instantiate components
            eval_expr: Whether to evaluate expressions
            default: Default value if not found

        Returns:
            Resolved value

        Raises:
            RecursionError: If max depth exceeded
            CircularReferenceError: If circular reference detected
            ConfigKeyError: If reference not found
        """
        # Prevent stack overflow attacks
        if _depth >= self.max_resolution_depth:
            raise RecursionError(
                f"Maximum reference resolution depth ({self.max_resolution_depth}) exceeded while resolving '{id}'. "
                f"This may indicate an overly complex configuration or a potential DoS attack."
            )

        id = self.normalize_id(id)

        # Return cached result if available
        if id in self._resolved:
            return self._resolved[id]

        # Look up the item
        try:
            item = look_up_option(id, self._items, print_all_options=False, default=default or "no_default")
        except ValueError as err:
            # Provide helpful error with suggestions
            source_location = None
            for config_item in self._items.values():
                if hasattr(config_item, "source_location") and config_item.source_location:
                    source_location = config_item.source_location
                    break

            available_keys = list(self._items.keys())
            config_context = None

            # For nested IDs, try to get parent context to show available keys
            if ID_SEP_KEY in id:
                parent_id = ID_SEP_KEY.join(id.split(ID_SEP_KEY)[:-1])
                try:
                    parent_item = self.get_item(parent_id)
                    if parent_item and isinstance(parent_item.get_config(), dict):
                        config_context = parent_item.get_config()
                except (ValueError, KeyError):
                    pass

            raise ConfigKeyError(
                f"Config ID '{id}' not found in the configuration",
                source_location=source_location,
                missing_key=id,
                available_keys=available_keys,
                config_context=config_context,
            ) from err

        # If default was returned, just return it
        if not isinstance(item, Item):
            return item

        item_config = item.get_config()

        # Initialize waiting list for circular reference detection
        if waiting_list is None:
            waiting_list = set()
        waiting_list.add(id)

        # First, resolve any import expressions (they need to run first)
        for t, v in self._items.items():
            if t not in self._resolved and isinstance(v, Expression) and v.is_import_statement(v.get_config()):
                self._resolved[t] = v.evaluate() if eval_expr else v

        # Find all references in this item's config
        refs = self.find_refs_in_config(config=item_config, id=id)

        # Resolve dependencies first
        for dep_id in refs.keys():
            # Check for circular references
            if dep_id in waiting_list:
                raise CircularReferenceError(
                    f"Circular reference detected: '{dep_id}' references back to '{id}'",
                    source_location=item.source_location if hasattr(item, "source_location") else None,
                )

            # Resolve dependency if not already resolved
            if dep_id not in self._resolved:
                try:
                    look_up_option(dep_id, self._items, print_all_options=False)
                except ValueError as err:
                    msg = f"the referring item `@{dep_id}` is not defined in the config content."
                    if not self.allow_missing_reference:
                        available_keys = list(self._items.keys())
                        raise ConfigKeyError(
                            f"Reference '@{dep_id}' not found in configuration",
                            source_location=item.source_location if hasattr(item, "source_location") else None,
                            missing_key=dep_id,
                            available_keys=available_keys,
                        ) from err
                    warnings.warn(msg, stacklevel=2)
                    continue

                # Recursively resolve dependency
                self._resolve_one_item(
                    id=dep_id,
                    waiting_list=waiting_list,
                    _depth=_depth + 1,
                    instantiate=instantiate,
                    eval_expr=eval_expr,
                )
                waiting_list.discard(dep_id)

        # All dependencies resolved, now resolve this item
        new_config = self.update_config_with_refs(config=item_config, id=id, refs=self._resolved)
        item.update_config(config=new_config)

        # Generate final resolved value based on item type
        if isinstance(item, Component):
            self._resolved[id] = item.instantiate() if instantiate else item
        elif isinstance(item, Expression):
            self._resolved[id] = item.evaluate(globals={f"{self._vars}": self._resolved}) if eval_expr else item
        else:
            self._resolved[id] = new_config

        return self._resolved[id]

    @classmethod
    def normalize_id(cls, id: str | int) -> str:
        """Normalize ID to string format.

        Args:
            id: ID to normalize

        Returns:
            String ID
        """
        return str(id)

    @classmethod
    def split_id(cls, id: str | int, last: bool = False) -> list[str]:
        """Split ID string by separator.

        Args:
            id: ID to split
            last: If True, only split rightmost part

        Returns:
            List of ID components
        """
        if not last:
            return cls.normalize_id(id).split(cls.sep)
        res = cls.normalize_id(id).rsplit(cls.sep, 1)
        return ["".join(res[:-1]), res[-1]]

    @classmethod
    def iter_subconfigs(cls, id: str, config: Any) -> Iterator[tuple[str, str, Any]]:
        """Iterate over sub-configs with IDs.

        Args:
            id: Current ID path
            config: Config to iterate (dict or list)

        Yields:
            Tuples of (key, sub_id, value)
        """
        for k, v in config.items() if isinstance(config, dict) else enumerate(config):
            sub_id = f"{id}{cls.sep}{k}" if id != "" else f"{k}"
            yield k, sub_id, v

    @classmethod
    def match_refs_pattern(cls, value: str) -> dict[str, int]:
        """Find reference patterns in a string.

        Args:
            value: String to search for references

        Returns:
            Dict mapping reference IDs to occurrence counts
        """
        value = normalize_id(value)
        return scan_references(value)

    @classmethod
    def update_refs_pattern(cls, value: str, refs: dict) -> str:
        """Replace reference patterns with resolved values.

        Args:
            value: String containing references
            refs: Dict of resolved references

        Returns:
            String with references replaced
        """
        value = normalize_id(value)

        try:
            return replace_references(value, refs, cls._vars)
        except KeyError as e:
            # Extract reference ID from error message
            # The error message format is: "Reference '@ref_id' not found in resolved references"
            ref_id = str(e).split("'")[1].lstrip("@")
            msg = f"can not find expected ID '{ref_id}' in the references."
            if not cls.allow_missing_reference:
                raise KeyError(msg) from e
            warnings.warn(msg, stacklevel=2)
            return value

    @classmethod
    def find_refs_in_config(cls, config: Any, id: str, refs: dict[str, int] | None = None) -> dict[str, int]:
        """Recursively find all references in config.

        Args:
            config: Config to search
            id: Current ID path
            refs: Accumulated references dict

        Returns:
            Dict of reference IDs to counts
        """
        refs_ = refs or {}

        # Check string values for reference patterns
        if isinstance(config, str):
            for ref_id, count in cls.match_refs_pattern(value=config).items():
                refs_[ref_id] = refs_.get(ref_id, 0) + count

        # Recursively search nested structures
        if isinstance(config, (list, dict)):
            for _, sub_id, v in cls.iter_subconfigs(id, config):
                # Instantiable and expression items are also dependencies
                if (Component.is_instantiable(v) or Expression.is_expression(v)) and sub_id not in refs_:
                    refs_[sub_id] = 1
                refs_ = cls.find_refs_in_config(v, sub_id, refs_)

        return refs_

    @classmethod
    def update_config_with_refs(cls, config: Any, id: str, refs: dict | None = None) -> Any:
        """Update config by replacing references with resolved values.

        Args:
            config: Config to update
            id: Current ID path
            refs: Dict of resolved references

        Returns:
            Config with references replaced
        """
        refs_ = refs or {}

        # Replace references in strings
        if isinstance(config, str):
            return cls.update_refs_pattern(config, refs_)

        # Return non-container types as-is
        if not isinstance(config, (list, dict)):
            return config

        # Recursively update nested structures
        ret = type(config)()
        for idx, sub_id, v in cls.iter_subconfigs(id, config):
            if Component.is_instantiable(v) or Expression.is_expression(v):
                updated = refs_[sub_id]
                # Skip disabled components
                if Component.is_instantiable(v) and updated is None:
                    continue
            else:
                updated = cls.update_config_with_refs(v, sub_id, refs_)

            if isinstance(ret, dict):
                ret[idx] = updated
            else:
                ret.append(updated)

        return ret
