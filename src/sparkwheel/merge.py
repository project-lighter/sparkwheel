"""Configuration merging with +/~ directive support for fine-grained merge control."""

from copy import deepcopy
from typing import Any

from .exceptions import ConfigMergeError

__all__ = ["merge_configs"]


def _has_merge_directive(config: Any) -> bool:
    """Check if a config dict contains any + (merge) directives.

    This is used for implicit propagation - if a nested value has +,
    its parent should also be merged instead of replaced.

    Args:
        config: Config value to check (dict, list, or primitive)

    Returns:
        True if config is a dict containing keys with + prefix
    """
    if not isinstance(config, dict):
        return False

    # Check if any keys start with +
    for key in config.keys():
        if isinstance(key, str) and key.startswith('+'):
            return True
        # Recursively check nested dicts for + directives
        if _has_merge_directive(config[key]):
            return True

    return False


def merge_configs(base: dict, override: dict, _in_merge_context: bool = False) -> dict:
    """Merge two configuration dictionaries with +/~ directive support.

    Directives control merge behavior at any nesting level:
        +key: value   - MERGE with existing key (dicts merge recursively, lists append)
        ~key: null    - DELETE existing key from base
        key: value    - REPLACE (default, but implicit propagation applies if nested + exists)

    Validation:
        - `+` directive requires the key to exist and types to match:
          * Both values must be dicts (recursive merge) or lists (append)
          * Raises ConfigMergeError if key doesn't exist or types mismatch
        - `~` directive requires the key to exist:
          * Raises ConfigMergeError if key doesn't exist
        - These validations catch typos and config ordering issues early

    Implicit Propagation:
        When a nested key has +, parent keys automatically merge instead of replace.
        Example: {"model": {"optimizer": {"+nested": {...}}}} will merge model and optimizer,
        even though they don't have + prefix, because a nested key does.

    Args:
        base: Base configuration dict
        override: Override configuration dict with optional +/~ prefixes
        _in_merge_context: Internal flag tracking if we're in implicit merge mode

    Returns:
        Merged configuration dict

    Raises:
        ConfigMergeError: If + or ~ directives are used incorrectly

    Examples:
        >>> # Dict merge
        >>> base = {"a": 1, "b": {"x": 1, "y": 2}}
        >>> override = {"b": {"+x": 10, "z": 3}}
        >>> merge_configs(base, override)
        {"a": 1, "b": {"x": 10, "y": 2, "z": 3}}  # b is merged, not replaced

        >>> # List append
        >>> base = {"plugins": ["logger", "metrics"]}
        >>> override = {"+plugins": ["cache"]}
        >>> merge_configs(base, override)
        {"plugins": ["logger", "metrics", "cache"]}

        >>> # Delete key
        >>> base = {"a": 1, "b": 2, "c": 3}
        >>> override = {"~b": None}
        >>> merge_configs(base, override)
        {"a": 1, "c": 3}
    """
    if not isinstance(base, dict) or not isinstance(override, dict):
        # For non-dict values, override replaces base
        return deepcopy(override)

    result = deepcopy(base)

    for key, value in override.items():
        if isinstance(key, str):
            # Handle delete directive (~key)
            if key.startswith('~'):
                actual_key = key[1:]
                if actual_key not in result:
                    raise ConfigMergeError(
                        f"Cannot delete non-existent key '{actual_key}'",
                        suggestion=f"The '~' prefix deletes existing keys from configuration.\n"
                        f"Either remove '~{actual_key}' or check if the key name is correct.",
                    )
                del result[actual_key]
                continue

            # Handle merge directive (+key)
            if key.startswith('+'):
                actual_key = key[1:]

                # Validate that key exists
                if actual_key not in result:
                    raise ConfigMergeError(
                        f"Cannot merge into non-existent key '{actual_key}'",
                        suggestion=f"The '+' prefix merges values into existing keys.\n"
                        f"To create a new key, use '{actual_key}' without the '+' prefix.\n\n"
                        f"Change '+{actual_key}:' to '{actual_key}:'",
                    )

                # Check type compatibility
                base_is_dict = isinstance(result[actual_key], dict)
                base_is_list = isinstance(result[actual_key], list)
                value_is_dict = isinstance(value, dict)
                value_is_list = isinstance(value, list)

                if base_is_dict and value_is_dict:
                    # Both dicts: recursively merge
                    result[actual_key] = merge_configs(result[actual_key], value, _in_merge_context=True)
                elif base_is_list and value_is_list:
                    # Both lists: append/extend
                    result[actual_key] = result[actual_key] + value
                else:
                    # Type mismatch
                    base_type = type(result[actual_key]).__name__
                    override_type = type(value).__name__
                    raise ConfigMergeError(
                        f"Cannot merge '+{actual_key}': type mismatch",
                        suggestion=f"Base value is {base_type}, override value is {override_type}.\n"
                        f"The '+' prefix only works when both values are dicts (merge) or lists (append).\n"
                        f"To replace with a different type, remove the '+' prefix.\n\n"
                        f"Change '+{actual_key}:' to '{actual_key}:'",
                    )
                continue

        # No directive prefix - check for implicit propagation
        # If this value contains any + directives nested inside, we should merge instead of replace
        should_merge = _in_merge_context or _has_merge_directive(value)

        if should_merge and key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Implicit merge: recursively merge because parent or child has merge directive
            result[key] = merge_configs(result[key], value, _in_merge_context=True)
        else:
            # Default: replace
            result[key] = deepcopy(value)

    return result
