"""Configuration diffing utilities with semantic comparison support."""

import json
from dataclasses import dataclass
from os import PathLike
from typing import Any

__all__ = ["ConfigDiff", "diff_configs", "format_diff_tree", "format_diff_unified", "format_diff_json"]


@dataclass
class ConfigDiff:
    """Represents differences between two configuration files.

    Attributes:
        added: Keys that exist in config2 but not in config1
        removed: Keys that exist in config1 but not in config2
        changed: Keys with different values between configs (maps key to (old_value, new_value))
        unchanged: Keys with identical values in both configs
    """

    added: dict[str, Any]
    removed: dict[str, Any]
    changed: dict[str, tuple[Any, Any]]
    unchanged: dict[str, Any]

    def has_changes(self) -> bool:
        """Check if there are any differences between the configs.

        Returns:
            True if there are added, removed, or changed keys
        """
        return bool(self.added or self.removed or self.changed)

    def summary(self) -> str:
        """Get a human-readable summary of changes.

        Returns:
            Summary string like "3 changed, 2 added, 1 removed" or "no changes"

        Examples:
            >>> diff = ConfigDiff(added={'a': 1}, removed={}, changed={'b': (1, 2)}, unchanged={})
            >>> diff.summary()
            '1 changed, 1 added'
        """
        parts = []
        if self.changed:
            parts.append(f"{len(self.changed)} changed")
        if self.added:
            parts.append(f"{len(self.added)} added")
        if self.removed:
            parts.append(f"{len(self.removed)} removed")
        return ", ".join(parts) if parts else "no changes"


def _flatten_config(config: dict[str, Any], parent_key: str = "", sep: str = "::") -> dict[str, Any]:
    """Flatten a nested config dict into flat key-value pairs.

    Args:
        config: Nested configuration dictionary
        parent_key: Parent key prefix for recursion
        sep: Separator for nested keys (default: "::")

    Returns:
        Flattened dictionary with nested keys joined by separator

    Examples:
        >>> _flatten_config({"a": {"b": 1, "c": 2}})
        {'a::b': 1, 'a::c': 2}
    """
    items = {}
    for key, value in config.items():
        # Skip metadata
        if key == "_meta_":
            continue

        new_key = f"{parent_key}{sep}{key}" if parent_key else key

        if isinstance(value, dict):
            # Recursively flatten nested dicts
            items.update(_flatten_config(value, new_key, sep))
        else:
            items[new_key] = value

    return items


def diff_configs(
    path1: PathLike | dict,
    path2: PathLike | dict,
    resolve: bool = False,
    ignore_keys: list[str] | None = None,
) -> ConfigDiff:
    """Compare two configuration files or dicts.

    Args:
        path1: First config file path or dict
        path2: Second config file path or dict
        resolve: If True, resolve references and expressions before comparing
                (enables semantic diff - configs with different syntax but same
                resolved values will be considered identical)
        ignore_keys: List of config IDs to ignore in diff (e.g., ["metadata", "timestamp"])

    Returns:
        ConfigDiff object containing added, removed, changed, and unchanged keys

    Examples:
        >>> diff = diff_configs("config_v1.yaml", "config_v2.yaml")
        >>> print(diff.summary())
        '2 changed, 1 added, 1 removed'

        >>> # Semantic diff - compare resolved values
        >>> diff = diff_configs("config_v1.yaml", "config_v2.yaml", resolve=True)
        >>> if not diff.has_changes():
        ...     print("Configs are semantically equivalent")
    """
    from .config_parser import ConfigParser

    # Load configs
    if isinstance(path1, dict):
        config1 = path1
        parser1 = ConfigParser.load(config1)
    else:
        parser1 = ConfigParser.load(path1)
        config1 = parser1.config

    if isinstance(path2, dict):
        config2 = path2
        parser2 = ConfigParser.load(config2)
    else:
        parser2 = ConfigParser.load(path2)
        config2 = parser2.config

    # Resolve if requested
    if resolve:
        config1 = parser1.resolve()
        config2 = parser2.resolve()

    # Flatten configs for comparison
    flat1 = _flatten_config(config1)
    flat2 = _flatten_config(config2)

    # Apply ignore filter
    if ignore_keys:
        flat1 = {k: v for k, v in flat1.items() if k not in ignore_keys}
        flat2 = {k: v for k, v in flat2.items() if k not in ignore_keys}

    # Find differences
    all_keys = set(flat1.keys()) | set(flat2.keys())

    added = {}
    removed = {}
    changed = {}
    unchanged = {}

    for key in all_keys:
        if key in flat1 and key in flat2:
            if flat1[key] == flat2[key]:
                unchanged[key] = flat1[key]
            else:
                changed[key] = (flat1[key], flat2[key])
        elif key in flat2:
            added[key] = flat2[key]
        else:
            removed[key] = flat1[key]

    return ConfigDiff(
        added=added,
        removed=removed,
        changed=changed,
        unchanged=unchanged,
    )


