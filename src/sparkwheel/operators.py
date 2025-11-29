"""Configuration merging with composition-by-default and operators (=, ~)."""

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .locations import LocationRegistry
    from .utils.exceptions import Location

from .utils.constants import ID_SEP_KEY, REMOVE_KEY, REPLACE_KEY
from .utils.exceptions import ConfigMergeError, build_missing_key_error

__all__ = ["apply_operators", "validate_operators", "_validate_delete_operator", "MergeContext"]


@dataclass
class MergeContext:
    """Context for configuration merging operations.

    This class consolidates location tracking and path information needed
    during recursive config merging. Using a context object reduces parameter
    threading and makes it easier to extend with additional context in the future.

    Attributes:
        locations: Optional registry tracking file locations of config keys
        current_path: Current path in config tree using :: separator (e.g., "model::optimizer::lr")

    Examples:
        >>> ctx = MergeContext()
        >>> child_ctx = ctx.child_path("model")
        >>> child_ctx.current_path
        'model'
        >>> grandchild_ctx = child_ctx.child_path("lr")
        >>> grandchild_ctx.current_path
        'model::lr'
    """

    locations: "LocationRegistry | None" = None
    current_path: str = ""

    def child_path(self, key: str) -> "MergeContext":
        """Create a child context for a nested config key.

        Args:
            key: Key to append to current path

        Returns:
            New MergeContext with updated path, sharing the same source location registry

        Examples:
            >>> ctx = MergeContext(current_path="model")
            >>> child = ctx.child_path("optimizer")
            >>> child.current_path
            'model::optimizer'
        """
        new_path = f"{self.current_path}{ID_SEP_KEY}{key}" if self.current_path else key
        return MergeContext(locations=self.locations, current_path=new_path)

    def get_source_location(self, key: str) -> "Location | None":
        """Get source location for a key in the current context.

        Tries both the exact key and the key without operator prefix to handle
        operator keys correctly (e.g., ~key, =key).

        Args:
            key: Key to look up (may include operators like ~key or =key)

        Returns:
            Location if found, None otherwise

        Examples:
            >>> ctx = MergeContext(locations=registry, current_path="model")
            >>> ctx.get_source_location("~lr")  # Looks up both "model::~lr" and "model::lr"
            >>> ctx.get_source_location("=lr")  # Looks up both "model::=lr" and "model::lr"
        """
        if not self.locations:
            return None

        # Build full path for the key
        key_path = f"{self.current_path}{ID_SEP_KEY}{key}" if self.current_path else key

        # Try the key as-is first
        location = self.locations.get(key_path)
        if location:
            return location

        # If key starts with an operator (~, =), also try without the operator
        if key.startswith((REMOVE_KEY, REPLACE_KEY)):
            actual_key = key[1:]
            actual_path = f"{self.current_path}{ID_SEP_KEY}{actual_key}" if self.current_path else actual_key
            return self.locations.get(actual_path)

        return None


def _validate_delete_operator(key: str, value: Any) -> None:
    """Validate remove operator value.

    Args:
        key: The key name (without ~ prefix)
        value: The value provided with ~key

    Raises:
        ConfigMergeError: If value is not null, empty, or a list
    """
    # Allow null, empty string, or list
    if value is not None and value != "" and not isinstance(value, list):
        raise ConfigMergeError(
            f"Remove operator '~{key}' must have null, empty, or list value",
            suggestion=f"The '~' prefix removes keys/items and accepts:\n"
            f"- null or empty: remove the entire key\n"
            f"- list: remove specific items (indices for lists, keys for dicts)\n\n"
            f"To remove the entire '{key}':\n"
            f"  ~{key}: null\n"
            f"  # or\n"
            f"  ~{key}:\n\n"
            f"To remove specific items from a list:\n"
            f"  ~{key}: [0, 2, 4]  # Remove indices 0, 2, 4\n\n"
            f"To remove specific keys from a dict:\n"
            f"  ~{key}: [\"train\", \"test\"]  # Remove keys 'train' and 'test'\n\n"
            f"To remove a nested key:\n"
            f"  {key}:\n"
            f"    ~nested: null\n\n"
            f"Or use path notation:\n"
            f"  ~{key}::nested: null",
        )

    # Validate list is not empty
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


