"""Resolve references between Items."""

import warnings
from collections.abc import Iterator
from copy import copy
from typing import Any

from .items import Component, Expression, Item
from .operators import _copy_containers
from .path_utils import normalize_id, replace_references, scan_references
from .utils import allow_missing_reference, look_up_option
from .utils.constants import ID_SEP_KEY, RESOLVED_REF_KEY
from .utils.exceptions import CircularReferenceError, ConfigKeyError

__all__ = ["Resolver"]


class _ExpressionReferences:
    """Resolve Python-selected references within one immutable build generation."""

    def __init__(self, resolver: "Resolver", path: str, waiting: set[str], depth: int, mode: tuple[bool, bool]):
        self._resolver = resolver
        self._path = path
        self._waiting = waiting | {path}
        self._depth = depth
        self._mode = mode
        self._cache = resolver._resolved_by_mode[mode]

    def __getitem__(self, path: str) -> Any:
        if path not in self._cache and path in self._waiting:
            item = self._resolver._items.get(self._path)
            raise CircularReferenceError(
                f"Circular reference detected: '{path}' references back to '{self._path}'",
                source_location=item.source_location if item is not None else None,
            )
        return self._resolver._resolve_one_item(
            path,
            waiting_list=set(self._waiting),
            _depth=self._depth + 1,
            instantiate=self._mode[0],
            eval_expr=self._mode[1],
        )