def format_diff_tree(diff: ConfigDiff, name1: str = "config1", name2: str = "config2", show_unchanged: bool = False) -> str:
    """Format diff as a tree structure (default, human-readable format).

    Args:
        diff: ConfigDiff object to format
        name1: Name of first config file
        name2: Name of second config file
        show_unchanged: If True, include unchanged keys in output

    Returns:
        Formatted tree-style diff string

    Example output:
        Configuration Diff: config_v1.yaml → config_v2.yaml

        model
          ✓ _target_: "torch.nn.Linear" (unchanged)
          ✗ hidden_size: 512 → 1024
          + dropout: 0.1 (added)

        Summary:
          1 changed, 1 added
    """
    from .errors.formatters import format_error, format_success, _get_colors_enabled

    lines = [f"Configuration Diff: {name1} → {name2}", ""]

    if not diff.has_changes() and not show_unchanged:
        lines.append("No differences found")
        return "\n".join(lines)

    if not diff.has_changes() and show_unchanged:
        lines.append("No differences found")
        lines.append("")

    # Group by top-level section
    def get_section(key: str) -> str:
        return key.split("::")[0] if "::" in key else key

    sections = {}
    for key in sorted(list(diff.added.keys()) + list(diff.removed.keys()) + list(diff.changed.keys()) + (list(diff.unchanged.keys()) if show_unchanged else [])):
        section = get_section(key)
        if section not in sections:
            sections[section] = {"added": {}, "removed": {}, "changed": {}, "unchanged": {}}

        if key in diff.added:
            sections[section]["added"][key] = diff.added[key]
        elif key in diff.removed:
            sections[section]["removed"][key] = diff.removed[key]
        elif key in diff.changed:
            sections[section]["changed"][key] = diff.changed[key]
        elif show_unchanged and key in diff.unchanged:
            sections[section]["unchanged"][key] = diff.unchanged[key]

    # Format sections
    for section in sorted(sections.keys()):
        items = sections[section]
        if not any(items.values()):
            continue

        lines.append(section)

        # Show unchanged first (if requested)
        if show_unchanged:
            for key in sorted(items["unchanged"].keys()):
                value = items["unchanged"][key]
                display_key = key[len(section) + 2:] if key.startswith(section + "::") else key
                value_str = _format_value(value)
                if _get_colors_enabled():
                    lines.append(f"  {format_success('✓')} {display_key}: {value_str} (unchanged)")
                else:
                    lines.append(f"  ✓ {display_key}: {value_str} (unchanged)")

        # Show changed
        for key in sorted(items["changed"].keys()):
            old_val, new_val = items["changed"][key]
            display_key = key[len(section) + 2:] if key.startswith(section + "::") else key
            old_str = _format_value(old_val)
            new_str = _format_value(new_val)
            if _get_colors_enabled():
                lines.append(f"  {format_error('✗')} {display_key}: {old_str} → {new_str}")
            else:
                lines.append(f"  ✗ {display_key}: {old_str} → {new_str}")

        # Show added
        for key in sorted(items["added"].keys()):
            value = items["added"][key]
            display_key = key[len(section) + 2:] if key.startswith(section + "::") else key
            value_str = _format_value(value)
            if _get_colors_enabled():
                lines.append(f"  {format_success('+')} {display_key}: {value_str} (added)")
            else:
                lines.append(f"  + {display_key}: {value_str} (added)")

        # Show removed
        for key in sorted(items["removed"].keys()):
            value = items["removed"][key]
            display_key = key[len(section) + 2:] if key.startswith(section + "::") else key
            value_str = _format_value(value)
            if _get_colors_enabled():
                lines.append(f"  {format_error('-')} {display_key}: {value_str} (removed)")
            else:
                lines.append(f"  - {display_key}: {value_str} (removed)")

        lines.append("")

    # Summary
    lines.append("Summary:")
    lines.append(f"  {diff.summary()}")

    return "\n".join(lines)


