"""Path parsing and manipulation utilities.

Provides helper functions for working with config paths, building on
the regex patterns from path_patterns.py.
"""

from typing import Any

from .path_patterns import PathPatterns
from .utils.constants import ID_SEP_KEY

__all__ = [
    "split_id",
    "normalize_id",
    "resolve_relative_ids",
    "scan_references",
    "replace_references",
]


def split_id(id: str | int) -> list[str]:
    """Split config ID into parts by :: separator.

    Args:
        id: Config ID to split

    Returns:
        List of ID components

    Examples:
        >>> split_id("model::optimizer::lr")
        ["model", "optimizer", "lr"]
        >>> split_id("data::0::value")
        ["data", "0", "value"]
        >>> split_id("simple")
        ["simple"]
    """
    return normalize_id(id).split(ID_SEP_KEY)


def normalize_id(id: str | int) -> str:
    """Normalize ID to string format.

    Args:
        id: ID to normalize (string or int)

    Returns:
        String representation of ID

    Examples:
        >>> normalize_id("model::lr")
        "model::lr"
        >>> normalize_id(42)
        "42"
    """
    return str(id)


def resolve_relative_ids(current_id: str, value: str) -> str:
    """Resolve relative references (@::, @::::) to absolute paths.

    Converts relative navigation patterns to absolute paths based on
    the current position in the config tree.

    Args:
        current_id: Current position in config (e.g., "model::optimizer")
        value: String that may contain relative references

    Returns:
        String with relative references resolved to absolute

    Examples:
        >>> resolve_relative_ids("model::optimizer", "@::lr")
        "@model::lr"
        >>> resolve_relative_ids("a::b::c", "@::::lr")
        "@a::lr"
        >>> resolve_relative_ids("model", "@::lr")
        "@lr"

    Raises:
        ValueError: If relative reference goes beyond root
    """
    # Find all relative reference patterns using centralized regex
    patterns = PathPatterns.find_relative_references(value)

    # Sort by length (longest first) to avoid partial replacements
    # e.g., replace "@::::" before "@::" so we don't double-process
    patterns = sorted(set(patterns), key=len, reverse=True)

    current_parts = current_id.split(ID_SEP_KEY) if current_id else []

    for pattern in patterns:
        # Determine symbol (@ for reference, % for macro)
        symbol = pattern[0]

        # Count :: pairs to determine how many levels to go up
        # @:: = 1 level up, @:::: = 2 levels up
        levels_up = pattern[1:].count(ID_SEP_KEY)

        # Validate we don't go too far up the tree
        if levels_up > len(current_parts):
            raise ValueError(
                f"Relative reference '{pattern}' in '{value}' attempts to go "
                f"{levels_up} levels up, but current path '{current_id}' only "
                f"has {len(current_parts)} levels"
            )

        # Calculate the absolute path
        if levels_up == len(current_parts):
            # Going to root level
            absolute = symbol
        else:
            # Going to ancestor at specific level
            ancestor_parts = current_parts[:-levels_up] if levels_up > 0 else current_parts
            absolute = symbol + ID_SEP_KEY.join(ancestor_parts)
            if ancestor_parts:  # Add trailing separator if not at root
                absolute += ID_SEP_KEY

        # Replace pattern in value
        value = value.replace(pattern, absolute)

    return value


def scan_references(text: str) -> dict[str, int]:
    """Find all @ reference patterns in text and count occurrences.

    Only scans in expressions ($...) or pure reference values.

    Args:
        text: String to scan

    Returns:
        Dict mapping reference IDs (without @) to occurrence counts

    Examples:
        >>> scan_references("@model::lr")
        {"model::lr": 1}
        >>> scan_references("$@x + @x")
        {"x": 2}
        >>> scan_references("normal text")
        {}
    """
    refs: dict[str, int] = {}

    # Only process expressions or pure references
    is_expr = text.startswith("$")
    is_pure_ref = text.startswith("@")

    if not (is_expr or is_pure_ref):
        return refs

    # Use centralized pattern to find all references
    ref_ids = PathPatterns.find_absolute_references(text)

    # Count occurrences
    for ref_id in ref_ids:
        refs[ref_id] = refs.get(ref_id, 0) + 1

    return refs


def replace_references(text: str, resolved_refs: dict[str, Any], local_var_name: str = "__local_refs") -> str | Any:
    """Replace @ references with resolved values.

    For pure references: Returns the resolved value directly
    For expressions: Replaces @ref with __local_refs['ref'] for eval()
    For other text: Returns unchanged

    Args:
        text: String containing references
        resolved_refs: Dict mapping reference IDs to resolved values
        local_var_name: Variable name for expression substitution

    Returns:
        - Resolved value if text is a pure reference
        - Modified string if text is an expression
        - Original text if no references

    Examples:
        >>> refs = {"model::lr": 0.001, "x": 42}
        >>> replace_references("@model::lr", refs)
        0.001
        >>> replace_references("$@x * 2", refs)
        "$__local_refs['x'] * 2"
        >>> replace_references("normal", refs)
        "normal"

    Raises:
        KeyError: If a referenced ID is not in resolved_refs
    """
    is_expr = text.startswith("$")
    is_pure_ref = text.startswith("@") and "@" not in text[1:]

    if is_pure_ref:
        # Entire value is a single reference - return resolved value
        ref_id = text[1:]  # Strip @
        if ref_id not in resolved_refs:
            raise KeyError(f"Reference '@{ref_id}' not found in resolved references")
        return resolved_refs[ref_id]

    if not is_expr:
        # Not an expression or reference - return as-is
        return text

    # Expression - find all references and replace with variable access
    # Use regex to find and replace
    def replace_match(match):
        ref_id = match.group(1)
        if ref_id not in resolved_refs:
            raise KeyError(f"Reference '@{ref_id}' not found in resolved references")
        return f"{local_var_name}['{ref_id}']"

    result = PathPatterns.ABSOLUTE_REFERENCE.sub(replace_match, text)
    return result
