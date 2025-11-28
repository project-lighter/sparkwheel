"""Path parsing and manipulation utilities.

Centralized regex patterns and helper functions for parsing configuration paths,
references, and file paths. Handles ID splitting, relative reference resolution,
and file path extraction from combined strings like "config.yaml::model::lr".
"""

import re
from typing import Any

from .utils.constants import ID_SEP_KEY, RAW_REF_KEY, RESOLVED_REF_KEY

__all__ = [
    "split_id",
    "normalize_id",
    "resolve_relative_ids",
    "scan_references",
    "replace_references",
    "split_file_and_id",
    "is_yaml_file",
    "get_by_id",
    "PathPatterns",  # Export for backward compatibility
]


# ============================================================================
# YAML File Detection
# ============================================================================


def is_yaml_file(filepath: str) -> bool:
    """Check if filepath is a YAML file (.yaml or .yml).

    Simple string check - no regex needed for this.

    Args:
        filepath: Path to check

    Returns:
        True if filepath ends with .yaml or .yml (case-insensitive)

    Examples:
        >>> is_yaml_file("config.yaml")
        True
        >>> is_yaml_file("CONFIG.YAML")
        True
        >>> is_yaml_file("data.json")
        False
    """
    lower = filepath.lower()
    return lower.endswith(".yaml") or lower.endswith(".yml")


# ============================================================================
# Compiled Regex Patterns
# ============================================================================


class PathPatterns:
    """Collection of compiled regex patterns for config path parsing.

    All patterns are compiled once at class definition time and reused.
    Each pattern includes documentation with examples of what it matches.
    """

    # File path and config ID splitting
    # Example: "config.yaml::model::lr" -> captures "config.yaml"
    # Uses lookahead (?=...) to find extension without consuming :: separator
    FILE_AND_ID = re.compile(r"(.*\.(yaml|yml))(?=(?:::.*)|$)", re.IGNORECASE)
    """Split combined file path and config ID.

    The pattern uses lookahead to find the file extension without consuming
    the :: separator that follows.

    Matches:
        - "config.yaml::model::lr" -> group 1: "config.yaml"
        - "path/to/file.yml::key" -> group 1: "path/to/file.yml"
        - "/abs/path/cfg.yaml::a::b" -> group 1: "/abs/path/cfg.yaml"

    Non-matches:
        - "model::lr" -> no .yaml/.yml extension
        - "data.json::key" -> wrong extension

    Edge cases handled:
        - Case insensitive: "Config.YAML::key" works
        - Multiple extensions: "backup.yaml.old" stops at first .yaml
        - Absolute paths: "/etc/config.yaml::key" works
    """

    RELATIVE_REFERENCE = re.compile(rf"(?:{RESOLVED_REF_KEY}|{RAW_REF_KEY})(::)+")
    """Match relative reference prefixes: @::, @::::, %::, etc.

    Used to find relative navigation patterns in config references.
    The number of :: pairs indicates how many levels to go up.

    Matches:
        - "@::" -> resolved reference one level up (parent)
        - "@::::" -> resolved reference two levels up (grandparent)
        - "%::" -> raw reference one level up
        - "%::::" -> raw reference two levels up

    Examples in context:
        - In "model::optimizer", "@::lr" means "@model::lr"
        - In "a::b::c", "@::::x" means "@a::x"

    Pattern breakdown:
        - (?:@|%) -> @ or % symbol (non-capturing group)
        - (::)+ -> one or more :: pairs (captured)
    """

    ABSOLUTE_REFERENCE = re.compile(rf"{RESOLVED_REF_KEY}(\w+(?:::\w+)*)")
    r"""Match absolute resolved reference patterns: @id::path::to::value

    Finds @ resolved references in config values and expressions. Handles nested
    paths with :: separators and list indices (numbers).

    Matches:
        - "@model::lr" -> captures "model::lr"
        - "@data::0::value" -> captures "data::0::value"
        - "@x" -> captures "x"

    Examples in expressions:
        - "$@model::lr * 2" -> matches "@model::lr"
        - "$@x + @y" -> matches "@x" and "@y"

    Pattern breakdown:
        - @ -> literal @ symbol
        - (\w+(?:::\w+)*) -> captures word chars followed by optional :: and more word chars

    Note: \w includes [a-zA-Z0-9_] plus Unicode word characters,
    so this handles international characters correctly.
    """

    @classmethod
    def split_file_and_id(cls, src: str) -> tuple[str, str]:
        """Split combined file path and config ID using FILE_AND_ID pattern.

        Args:
            src: String like "config.yaml::model::lr"

        Returns:
            Tuple of (filepath, config_id)

        Examples:
            >>> PathPatterns.split_file_and_id("config.yaml::model::lr")
            ("config.yaml", "model::lr")
            >>> PathPatterns.split_file_and_id("model::lr")
            ("", "model::lr")
            >>> PathPatterns.split_file_and_id("/path/to/file.yml::key")
            ("/path/to/file.yml", "key")
        """
        src = src.strip()
        match = cls.FILE_AND_ID.search(src)

        if not match:
            return "", src  # Pure ID, no file path

        filepath = match.group(1)
        remainder = src[match.end() :]

        # Strip leading :: from config ID part
        config_id = remainder[2:] if remainder.startswith("::") else remainder

        return filepath, config_id

    @classmethod
    def find_relative_references(cls, text: str) -> list[str]:
        """Find all relative reference patterns in text.

        Args:
            text: String to search

        Returns:
            List of relative reference patterns found (e.g., ['@::', '@::::'])

        Examples:
            >>> PathPatterns.find_relative_references("value: @::sibling")
            ['@::']
            >>> PathPatterns.find_relative_references("@::::parent and @::sibling")
            ['@::::', '@::']
        """
        # Use finditer to get full matches instead of just captured groups
        return [match.group(0) for match in cls.RELATIVE_REFERENCE.finditer(text)]

    @classmethod
    def find_absolute_references(cls, text: str) -> list[str]:
        """Find all absolute reference patterns in text.

        Only searches in expressions ($...) or pure reference values.

        Args:
            text: String to search

        Returns:
            List of reference IDs found (without @ prefix)

        Examples:
            >>> PathPatterns.find_absolute_references("@model::lr")
            ['model::lr']
            >>> PathPatterns.find_absolute_references("$@x + @y")
            ['x', 'y']
            >>> PathPatterns.find_absolute_references("normal text")
            []
        """
        is_expr = text.startswith("$")
        is_pure_ref = text.startswith("@")

        if not (is_expr or is_pure_ref):
            return []

        return cls.ABSOLUTE_REFERENCE.findall(text)


