"""Configuration merging with merge (+) and delete (~) operator support."""

from copy import deepcopy
from typing import Any

from .utils.constants import DELETE_KEY, MERGE_KEY
from .utils.exceptions import ConfigMergeError

__all__ = ["apply_operators", "_validate_delete_operator"]


def _contains_operator(config: Any) -> bool:
    """Check if a config contains any merge (+) or delete (~) operators.

    Used for implicit propagation: if a nested value has + or ~,
    parent dicts automatically merge instead of replace.

    Args:
        config: Config value to check (dict, list, or primitive)

    Returns:
        True if config contains keys with + or ~ prefix
    """
    if not isinstance(config, dict):
        return False

    for key in config.keys():
        if isinstance(key, str) and (key.startswith(MERGE_KEY) or key.startswith(DELETE_KEY)):
            return True
        if _contains_operator(config[key]):
            return True

    return False


def _validate_delete_operator(key: str, value: Any) -> None:
    """Validate delete operator value.

    Args:
        key: The key name (without ~ prefix)
        value: The value provided with ~key

    Raises:
        ConfigMergeError: If value is not null or empty
    """
    if value is not None and value != "":
        raise ConfigMergeError(
            f"Delete operator '~{key}' must have null or empty value",
            suggestion=f"The '~' prefix deletes a key and requires null or empty value.\n"
            f"The value is ignored, so only null or empty is allowed.\n\n"
            f"Did you mean to delete a nested key?\n\n"
            f"To delete the entire '{key}' key:\n"
            f"  ~{key}: null\n"
            f"  # or\n"
            f"  ~{key}:\n\n"
            f"To delete a nested key:\n"
            f"  {key}:\n"
            f"    nested:\n"
            f"      ~child: null\n\n"
            f"Or use path notation:\n"
            f"  ~{key}::nested::child: null",
        )


def apply_operators(base: dict, override: dict, _in_merge_context: bool = False) -> dict:
    """Apply configuration changes with merge (+) and delete (~) operators.

    Operators control merge behavior at any nesting level:
        +key: value   - Merge operator: merge with existing key (dicts merge recursively, lists append)
        ~key: null    - Delete operator: delete existing key from base
        key: value    - Replace (default, but implicit propagation may apply)

    Implicit Propagation:
        When a nested key has + or ~, parent dicts automatically merge instead of replace.
        Example: {"model": {"optimizer": {"+lr": 0.01}}} merges model and optimizer,
        even without explicit + prefix, because a nested key has an operator.

    Args:
        base: Base configuration dict
        override: Override configuration dict with optional +/~ operators
        _in_merge_context: Internal flag for implicit merge mode

    Returns:
        Merged configuration dict

    Raises:
        ConfigMergeError: If operators are used incorrectly

    Examples:
        >>> # Merge operator - preserves other keys
        >>> base = {"a": 1, "b": {"x": 1, "y": 2}}
        >>> override = {"b": {"+x": 10, "z": 3}}
        >>> apply_operators(base, override)
        {"a": 1, "b": {"x": 10, "y": 2, "z": 3}}

        >>> # Delete operator
        >>> base = {"a": 1, "b": 2, "c": 3}
        >>> override = {"~b": None}
        >>> apply_operators(base, override)
        {"a": 1, "c": 3}

        >>> # List append with merge operator
        >>> base = {"plugins": ["logger", "metrics"]}
        >>> override = {"+plugins": ["cache"]}
        >>> apply_operators(base, override)
        {"plugins": ["logger", "metrics", "cache"]}
    """
    if not isinstance(base, dict) or not isinstance(override, dict):
        return deepcopy(override)

    result = deepcopy(base)

    for key, value in override.items():
        if not isinstance(key, str):
            result[key] = deepcopy(value)
            continue

        # Process delete operator (~key)
        if key.startswith(DELETE_KEY):
            actual_key = key[1:]
            _validate_delete_operator(actual_key, value)

            if actual_key not in result:
                raise ConfigMergeError(
                    f"Cannot delete non-existent key '{actual_key}'",
                    suggestion=f"The '~' prefix deletes existing keys from configuration.\n"
                    f"Either remove '~{actual_key}' or check if the key name is correct.",
                )

            del result[actual_key]
            continue

        # Process merge operator (+key)
        if key.startswith(MERGE_KEY):
            actual_key = key[1:]

            if actual_key not in result:
                raise ConfigMergeError(
                    f"Cannot merge into non-existent key '{actual_key}'",
                    suggestion=f"The '+' prefix merges values into existing keys.\n"
                    f"To create a new key, use '{actual_key}' without the '+' prefix.\n\n"
                    f"Change '+{actual_key}:' to '{actual_key}:'",
                )

            base_val = result[actual_key]
            both_dicts = isinstance(base_val, dict) and isinstance(value, dict)
            both_lists = isinstance(base_val, list) and isinstance(value, list)

            if both_dicts:
                result[actual_key] = apply_operators(base_val, value, _in_merge_context=True)
            elif both_lists:
                result[actual_key] = base_val + value
            else:
                base_type = type(base_val).__name__
                override_type = type(value).__name__
                raise ConfigMergeError(
                    f"Cannot merge '+{actual_key}': type mismatch",
                    suggestion=f"Base value is {base_type}, override value is {override_type}.\n"
                    f"The '+' prefix only works when both values are dicts (merge) or lists (append).\n"
                    f"To replace with a different type, remove the '+' prefix.\n\n"
                    f"Change '+{actual_key}:' to '{actual_key}:'",
                )
            continue

        # No operator - check for implicit propagation
        should_merge = _in_merge_context or _contains_operator(value)

        if should_merge and key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Implicit merge due to nested operator
            result[key] = apply_operators(result[key], value, _in_merge_context=True)
        else:
            # Default: replace
            result[key] = deepcopy(value)

    return result
