"""Context display utilities for error messages - available keys, resolution chains, etc."""

from typing import Any

__all__ = [
    "format_available_keys",
    "format_resolution_chain",
]


def format_available_keys(config: dict[str, Any], max_keys: int = 10) -> str:
    """Format available keys for display in error messages.

    Args:
        config: Configuration dictionary to extract keys from
        max_keys: Maximum number of keys to display (default: 10)

    Returns:
        Formatted string with available keys and their values (truncated if needed)

    Examples:
        >>> config = {"_target_": "torch.nn.Linear", "in_features": 784, "out_features": 10}
        >>> print(format_available_keys(config))
        Available keys:
          - _target_: "torch.nn.Linear"
          - in_features: 784
          - out_features: 10
    """
    if not config or not isinstance(config, dict):
        return ""

    lines = ["Available keys:"]

    keys_to_show = list(config.keys())[:max_keys]

    for key in keys_to_show:
        value = config[key]
        value_repr = _format_value_repr(value)
        lines.append(f"  - {key}: {value_repr}")

    if len(config) > max_keys:
        remaining = len(config) - max_keys
        lines.append(f"  ... and {remaining} more")

    return "\n".join(lines)


def _format_value_repr(value: Any, max_length: int = 50) -> str:
    """Format a value for compact display.

    Args:
        value: Value to format
        max_length: Maximum length for the representation

    Returns:
        Formatted string representation

    Examples:
        >>> _format_value_repr("hello")
        '"hello"'
        >>> _format_value_repr(42)
        '42'
        >>> _format_value_repr({"a": 1, "b": 2})
        '{a: 1, b: 2}'
    """
    if isinstance(value, str):
        repr_str = f'"{value}"'
    elif isinstance(value, (int, float, bool, type(None))):
        repr_str = str(value)
    elif isinstance(value, dict):
        if not value:
            repr_str = "{}"
        elif len(value) <= 3:
            # Show small dicts compactly
            items = [f"{k}: {_format_value_repr(v, max_length=20)}" for k, v in list(value.items())[:3]]
            repr_str = "{" + ", ".join(items) + "}"
        else:
            repr_str = f"{{...}} ({len(value)} keys)"
    elif isinstance(value, list):
        if not value:
            repr_str = "[]"
        elif len(value) <= 3:
            items = [_format_value_repr(v, max_length=20) for v in value[:3]]
            repr_str = "[" + ", ".join(items) + "]"
        else:
            repr_str = f"[...] ({len(value)} items)"
    else:
        repr_str = str(type(value).__name__)

    # Truncate if too long
    if len(repr_str) > max_length:
        repr_str = repr_str[: max_length - 3] + "..."

    return repr_str


def format_resolution_chain(
    chain: list[tuple[str, str, bool]],
    title: str = "Resolution chain:",
) -> str:
    """Format a resolution chain for display in error messages.

    Args:
        chain: List of (id, reference, success) tuples representing the resolution chain
        title: Title for the chain display

    Returns:
        Formatted string with the resolution chain visualization

    Examples:
        >>> chain = [
        ...     ("training::optimizer", "@optimizer", True),
        ...     ("optimizer::lr", "@base::learning_rate", True),
        ...     ("base::learning_rate", "", False),
        ... ]
        >>> print(format_resolution_chain(chain))
        Resolution chain:
          1. training::optimizer = "@optimizer" ✓
          2. optimizer::lr = "@base::learning_rate" ✓
          3. base::learning_rate = ❌ NOT FOUND
    """
    if not chain:
        return ""

    lines = [title]

    for i, (id_str, reference, success) in enumerate(chain, 1):
        if success:
            if reference:
                status = "✓"
                lines.append(f'  {i}. {id_str} = "{reference}" {status}')
            else:
                lines.append(f"  {i}. {id_str} ✓")
        else:
            lines.append(f"  {i}. {id_str} = ❌ NOT FOUND")

    # Add suggestion
    if chain and not chain[-1][2]:  # Last item failed
        lines.append("")
        lines.append(f"💡 The reference chain failed at step {len(chain)}.")

    return "\n".join(lines)
