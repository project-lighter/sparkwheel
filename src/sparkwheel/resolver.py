"""Resolve references between Items."""

import warnings
from collections.abc import Iterator
from copy import copy
from pydoc import ErrorDuringImport, locate
from typing import Any

from .errors import get_suggestions
from .items import Component, Expression, Item
from .path_utils import normalize_id, replace_references, scan_references
from .utils import CompInitMode, allow_missing_reference, look_up_option
from .utils.constants import EXPR_KEY, ID_SEP_KEY, RESOLVED_REF_KEY
from .utils.exceptions import (
    BaseError,
    CircularReferenceError,
    ConfigKeyError,
    InstantiationError,
    Location,
    TargetNotFoundError,
)

__all__ = ["Resolver"]


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

    _vars = Expression.refs_var  # Variable name for resolved refs in expression evaluation
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
        self._resolved: dict[str, Any] = {}
        # One cache per (instantiate, eval_expr) mode: a Component wrapper is never an instance.
        self._resolved_by_mode: dict[tuple[bool, bool], dict[str, Any]] = {(True, True): self._resolved}

        if items:
            for item in items:
                self.add_item(item)

    def reset(self) -> None:
        """Clear all items and resolved content."""
        self._items = {}
        self._resolved = {}
        self._resolved_by_mode = {(True, True): self._resolved}

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
        """Get Item by id, optionally resolved.

        Args:
            id: ID of the config item
            resolve: Whether to resolve the item (default: False)
            **kwargs: Additional arguments for resolution

        Returns:
            Item if found, None otherwise (or resolved value if resolve=True)
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
        resolved = self._resolved_by_mode.setdefault((instantiate, eval_expr), {})

        # Return cached result if available
        if id in resolved:
            return resolved[id]

        # Look up the item
        try:
            item = look_up_option(id, self._items, print_all_options=False, default=default or "no_default")
        except ValueError as err:
            # Point at the nearest existing parent (the id itself is not in any file)
            source_location = None
            parent_id = id
            while ID_SEP_KEY in parent_id and source_location is None:
                parent_id = parent_id.rsplit(ID_SEP_KEY, 1)[0]
                parent = self._items.get(parent_id)
                source_location = parent.source_location if isinstance(parent, Item) else None

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

        # A literally disabled component is skipped before its arguments are built
        if isinstance(item, Component) and self._disabled_flag(item_config):
            resolved[id] = None
            return None

        # First, resolve any import expressions (they need to run first)
        for t, v in self._items.items():
            if t not in resolved and isinstance(v, Expression) and v.is_import_statement(v.get_config()):
                resolved[t] = v.evaluate() if eval_expr else v

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
            if dep_id not in resolved:
                try:
                    look_up_option(dep_id, self._items, print_all_options=False)
                except ValueError as err:
                    msg = f"the referring item `@{dep_id}` is not defined in the config content."
                    if not self.allow_missing_reference:
                        available_keys = list(self._items.keys())
                        raise ConfigKeyError(
                            f"Reference '@{dep_id}' not found in configuration",
                            source_location=self._location_of_ref(id, dep_id) or item.source_location,
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
        if isinstance(item, Expression):
            # The expression looks up its `@` references itself, so errors show it as written
            resolved[id] = item.evaluate(globals={f"{self._vars}": resolved}) if eval_expr else item
            return resolved[id]

        # Resolve a copy of this item (the parsed item stays as authored)
        new_config = self.update_config_with_refs(config=item_config, id=id, refs=resolved)
        item = copy(item)
        item.update_config(config=new_config)
        if isinstance(item, Component):
            resolved[id] = item.instantiate() if instantiate else item
        else:
            resolved[id] = new_config

        return resolved[id]

    def _location_of_ref(self, id: str, ref_id: str) -> Location | None:
        """Location of the value under `id` that holds the reference `@ref_id`."""
        for sub_id, sub_item in self._items.items():
            in_subtree = sub_id == id or not id or sub_id.startswith(f"{id}{self.sep}")
            config = sub_item.get_config() if isinstance(sub_item, Item) else None
            if in_subtree and isinstance(config, str) and ref_id in self.match_refs_pattern(config):
                return sub_item.source_location
        return None

    @staticmethod
    def _disabled_flag(config: dict[str, Any]) -> bool | None:
        """A component's literal `_disabled_` value, or None when a reference or expression decides it at resolve time."""
        flag = config.get("_disabled_", False)
        if isinstance(flag, (dict, list)) or (isinstance(flag, str) and flag.startswith((EXPR_KEY, RESOLVED_REF_KEY))):
            return None
        return flag.lower().strip() == "true" if isinstance(flag, str) else bool(flag)

    def find_problems(self) -> list[BaseError]:
        """Find the mistakes resolving would raise, without building components or evaluating expressions.

        Checks that references exist, `_target_`s can be imported, components' arguments fit their target's
        signature and expressions compile. Components that are (or may be) disabled are skipped.
        """
        problems: list[BaseError] = []
        skipped = [
            id
            for id, item in self._items.items()
            if isinstance(item, Component) and self._checked_disabled_flag(item.get_config()) is not False
        ]
        for id, item in self._items.items():
            if any(id == s or id.startswith(f"{s}{self.sep}") for s in skipped):
                continue
            config = item.get_config()
            if isinstance(item, Component):
                problems.extend(self._component_problems(item))
            if not isinstance(config, str):
                continue
            if not self.allow_missing_reference:
                for ref_id in self.match_refs_pattern(config):
                    if ref_id not in self._items:
                        problems.append(
                            ConfigKeyError(
                                f"Reference '@{ref_id}' not found in configuration",
                                source_location=item.source_location,
                                missing_key=ref_id,
                                available_keys=list(self._items),
                            )
                        )
            if isinstance(item, Expression) and not item.is_import_statement(config):
                code = replace_references(config, dict.fromkeys(self.match_refs_pattern(config)), self._vars)
                code = code[len(EXPR_KEY) :].strip()
                try:
                    compile(code, "<expression>", "eval")
                except SyntaxError as e:
                    problems.append(item._evaluation_error(e, code))
        return problems

    def _checked_disabled_flag(self, config: dict[str, Any]) -> bool | None:
        """`_disabled_flag`, also when `_disabled_` references a plain value (`_disabled_: "@debug"`)."""
        flag = config.get("_disabled_")
        if isinstance(flag, str) and flag.startswith(RESOLVED_REF_KEY):
            target = self._items.get(flag[len(RESOLVED_REF_KEY) :])
            if type(target) is Item:  # neither a component nor an expression
                return self._disabled_flag({"_disabled_": target.get_config()})
        return self._disabled_flag(config)

    @staticmethod
    def _component_problems(item: Component) -> list[BaseError]:
        """An unknown `_mode_`, a `_target_` that cannot be imported, or arguments that do not fit its signature."""
        config = item.get_config()
        problems: list[BaseError] = []
        mode = config.get("_mode_", CompInitMode.DEFAULT)
        literal_mode = isinstance(mode, str) and not mode.startswith((EXPR_KEY, RESOLVED_REF_KEY))
        modes = [m.value for m in CompInitMode]
        if literal_mode and mode.strip() not in modes:
            close = get_suggestions(mode, modes, max_suggestions=1)
            problems.append(
                InstantiationError(
                    f"Unknown _mode_ '{mode}'",
                    source_location=item.location_of("_mode_"),
                    suggestion=(f"Did you mean '{close[0][0]}'? " if close else "") + f"Modes: {', '.join(modes)}.",
                )
            )
        target = config["_target_"]
        if not isinstance(target, str) or target.startswith((EXPR_KEY, RESOLVED_REF_KEY)):
            return problems  # decided at resolve time
        try:
            located = locate(target)
        except ErrorDuringImport as e:  # the module exists but raises when imported
            cause = getattr(e, "value", e)
            problem: BaseError = InstantiationError(
                f"Cannot import '{target}': {type(cause).__name__}: {cause}",
                source_location=item.location_of("_target_"),
            )
            return [*problems, problem]
        if located is None:
            problem = TargetNotFoundError(
                f"Cannot locate class or function: '{target}'",
                source_location=item.location_of("_target_"),
                suggestion=item._suggest_similar_modules(target),
            )
            return [*problems, problem]
        args = config.get("_args_", [])
        kwargs = {k: v for k, v in config.items() if k not in item.non_arg_keys}
        # Called now with only these arguments, a default-mode target must get every one it needs
        complete = literal_mode and mode.strip() == CompInitMode.DEFAULT and isinstance(args, list)
        return problems + item.argument_errors(
            located, args if isinstance(args, list) else [], kwargs, allow_missing=not complete
        )

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
                if Component.is_instantiable(v) and cls._disabled_flag(v):
                    continue  # a disabled component resolves to None, so nothing inside it is needed
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
