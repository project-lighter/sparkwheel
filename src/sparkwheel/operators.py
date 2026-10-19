"""Applying configuration changes: `key` sets, `+key` combines, `~key` deletes.

A file, dict or override is a list of statements applied in order to the config:

- ``key: value`` sets ``key`` to ``value``, whatever it held before.
- ``+key: value`` combines ``value`` with what ``key`` holds: a dict merges into a dict, all the way down;
  a list is appended to a list. On a missing or null key it sets.
- ``~key`` deletes ``key``; ``~key: [items]`` deletes indices of a list or keys of a dict.

Keys may be ``::`` paths (``model::optimizer::lr: 0.01``), which set one value deep inside.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .locations import LocationRegistry
    from .utils.exceptions import Location

from .path_utils import split_id
from .utils.constants import COMBINE_KEY, ID_SEP_KEY, REMOVE_KEY
from .utils.exceptions import ConfigKeyError, ConfigMergeError, build_missing_key_error

__all__ = ["apply_operators", "split_operator", "_validate_delete_operator", "MergeContext"]

_REMOVED_REPLACE_KEY = "="  # the replace operator of Sparkwheel < 0.1


@dataclass
class MergeContext:
    """Where a change is being applied, for error messages and source locations.

    Attributes:
        locations: Locations of the incoming statements (e.g. the file being applied)
        existing: Locations of the config being changed; stale entries are removed as values are replaced
        current_path: Path of the value being changed, using ``::`` (e.g. ``"model::optimizer"``)
    """

    locations: "LocationRegistry | None" = None
    existing: "LocationRegistry | None" = None
    current_path: str = ""

    def child_path(self, key: str) -> "MergeContext":
        """Context for a key under the current path.

        Examples:
            >>> MergeContext(current_path="model").child_path("optimizer").current_path
            'model::optimizer'
        """
        new_path = f"{self.current_path}{ID_SEP_KEY}{key}" if self.current_path else key
        return MergeContext(locations=self.locations, existing=self.existing, current_path=new_path)

    def get_source_location(self, key: str) -> "Location | None":
        """Location of the statement ``key`` (with or without its operator) under the current path."""
        if not self.locations:
            return None
        for name in (key, key.lstrip(COMBINE_KEY + REMOVE_KEY)):
            location = self.locations.get(f"{self.current_path}{ID_SEP_KEY}{name}" if self.current_path else name)
            if location:
                return location
        return None


def split_operator(key: str) -> tuple[str, str]:
    """Split a statement key into its operator (``""``, ``"+"`` or ``"~"``) and its path.

    Raises:
        ConfigMergeError: For the removed ``=key`` operator.
    """
    if key.startswith(_REMOVED_REPLACE_KEY):
        raise ConfigMergeError(
            f"'{key}': the '=' operator was removed in Sparkwheel 0.1",
            suggestion=f"Writing a key now replaces its value: write '{key[1:]}' instead.",
        )
    if key.startswith((COMBINE_KEY, REMOVE_KEY)):
        return key[0], key[1:]
    return "", key


def _validate_delete_operator(key: str, value: Any) -> None:
    """Validate the value of ``~key``: null, empty, or a non-empty list.

    Raises:
        ConfigMergeError: If the value is anything else
    """
    if value is not None and value != "" and not isinstance(value, list):
        raise ConfigMergeError(
            f"Remove operator '~{key}' must have null, empty, or list value",
            suggestion=f"The '~' prefix removes keys/items and accepts:\n"
            f"- null or empty: remove the entire key\n"
            f"- list: remove specific items (indices for lists, keys for dicts)\n\n"
            f"To remove the entire '{key}':\n"
            f"  ~{key}: null\n\n"
            f"To remove specific items from a list:\n"
            f"  ~{key}: [0, 2, 4]  # Remove indices 0, 2, 4\n\n"
            f"To remove specific keys from a dict:\n"
            f"  ~{key}: [\"train\", \"test\"]  # Remove keys 'train' and 'test'\n\n"
            f"To remove a nested key:\n"
            f"  ~{key}::nested: null",
        )
    if isinstance(value, list) and len(value) == 0:
        raise ConfigMergeError(
            f"Remove operator '~{key}' with list value cannot be empty",
            suggestion=f"Either provide indices/keys to remove, or use null to remove the entire key.\n\n"
            f"To remove the entire key:\n"
            f"  ~{key}: null\n\n"
            f"To remove specific items:\n"
            f"  ~{key}: [0, 1]  # For lists (indices)\n"
            f'  ~{key}: ["key1", "key2"]  # For dicts (keys)',
        )


def apply_operators(
    base: dict[str, Any],
    statements: dict[str, Any],
    context: MergeContext | None = None,
) -> dict[str, Any]:
    """Apply ``statements`` to a copy of ``base``: ``key`` sets, ``+key`` combines, ``~key`` deletes.

    Args:
        base: The config to change (not modified)
        statements: The changes, applied in order; keys may be ``::`` paths
        context: Source locations, for error messages

    Returns:
        The changed config

    Raises:
        ConfigMergeError: If an operator cannot be applied
        ConfigKeyError: If a path goes through a value that is not a mapping or list

    Examples:
        >>> apply_operators({"model": {"lr": 0.1, "depth": 4}}, {"model": {"lr": 0.01}})
        {'model': {'lr': 0.01}}
        >>> apply_operators({"model": {"lr": 0.1, "depth": 4}}, {"+model": {"lr": 0.01}})
        {'model': {'lr': 0.01, 'depth': 4}}
        >>> apply_operators({"model": {"lr": 0.1, "depth": 4}}, {"model::lr": 0.01})
        {'model': {'lr': 0.01, 'depth': 4}}
        >>> apply_operators({"milestones": [10]}, {"+milestones": [20]})
        {'milestones': [10, 20]}
        >>> apply_operators({"a": 1, "b": 2}, {"~b": None})
        {'a': 1}
    """
    result = deepcopy(base) if isinstance(base, dict) else {}
    _apply_statements(result, statements, context or MergeContext(), deep=False)
    return result


def _apply_statements(target: dict[str, Any], statements: dict[str, Any], context: MergeContext, deep: bool) -> None:
    """Apply each statement to ``target`` in place. ``deep``: a plain dict merges into a dict (inside ``+``)."""
    for key, value in statements.items():
        if not isinstance(key, str):
            target[key] = _fresh(value, context.child_path(str(key)))  # type: ignore[unreachable]
            continue
        operator, path = split_operator(key)
        *parents, name = split_id(path)
        container = _walk(target, parents, context, create=operator != REMOVE_KEY, statement=key)
        here = context.child_path(path)
        if isinstance(container, list):
            index = _list_index(container, name, here.current_path)
            name = index  # type: ignore[assignment]
            exists = True
        else:
            exists = name in container
        existing = container[name] if exists else None

        if operator == REMOVE_KEY:
            _validate_delete_operator(path, value)
            if not exists:
                available = [str(k) for k in container] if isinstance(container, dict) else []
                parent = ID_SEP_KEY.join(filter(None, [context.current_path, *parents])) or None
                raise build_missing_key_error(name, available, context.get_source_location(key), parent_key=parent)
            _delete(container, name, value, here, context.get_source_location(key))
        elif operator == COMBINE_KEY or (
            deep and isinstance(value, dict) and (existing is None or isinstance(existing, dict))
        ):
            container[name] = _combine(existing, value, here, context.get_source_location(key))
        else:
            _check_component(existing, value, here.current_path, context.get_source_location(key))
            if here.existing is not None:
                here.existing.remove_tree(here.current_path)
            container[name] = _fresh(value, here)


def _walk(target: Any, parents: list[str], context: MergeContext, create: bool, statement: str) -> Any:
    """Follow ``parents`` from ``target``, creating missing (or null) dicts when ``create``."""
    node = target
    for depth, key in enumerate(parents):
        here = ID_SEP_KEY.join(filter(None, [context.current_path, *parents[: depth + 1]]))
        if isinstance(node, list):
            node = node[_list_index(node, key, here)]
            continue
        if node.get(key) is None:
            if not create:
                parent = ID_SEP_KEY.join(filter(None, [context.current_path, *parents[:depth]])) or None
                raise build_missing_key_error(
                    key, [str(k) for k in node], context.get_source_location(statement), parent_key=parent
                )
            node[key] = {}
        if not isinstance(node[key], (dict, list)):
            raise ConfigKeyError(
                f"Cannot set '{statement.lstrip(COMBINE_KEY + REMOVE_KEY)}': '{here}' is {node[key]!r}, not a mapping",
                source_location=context.get_source_location(statement),
                suggestion=f"To replace the value, set '{here}' itself.",
            )
        node = node[key]
    return node


def _list_index(items: list, key: str, path: str) -> int:
    """The index ``key`` names in ``items``."""
    if key.lstrip("-").isdigit() and -len(items) <= int(key) < len(items):
        return int(key)
    raise ConfigKeyError(f"Cannot change '{path}': '{key}' is not an index of a list of {len(items)}")


def _fresh(value: Any, context: MergeContext) -> Any:
    """A copy of a set value. Its ``::`` keys become nested dicts; operators inside it are an error."""
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for key in value:
            if isinstance(key, str) and key.startswith((COMBINE_KEY, REMOVE_KEY)):
                raise ConfigMergeError(
                    f"'{context.current_path}' is set, so '{key}' inside it has nothing to "
                    f"{'combine with' if key.startswith(COMBINE_KEY) else 'delete'}",
                    source_location=context.get_source_location(key),
                    suggestion=f"Write '+{context.current_path.rsplit(ID_SEP_KEY, 1)[-1]}' to change "
                    f"'{context.current_path}' instead of replacing it.",
                )
        _apply_statements(result, value, MergeContext(context.locations, None, context.current_path), deep=False)
        return result
    if isinstance(value, list):
        return [_fresh(item, context.child_path(str(i))) for i, item in enumerate(value)]
    return deepcopy(value)


def _combine(existing: Any, value: Any, context: MergeContext, location: "Location | None") -> Any:
    """``+key``: merge a dict into a dict, all the way down, or append a list to a list."""
    path = context.current_path
    if existing is None:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            _apply_statements(result, value, context, deep=True)
            return result
        return _fresh(value, context)
    if isinstance(existing, dict) and isinstance(value, dict):
        if context.locations is not None:
            context.locations.pop(path)  # errors about the dict keep pointing at where it was defined
        _apply_statements(existing, value, context, deep=True)
        return existing
    if isinstance(existing, list) and isinstance(value, list):
        if context.locations is not None:
            context.locations.shift(path, len(existing))
        return existing + [_fresh(item, context.child_path(str(len(existing) + i))) for i, item in enumerate(value)]
    kind: dict[type, str] = {dict: "a mapping", list: "a list"}
    if isinstance(existing, list):
        suggestion = f"To append one item, write it as a list: '+{path.rsplit(ID_SEP_KEY, 1)[-1]}: [{value!r}]'."
    else:
        suggestion = f"To replace '{path}', drop the '+'."
    raise ConfigMergeError(
        f"Cannot combine '{path}': it is {kind.get(type(existing), repr(existing))}, "
        f"and '+' adds {kind.get(type(value), repr(value))}",
        source_location=location,
        suggestion=suggestion,
    )


def _check_component(existing: Any, value: Any, path: str, location: "Location | None") -> None:
    """Setting a component to a dict without ``_target_`` drops its class: almost always a missing ``+``."""
    if not (isinstance(existing, dict) and "_target_" in existing and isinstance(value, dict)):
        return
    if "_target_" in value:
        return
    name = path.rsplit(ID_SEP_KEY, 1)[-1]
    dropped = [str(k) for k in existing if k not in value]
    first = next(iter(value), "key")
    raise ConfigMergeError(
        f"'{path}' replaces the component {existing['_target_']!r} and drops {', '.join(map(repr, dropped))}",
        source_location=location,
        suggestion=f"To change only these keys, write '+{name}' instead of '{name}', or set them one by one "
        f"('{path}::{first}').",
    )


def _delete(container: Any, name: Any, value: Any, context: MergeContext, location: "Location | None") -> None:
    """``~key``: delete ``container[name]``, or the listed indices or keys of it."""
    path = context.current_path
    if value is None or value == "":
        if context.existing is not None:
            context.existing.remove_tree(path)
        del container[name]
        return
    current = container[name]
    if isinstance(current, list):
        indices = []
        for idx in value:
            if not isinstance(idx, int):
                raise ConfigMergeError(
                    f"Cannot remove from list '{path}': index must be integer, got {type(idx).__name__}",
                    source_location=location,
                    suggestion=f"When removing from a list, provide integer indices.\n\n"
                    f"Example:\n"
                    f"  ~{path}: [0, 2, 4]  # Remove items at indices 0, 2, 4\n"
                    f"  ~{path}: [-1]       # Remove last item",
                )
            if idx >= len(current) or idx < -len(current):
                raise ConfigMergeError(
                    f"Cannot remove from list '{path}': index {idx} out of range (list has {len(current)} items)",
                    source_location=location,
                    suggestion=f"Valid indices are 0 to {len(current) - 1}, or -{len(current)} to -1.\n"
                    f"Use null to remove the entire list:\n"
                    f"  ~{path}: null",
                )
            indices.append(idx % len(current))
        for idx in sorted(set(indices), reverse=True):
            del current[idx]
    elif isinstance(current, dict):
        for key in value:
            if key not in current:
                raise build_missing_key_error(key, list(current), location, parent_key=path)
            del current[key]
    else:
        raise ConfigMergeError(
            f"Cannot remove items from '{path}': expected list or dict, got {type(current).__name__}",
            source_location=location,
            suggestion=f"Item removal with '~{path}: [...]' only works for lists and dicts.\n"
            f"To remove the entire key:\n"
            f"  ~{path}: null",
        )