def validate_operators(config: dict[str, Any], parent_key: str = "") -> None:
    """Validate operator usage in config tree.

    With composition-by-default, validation is simpler:
    1. Remove operators error if key doesn't exist
    2. Replace operators work on any type
    3. No parent context requirements

    Args:
        config: Configuration dict to validate
        parent_key: Parent key path (for error messages)

    Raises:
        ConfigMergeError: If operator usage is invalid
    """
    if not isinstance(config, dict):
        return  # type: ignore[unreachable]

    for key, value in config.items():
        if not isinstance(key, str):
            continue  # type: ignore[unreachable]

        actual_key = key
        operator = None

        # Detect operator
        if key.startswith(REPLACE_KEY):
            actual_key = key[1:]
            operator = "replace"
        elif key.startswith(REMOVE_KEY):
            actual_key = key[1:]
            operator = "remove"

        full_key = f"{parent_key}::{actual_key}" if parent_key else actual_key

        # Validate remove operator
        if operator == "remove":
            _validate_delete_operator(actual_key, value)

        # Recurse into nested dicts
        if isinstance(value, dict) and operator != "remove":
            validate_operators(value, full_key)


def apply_operators(
    base: dict[str, Any],
    override: dict[str, Any],
    context: MergeContext | None = None,
) -> dict[str, Any]:
    """Apply configuration changes with composition-by-default semantics.

    Default behavior: Compose (merge dicts, extend lists)
    Operators:
        =key: value   - Replace operator: completely replace value (override default)
        ~key: null    - Remove operator: delete key or list items (errors if missing)
        key: value    - Compose (default): merge dict or extend list

    Composition-by-Default Philosophy:
        - Dicts merge recursively by default (preserves existing keys)
        - Lists extend by default (append new items)
        - Only scalars and type mismatches replace
        - Use = to explicitly replace entire dicts or lists
        - Use ~ to delete keys (errors if key doesn't exist)

    Args:
        base: Base configuration dict
        override: Override configuration dict with optional =/~ operators
        context: Optional merge context with metadata and path tracking

    Returns:
        Merged configuration dict

    Raises:
        ConfigMergeError: If operators are used incorrectly

    Examples:
        >>> # Default: Dicts merge
        >>> base = {"a": 1, "b": {"x": 1, "y": 2}}
        >>> override = {"b": {"x": 10}}
        >>> apply_operators(base, override)
        {"a": 1, "b": {"x": 10, "y": 2}}

        >>> # Default: Lists extend
        >>> base = {"plugins": ["logger", "metrics"]}
        >>> override = {"plugins": ["cache"]}
        >>> apply_operators(base, override)
        {"plugins": ["logger", "metrics", "cache"]}

        >>> # Replace operator: explicit override
        >>> base = {"model": {"lr": 0.001, "dropout": 0.1}}
        >>> override = {"=model": {"lr": 0.01}}
        >>> apply_operators(base, override)
        {"model": {"lr": 0.01}}

        >>> # Remove operator: delete key
        >>> base = {"a": 1, "b": 2, "c": 3}
        >>> override = {"b": 5, "~c": None}
        >>> apply_operators(base, override)
        {"a": 1, "b": 5}

        >>> # With context for better error messages
        >>> from .locations import LocationRegistry
        >>> ctx = MergeContext(locations=LocationRegistry())
        >>> apply_operators(base, override, context=ctx)
    """
    # Create context if not provided
    if context is None:
        context = MergeContext()

    if not isinstance(base, dict) or not isinstance(override, dict):
        return deepcopy(override)  # type: ignore[unreachable]

    result = deepcopy(base)

    for key, value in override.items():
        if not isinstance(key, str):
            result[key] = deepcopy(value)  # type: ignore[unreachable]
            continue

        # Process replace operator (=key)
        if key.startswith(REPLACE_KEY):
            actual_key = key[1:]
            result[actual_key] = deepcopy(value)
            continue

        # Process remove operator (~key)
        if key.startswith(REMOVE_KEY):
            actual_key = key[1:]
            _validate_delete_operator(actual_key, value)

            # Error if key doesn't exist
            if actual_key not in result:
                # Get source location using context helper
                source_location = context.get_source_location(key)
                raise build_missing_key_error(actual_key, list(result.keys()), source_location)

            # Handle remove entire key (null or empty value)
            if value is None or value == "":
                del result[actual_key]
                continue

            # Handle remove specific items from list or dict (list value)
            if isinstance(value, list):
                base_val = result[actual_key]

                # Remove from list by indices
                if isinstance(base_val, list):
                    list_len = len(base_val)

                    # Validate all items are integers and normalize negative indices
                    normalized_indices = []
                    for idx in value:
                        if not isinstance(idx, int):
                            raise ConfigMergeError(
                                f"Cannot remove from list '{actual_key}': index must be integer, got {type(idx).__name__}",
                                suggestion=f"When removing from a list, provide integer indices.\n\n"
                                f"Example:\n"
                                f"  ~{actual_key}: [0, 2, 4]  # Remove items at indices 0, 2, 4\n"
                                f"  ~{actual_key}: [-1]       # Remove last item",
                            )

                        # Validate index is in bounds
                        if idx >= list_len or idx < -list_len:
                            raise ConfigMergeError(
                                f"Cannot remove from list '{actual_key}': index {idx} out of range (list has {list_len} items)",
                                suggestion=f"Valid indices are 0 to {list_len - 1}, or -{list_len} to -1.\n"
                                f"Use null to remove the entire list:\n"
                                f"  ~{actual_key}: null",
                            )

                        # Normalize negative indices to positive
                        normalized_idx = idx if idx >= 0 else list_len + idx
                        normalized_indices.append(normalized_idx)

                    # Sort indices in descending order and remove duplicates
                    sorted_indices = sorted(set(normalized_indices), reverse=True)

                    # Remove in descending order to avoid shifting issues
                    for idx in sorted_indices:
                        del base_val[idx]

                # Remove from dict by keys
                elif isinstance(base_val, dict):
                    for del_key in value:
                        if del_key not in base_val:
                            # Use helper to build error with suggestions
                            available_keys = list(base_val.keys())
                            source_location = context.get_source_location(key)
                            raise build_missing_key_error(del_key, available_keys, source_location, parent_key=actual_key)
                        del base_val[del_key]

                else:
                    raise ConfigMergeError(
                        f"Cannot remove items from '{actual_key}': expected list or dict, got {type(base_val).__name__}",
                        suggestion=f"Item removal with '~{actual_key}: [...]' only works for lists and dicts.\n"
                        f"To remove the entire key:\n"
                        f"  ~{actual_key}: null",
                    )

                continue

        # No operator - COMPOSITION-BY-DEFAULT behavior
        if key in result:
            base_val = result[key]

            # For dicts: MERGE (composition)
            if isinstance(base_val, dict) and isinstance(value, dict):
                # Create child context for recursion
                child_context = context.child_path(key)
                result[key] = apply_operators(base_val, value, context=child_context)
                continue

            # For lists: EXTEND (composition)
            if isinstance(base_val, list) and isinstance(value, list):
                result[key] = base_val + value
                continue

            # For scalars: REPLACE
            # For type mismatches: REPLACE

        # Set/replace (for new keys or non-matching types)
        result[key] = deepcopy(value)

    return result
