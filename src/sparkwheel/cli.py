"""CLI argument parsing for configuration overrides with type inference."""

import json
from typing import Any

__all__ = ["parse_args"]


def parse_args(args: list[str]) -> dict[str, Any]:
    """Parse CLI arguments to typed dict.

    Handles automatic type conversion and +/~ prefixes for merge/delete.

    Args:
        args: List of CLI arguments (e.g., sys.argv[1:])
              User controls what to pass - no defaults!

    Returns:
        Dictionary ready for parser.update()

    Type Parsing:
        Uses JSON parsing for type inference:
        - Numbers: "123" → 123, "3.14" → 3.14
        - Booleans: "true" → True, "false" → False
        - Null: "null" → None
        - Lists: "[1,2,3]" → [1, 2, 3]
        - Dicts: "{a:1,b:2}" → {"a": 1, "b": 2}
        - Strings: Everything else or quoted values

    Prefix Support:
        key=value   - Normal set/replace
        +key=value  - Merge dict (for dict values)
        ~key        - Delete key

    Examples:
        >>> parse_args(["model::lr=0.001"])
        {"model::lr": 0.001}

        >>> parse_args(["+model::layers={third:{type:relu}}"])
        {"+model::layers": {"third": {"type": "relu"}}}

        >>> parse_args(["~old::param"])
        {"~old::param": None}

        >>> parse_args(["name=Experiment 1"])  # String (no quotes needed in shell)
        {"name": "Experiment 1"}

        >>> parse_args(["name=\"Experiment 1\""])  # String with quotes
        {"name": "Experiment 1"}

        >>> parse_args(["count=42", "enabled=true", "values=[1,2,3]"])
        {"count": 42, "enabled": True, "values": [1, 2, 3]}
    """
    result = {}
    for arg in args:
        if "=" in arg:
            key, value_str = arg.split("=", 1)
            # Preserve prefix in key, parse value
            result[key] = _parse_value(value_str)
        elif arg.startswith("~"):
            # Delete directive
            result[arg] = None  # Marker for deletion
    return result


def _parse_value(s: str) -> Any:
    """Parse string to appropriate Python type.

    Uses JSON parsing for type inference.

    Args:
        s: String value to parse

    Returns:
        Parsed Python value (int, float, bool, None, list, dict, or str)

    Examples:
        >>> _parse_value("123")
        123
        >>> _parse_value("3.14")
        3.14
        >>> _parse_value("true")
        True
        >>> _parse_value("false")
        False
        >>> _parse_value("null")
        None
        >>> _parse_value("[1,2,3]")
        [1, 2, 3]
        >>> _parse_value("{a:1,b:2}")
        {"a": 1, "b": 2}
        >>> _parse_value("hello")
        'hello'
        >>> _parse_value('"hello world"')
        'hello world'
    """
    # Try JSON first - handles int, float, bool, null, list, dict
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        # Not valid JSON - check if it's JSON-like but with unquoted keys (common in CLI)
        # Try to fix common patterns like {a:1} -> {"a":1}
        if s.startswith("{") and ":" in s and not s.startswith('{"'):
            try:
                # Try to fix unquoted keys in dict
                fixed = _fix_unquoted_keys(s)
                return json.loads(fixed)
            except (json.JSONDecodeError, ValueError):
                pass

        # Return as string
        return s


def _fix_unquoted_keys(s: str) -> str:
    """Fix unquoted keys and values in JSON-like dict strings.

    Converts {a:1,b:2} to {"a":1,"b":2} and {key:value} to {"key":"value"}
    for JSON parsing.

    Args:
        s: JSON-like string with unquoted keys/values

    Returns:
        Fixed JSON string

    Examples:
        >>> _fix_unquoted_keys("{a:1}")
        '{"a":1}'
        >>> _fix_unquoted_keys("{a:1,b:2}")
        '{"a":1,"b":2}'
        >>> _fix_unquoted_keys("{a:{nested:1}}")
        '{"a":{"nested":1}}'
        >>> _fix_unquoted_keys("{key:value}")
        '{"key":"value"}'
    """
    import re

    result = s

    # Step 1: Quote unquoted keys (before colons)
    # Pattern: word chars after { or , followed by colon
    result = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', result)

    # Step 2: Quote unquoted string values (word-only, not numbers/booleans/null)
    # Pattern: colon followed by bare word (not a number, bool, or null)
    # Don't quote: numbers, true, false, null, [ (lists), { (dicts)
    # This will match words that are values

    def quote_value(match):
        value = match.group(2).strip()
        # Don't quote numbers, booleans, null, or JSON structures
        if value in ('true', 'false', 'null') or value[0] in ('{', '[') or value.replace('.', '').replace('-', '').isdigit():
            return match.group(0)
        # Quote the value
        return match.group(1) + '"' + value + '"' + match.group(3)

    # Match values: after colon, before comma or }
    result = re.sub(r'(:\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*[,}])', quote_value, result)

    return result
