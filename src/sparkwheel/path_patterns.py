"""Centralized regex patterns for config path parsing.

This module contains all regex patterns used across sparkwheel for parsing
configuration paths, references, and file paths. Patterns are compiled once
at module load and documented with examples.

Why regex here?
- Complex patterns (lookahead, Unicode support)
- Performance (C regex engine)
- Correctness (battle-tested patterns)

Patterns are centralized here instead of scattered across multiple files
for easier maintenance, testing, and documentation.
"""

import re

from .utils.constants import ID_REF_KEY, MACRO_KEY

__all__ = [
    "PathPatterns",
    "is_yaml_file",
]


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

    RELATIVE_REFERENCE = re.compile(rf"(?:{ID_REF_KEY}|{MACRO_KEY})(::)+")
    """Match relative reference prefixes: @::, @::::, %::, etc.

    Used to find relative navigation patterns in config references.
    The number of :: pairs indicates how many levels to go up.

    Matches:
        - "@::" -> one level up (parent)
        - "@::::" -> two levels up (grandparent)
        - "%::" -> macro one level up
        - "%::::" -> macro two levels up

    Examples in context:
        - In "model::optimizer", "@::lr" means "@model::lr"
        - In "a::b::c", "@::::x" means "@a::x"

    Pattern breakdown:
        - (?:@|%) -> @ or % symbol (non-capturing group)
        - (::)+ -> one or more :: pairs (captured)
    """

    ABSOLUTE_REFERENCE = re.compile(rf"{ID_REF_KEY}(\w+(?:::\w+)*)")
    r"""Match absolute reference patterns: @id::path::to::value

    Finds @ references in config values and expressions. Handles nested
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


# Utility functions that delegate to PathPatterns


def split_file_and_id(src: str) -> tuple[str, str]:
    """Convenience function wrapping PathPatterns.split_file_and_id()."""
    return PathPatterns.split_file_and_id(src)


def find_references(text: str) -> list[str]:
    """Convenience function wrapping PathPatterns.find_absolute_references()."""
    return PathPatterns.find_absolute_references(text)