# ============================================================================
# Convenience Functions (delegate to PathPatterns)
# ============================================================================


def split_file_and_id(src: str) -> tuple[str, str]:
    """Convenience function wrapping PathPatterns.split_file_and_id().

    Args:
        src: String like "config.yaml::model::lr"

    Returns:
        Tuple of (filepath, config_id)

    Examples:
        >>> split_file_and_id("config.yaml::model::lr")
        ("config.yaml", "model::lr")
    """
    return PathPatterns.split_file_and_id(src)


def find_references(text: str) -> list[str]:
    """Convenience function wrapping PathPatterns.find_absolute_references().

    Args:
        text: String to search

    Returns:
        List of reference IDs found (without @ prefix)
    """
    return PathPatterns.find_absolute_references(text)


# ============================================================================
# ID Manipulation Functions
# ============================================================================


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


def _format_path_context(path_parts: list[str], index: int) -> str:
    """Format parent path context for error messages.

    Internal helper for get_by_id error messages.

    Args:
        path_parts: List of path components
        index: Current index in path_parts (0 = first level)

    Returns:
        Empty string for first level, or " in 'parent::path'" for nested levels
    """
    if index == 0:
        return ""
    parent_path = ID_SEP_KEY.join(path_parts[:index])
    return f" in '{parent_path}'"


def get_by_id(config: dict[str, Any] | list[Any], id: str) -> Any:
    """Navigate config structure by ID path.

    Traverses nested dicts and lists using :: separated path components.
    Provides detailed error messages with available keys when navigation fails.

    Args:
        config: Config dict or list to navigate
        id: ID path (e.g., "model::optimizer::lr" or "items::0::value")

    Returns:
        Value at the specified path

    Raises:
        KeyError: If a dict key is not found (includes available keys in message)
        TypeError: If trying to index a non-dict/list value

    Examples:
        >>> config = {"model": {"lr": 0.001, "layers": [64, 128]}}
        >>> get_by_id(config, "model::lr")
        0.001
        >>> get_by_id(config, "model::layers::1")
        128
        >>> get_by_id(config, "")
        {"model": {"lr": 0.001, "layers": [64, 128]}}

    Error messages include context:
        >>> get_by_id({"a": {"b": 1}}, "a::missing")
        KeyError: "Key 'missing' not found in 'a'. Available keys: ['b']"
    """
    if not id:
        return config

    current = config
    path_parts = split_id(id)

    for i, key in enumerate(path_parts):
        context = _format_path_context(path_parts, i)

        if isinstance(current, dict):
            if key not in current:
                available_keys = list(current.keys())
                error_msg = f"Key '{key}' not found{context}"
                error_msg += f". Available keys: {available_keys[:10]}"
                if len(available_keys) > 10:
                    error_msg += "..."
                raise KeyError(error_msg)
            current = current[key]
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except ValueError as e:
                raise KeyError(f"Invalid list index '{key}'{context}: not an integer") from e
            except IndexError as e:
                raise KeyError(f"List index '{key}' out of range{context}: {e}") from e
        else:
            raise TypeError(f"Cannot index {type(current).__name__} with key '{key}'{context}")

    return current


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
        # Determine symbol (@ for resolved reference, % for raw reference)
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