class Resolver:
    """Resolve references between Items.

    Manages Items and resolves resolved reference strings (starting with @) by
    substituting them with their corresponding resolved values (instantiated objects,
    evaluated expressions, etc.).

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

    Resolved references can use :: separator for nested access:
    - Dictionary keys: @config::key::subkey
    - List indices: @list::0::subitem
    """

    _vars = "__local_refs"  # Variable name for resolved refs in expression evaluation
    sep = ID_SEP_KEY  # Separator for nested key access
    ref = RESOLVED_REF_KEY  # Resolved reference prefix (@)
    allow_missing_reference = allow_missing_reference
    max_resolution_depth = 100  # Prevent DoS from deeply nested references

    def __init__(self, items: list[Item] | None = None):
        """Initialize resolver with optional items.

        Args:
            items: Optional list of Items to add during initialization
        """
        self._items: dict[str, Item] = {}
        # Keep the default cache available for existing internal integrations.
        self._resolved: dict[str, Any] = {}
        self._resolved_by_mode: dict[tuple[bool, bool], dict[str, Any]] = {(True, True): self._resolved}
        self._guard_states: dict[tuple[bool, bool], dict[str, bool]] = {}
        self._resolution_mode = (True, True)
        self._current_path = ""
        self._active_resolutions: dict[tuple[bool, bool], set[str]] = {}

        if items:
            for item in items:
                self.add_item(item)

    def reset(self) -> None:
        """Clear all items and resolved content."""
        self._items = {}
        self._resolved = {}
        self._resolved_by_mode = {(True, True): self._resolved}
        self._guard_states = {}
        self._active_resolutions = {}

    def is_resolved(self) -> bool:
        """Check if any items have been resolved."""
        return any(self._resolved_by_mode.values())

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
        """Get the registered Item by id, optionally populating the resolution cache.

        Args:
            id: ID of the config item
            resolve: Whether to resolve the item (default: False)
            **kwargs: Additional arguments for resolution

        Returns:
            The original Item if found, None otherwise. Use resolve() for its resolved value.
        """
        id = self.normalize_id(id)
        if resolve:
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
        evaluates expressions (if requested). Each (instantiate, eval_expr) pair
        has a separate cache. Repeated calls in the same mode share resolved objects,
        including after calls in a different mode.

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
        """Track active graph construction, including escaped Python callbacks."""
        path = self.normalize_id(id)
        mode = (instantiate, eval_expr)
        if path in self._resolved_by_mode.get(mode, {}):
            return self._resolve_item(path, waiting_list, _depth, instantiate, eval_expr, default)
        active = self._active_resolutions.setdefault(mode, set())
        if path in active:
            item = self._items.get(path)
            raise CircularReferenceError(
                f"Circular reference detected while constructing '{path}'",
                source_location=item.source_location if item is not None else None,
            )
        active.add(path)
        try:
            return self._resolve_item(path, waiting_list, _depth, instantiate, eval_expr, default)
        finally:
            active.discard(path)

    def _resolve_item(
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

        self._resolution_mode = (instantiate, eval_expr)
        resolved = self._resolved_by_mode.setdefault(self._resolution_mode, {})

        # Return cached result if available
        if id in resolved:
            return resolved[id]

        self._prepare_item(id)

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

        if isinstance(item, Component):
            disabled = self._literal_disabled(item_config)
            guard = item_config.get("_disabled_", False)
            if disabled is None:
                guard_id = f"{id}::_disabled_" if id else "_disabled_"
                self._prepare_item(guard_id)
                guard = self._resolve_one_item(
                    guard_id, waiting_list, _depth + 1, instantiate=instantiate, eval_expr=eval_expr
                )
                waiting_list.discard(guard_id)
                if not eval_expr and isinstance(guard, Item):
                    # The guard cannot be decided in this mode. Preserve its
                    # wrapper without constructing or touching the payload.
                    result = copy(item)
                    config = _copy_containers(item_config)
                    config["_disabled_"] = guard
                    result.update_config(config)
                    resolved[id] = result
                    return result
                disabled = Component({"_disabled_": guard}).is_disabled()
            self._guard_states.setdefault(self._resolution_mode, {})[id] = disabled
            if disabled:
                if instantiate:
                    resolved[id] = None
                else:
                    result = copy(item)
                    config = _copy_containers(item_config)
                    config["_disabled_"] = guard
                    result.update_config(config)
                    resolved[id] = result
                return resolved[id]

        self._prepare_enabled_item(id, waiting_list, _depth, instantiate, eval_expr)
        # Import declarations in inactive component payloads stay inactive.
        self._current_path = id
        self._resolve_imports(resolved, eval_expr)

        if isinstance(item, Expression) and eval_expr:
            references = scan_references(item_config)
            prepared = copy(item)
            prepared.update_config(replace_references(item_config, dict.fromkeys(references), self._vars))
            values = _ExpressionReferences(self, id, waiting_list, _depth, (instantiate, eval_expr))
            expression_result = prepared.evaluate(globals={self._vars: values})
            self._publish_expression_references(set(references))
            resolved[id] = expression_result
            return expression_result

        # A nested component owns its argument dependencies and guard boundary.
        refs = self._dependency_refs(config=item_config, id=id)

        # Resolve dependencies first
        for dep_id in refs.keys():
            # Check for circular references
            if dep_id in waiting_list:
                raise CircularReferenceError(
                    f"Circular reference detected: '{dep_id}' references back to '{id}'",
                    source_location=item.source_location if hasattr(item, "source_location") else None,
                )

            # Resolve dependency if not already resolved
            if dep_id not in resolved:
                self._prepare_item(dep_id)
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
        new_config = self._substitute_refs(config=item_config, id=id, refs=resolved)
        # Replacing references is mode-specific. Keep the registered definition
        # intact so another mode never inherits instantiated objects or wrappers.
        # A shallow copy retains opaque Python inputs without cloning them;
        # update_config_with_refs has already rebuilt the config containers.
        item = copy(item)
        item.update_config(config=new_config)

        # Generate final resolved value based on item type
        if isinstance(item, Component):
            resolved[id] = item.instantiate() if instantiate else item
        elif isinstance(item, Expression):
            resolved[id] = item.evaluate(globals={f"{self._vars}": resolved}) if eval_expr else item
        else:
            resolved[id] = new_config

        return resolved[id]

    def _publish_expression_references(self, paths: set[str]) -> None:
        """Extension point for conservative binding ownership after publication."""

    def _prepare_item(self, id: str) -> None:
        """Extension point for scoped, on-demand definitions."""

    def _prepare_enabled_item(self, id: str, waiting_list: set[str], depth: int, instantiate: bool, eval_expr: bool) -> None:
        """Extension point after a component's guard permits argument work."""

    def _resolve_imports(self, resolved: dict[str, Any], eval_expr: bool) -> None:
        for id, item in self._items.items():
            if (
                id not in resolved
                and isinstance(item, Expression)
                and item.is_import_statement(item.get_config())
                and self._import_visible(id)
            ):
                self._resolve_import_item(item, id, resolved, eval_expr)

    @staticmethod
    def _resolve_import_item(item: Expression, id: str, resolved: dict[str, Any], eval_expr: bool) -> None:
        if not eval_expr:
            # Each requested wrapper still needs ordinary dependency preparation;
            # global declaration discovery must not cache untouched definitions.
            return
        imported = item.load_imports()
        if item.is_import_only():
            resolved[id] = imported

    @staticmethod
    def _literal_disabled(config: Any) -> bool | None:
        """Return a literal guard state without calling opaque Python objects."""
        if not Component.is_instantiable(config):
            return False
        value = config.get("_disabled_", False)
        if type(value) is str:
            return None if value.startswith(("@", "$", "%")) else value.lower().strip() == "true"
        if Component.is_instantiable(value):
            return None
        if value is None or type(value) in (bool, int, float, complex, tuple, list, dict):
            return bool(value)
        return None

    @classmethod
    def _dependency_refs(cls, config: Any, id: str) -> dict[str, int]:
        """Discover immediate graph dependencies, preserving component guards."""
        if Component.is_instantiable(config) and cls._literal_disabled(config) is True:
            return {}
        if isinstance(config, str):
            return cls.match_refs_pattern(config)
        refs: dict[str, int] = {}
        if isinstance(config, (dict, list)):
            for _, path, value in cls.iter_subconfigs(id, config):
                if Component.is_instantiable(value) or Expression.is_expression(value):
                    refs[path] = refs.get(path, 0) + 1
                else:
                    for dependency, count in cls._dependency_refs(value, path).items():
                        refs[dependency] = refs.get(dependency, 0) + count
        return refs

    def _import_visible(self, path: str) -> bool:
        """Only collect imports from enabled components or the requested subtree."""
        parts = path.split(self.sep)
        states = self._guard_states.get(self._resolution_mode, {})
        for length in range(len(parts)):
            parent = self.sep.join(parts[:length])
            item = self._items.get(parent)
            if not isinstance(item, Component):
                continue
            state = states.get(parent, self._literal_disabled(item.get_config()))
            if state is False:
                continue
            # A requested descendant is independent of its disabled parent;
            # imports must still belong to that explicitly requested subtree.
            inside_parent = self._current_path != parent and (not parent or self._current_path.startswith(parent + self.sep))
            inside_request = path == self._current_path or path.startswith(self._current_path + self.sep)
            if not (inside_parent and inside_request):
                return False
        return True

    def _substitute_refs(self, config: Any, id: str, refs: dict[str, Any]) -> Any:
        return self.update_config_with_refs(config=config, id=id, refs=refs)

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
            yield k, sub_id, v  # type: ignore[misc]

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
    def update_refs_pattern(cls, value: str, refs: dict[str, Any]) -> str:
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
    def update_config_with_refs(cls, config: Any, id: str, refs: dict[str, Any] | None = None) -> Any:
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