def format_diff_unified(diff: ConfigDiff, name1: str = "config1", name2: str = "config2") -> str:
    """Format diff as unified diff (git-style format).

    Args:
        diff: ConfigDiff object to format
        name1: Name of first config file
        name2: Name of second config file

    Returns:
        Formatted unified-style diff string

    Example output:
        --- config_v1.yaml
        +++ config_v2.yaml
        @@ model @@
          _target_: "torch.nn.Linear"
        - hidden_size: 512
        + hidden_size: 1024
        + dropout: 0.1
    """
    lines = [f"--- {name1}", f"+++ {name2}"]

    if not diff.has_changes():
        return "\n".join(lines + ["No differences"])

    # Group by section
    def get_section(key: str) -> str:
        return key.split("::")[0] if "::" in key else key

    sections = {}
    for key in sorted(list(diff.added.keys()) + list(diff.removed.keys()) + list(diff.changed.keys())):
        section = get_section(key)
        if section not in sections:
            sections[section] = {"added": {}, "removed": {}, "changed": {}}

        if key in diff.added:
            sections[section]["added"][key] = diff.added[key]
        elif key in diff.removed:
            sections[section]["removed"][key] = diff.removed[key]
        elif key in diff.changed:
            sections[section]["changed"][key] = diff.changed[key]

    # Format sections
    for section in sorted(sections.keys()):
        items = sections[section]
        if not any(items.values()):
            continue

        lines.append(f"@@ {section} @@")

        # Show removed and changed (old values)
        for key in sorted(items["removed"].keys()):
            value = items["removed"][key]
            display_key = key[len(section) + 2:] if key.startswith(section + "::") else key
            lines.append(f"- {display_key}: {_format_value(value)}")

        for key in sorted(items["changed"].keys()):
            old_val, _ = items["changed"][key]
            display_key = key[len(section) + 2:] if key.startswith(section + "::") else key
            lines.append(f"- {display_key}: {_format_value(old_val)}")

        # Show added and changed (new values)
        for key in sorted(items["added"].keys()):
            value = items["added"][key]
            display_key = key[len(section) + 2:] if key.startswith(section + "::") else key
            lines.append(f"+ {display_key}: {_format_value(value)}")

        for key in sorted(items["changed"].keys()):
            _, new_val = items["changed"][key]
            display_key = key[len(section) + 2:] if key.startswith(section + "::") else key
            lines.append(f"+ {display_key}: {_format_value(new_val)}")

        lines.append("")

    return "\n".join(lines)


def format_diff_json(diff: ConfigDiff) -> str:
    """Format diff as JSON (machine-readable format).

    Args:
        diff: ConfigDiff object to format

    Returns:
        JSON string representation of the diff

    Example output:
        {
          "added": {"model::dropout": 0.1},
          "removed": {"training::old_param": 123},
          "changed": {"model::hidden_size": {"old": 512, "new": 1024}},
          "summary": "1 changed, 1 added, 1 removed"
        }
    """
    # Convert changed tuples to dict format
    changed_formatted = {k: {"old": v[0], "new": v[1]} for k, v in diff.changed.items()}

    result = {
        "added": diff.added,
        "removed": diff.removed,
        "changed": changed_formatted,
        "summary": diff.summary(),
    }

    return json.dumps(result, indent=2, default=str)


def _format_value(value: Any, max_length: int = 50) -> str:
    """Format a value for compact display in diff output.

    Args:
        value: Value to format
        max_length: Maximum length for the representation

    Returns:
        Formatted string representation
    """
    if isinstance(value, str):
        repr_str = f'"{value}"'
    elif isinstance(value, (int, float, bool, type(None))):
        repr_str = str(value)
    elif isinstance(value, dict):
        repr_str = f"{{...}} ({len(value)} keys)"
    elif isinstance(value, list):
        repr_str = f"[...] ({len(value)} items)"
    else:
        repr_str = str(type(value).__name__)

    # Truncate if too long
    if len(repr_str) > max_length:
        repr_str = repr_str[:max_length - 3] + "..."

    return repr_str
