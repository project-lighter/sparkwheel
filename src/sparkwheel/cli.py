"""
CLI utilities for Sparkwheel configuration overrides.

This module provides utilities for parsing command-line configuration overrides
in the format "key::path=value". Designed to be reusable across any application
using Sparkwheel for configuration management.

Examples:
    Basic parsing:
        >>> from sparkwheel.cli import parse_override
        >>> key, value = parse_override("model::lr=0.001")
        >>> print(key, value)
        model::lr 0.001

    Multiple overrides:
        >>> from sparkwheel.cli import parse_overrides
        >>> overrides = parse_overrides([
        ...     "model::lr=0.001",
        ...     "trainer::max_epochs=100"
        ... ])
        >>> print(overrides)
        {'model::lr': 0.001, 'trainer::max_epochs': 100}

    Using with Config:
        >>> from sparkwheel import Config
        >>> config = Config.from_cli(
        ...     "config.yaml",
        ...     ["model::lr=0.001", "trainer::devices=[0,1,2]"]
        ... )
"""

import ast
from typing import Any

__all__ = ["parse_override", "parse_overrides"]


def parse_override(arg: str) -> tuple[str, Any]:
    """
    Parse a single CLI override argument.

    Parses command-line overrides in the format "key::path=value" where:
    - key::path uses Sparkwheel's path separator (::)
    - value is automatically parsed as Python literal when possible

    Args:
        arg: Override string in format "key::path=value"

    Returns:
        Tuple of (key, parsed_value) where value has been converted to
        appropriate Python type (int, float, list, dict, bool, None, or str)

    Raises:
        ValueError: If the argument format is invalid (no '=' sign)

    Examples:
        Parse integers:
            >>> parse_override("trainer::max_epochs=100")
            ('trainer::max_epochs', 100)

        Parse floats:
            >>> parse_override("model::lr=0.001")
            ('model::lr', 0.001)

        Parse lists:
            >>> parse_override("trainer::devices=[0,1,2]")
            ('trainer::devices', [0, 1, 2])

        Parse booleans:
            >>> parse_override("trainer::fast_dev_run=True")
            ('trainer::fast_dev_run', True)

        Parse None:
            >>> parse_override("model::scheduler=None")
            ('model::scheduler', None)

        Parse dicts:
            >>> parse_override("model::config={'a':1,'b':2}")
            ('model::config', {'a': 1, 'b': 2})

        Parse strings (when literal_eval fails):
            >>> parse_override("model::name=resnet50")
            ('model::name', 'resnet50')

        Nested paths:
            >>> parse_override("system::model::optimizer::lr=0.001")
            ('system::model::optimizer::lr', 0.001)
    """
    if "=" not in arg:
        raise ValueError(f"Invalid override format: '{arg}'. Expected format: 'key::path=value'")

    # Split on first = only (value might contain =)
    key, value_str = arg.split("=", 1)

    # Try to parse value as Python literal
    # This handles: int, float, list, dict, tuple, bool, None
    try:
        value = ast.literal_eval(value_str)
    except (ValueError, SyntaxError):
        # If parsing fails, keep as string
        # This handles strings that don't need quotes on CLI
        value = value_str

    return key, value


def parse_overrides(args: list[str]) -> dict[str, Any]:
    """
    Parse multiple CLI override arguments.

    Convenience function to parse a list of override strings into
    a dictionary suitable for passing to Config.set() or Config.update().

    Args:
        args: List of override strings in format "key::path=value"

    Returns:
        Dictionary mapping configuration keys to parsed values

    Raises:
        ValueError: If any argument has invalid format

    Examples:
        Basic usage:
            >>> parse_overrides([
            ...     "model::lr=0.001",
            ...     "trainer::max_epochs=100"
            ... ])
            {'model::lr': 0.001, 'trainer::max_epochs': 100}

        Mixed types:
            >>> parse_overrides([
            ...     "model::name=resnet50",
            ...     "model::layers=[64,128,256]",
            ...     "trainer::devices=[0,1]",
            ...     "debug=True"
            ... ])
            {
                'model::name': 'resnet50',
                'model::layers': [64, 128, 256],
                'trainer::devices': [0, 1],
                'debug': True
            }

        Empty list:
            >>> parse_overrides([])
            {}

        With Config:
            >>> from sparkwheel import Config
            >>> config = Config.load("config.yaml")
            >>> overrides = parse_overrides(["model::lr=0.01"])
            >>> for key, value in overrides.items():
            ...     config.set(key, value)
    """
    if not args:
        return {}

    return dict(parse_override(arg) for arg in args)
