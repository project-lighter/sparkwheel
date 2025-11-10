"""Configuration checking utilities for validation and debugging."""

from dataclasses import dataclass, field
from os import PathLike
from typing import Any

__all__ = ["CheckResult", "check_config", "list_config_ids", "format_check_result"]


@dataclass
class CheckResult:
    """Result of configuration check.

    Attributes:
        is_valid: True if config passed all checks
        errors: List of error messages
        warnings: List of warning messages
        num_references: Number of references found
        num_expressions: Number of expressions found
        num_components: Number of components (items with _target_)
        config_ids: List of all config IDs found
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    num_references: int = 0
    num_expressions: int = 0
    num_components: int = 0
    config_ids: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Get human-readable summary.

        Returns:
            Summary string like "Check passed!" or "Check failed: 3 errors, 1 warning"

        Examples:
            >>> result = CheckResult(is_valid=True, errors=[], warnings=[])
            >>> result.summary()
            'Check passed!'

            >>> result = CheckResult(is_valid=False, errors=["error1", "error2"], warnings=["warn1"])
            >>> result.summary()
            'Check failed: 2 errors, 1 warning'
        """
        if self.is_valid:
            return "Check passed!"

        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error{'s' if len(self.errors) > 1 else ''}")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning{'s' if len(self.warnings) > 1 else ''}")

        return f"Check failed: {', '.join(parts)}"


def check_config(
    path: PathLike | dict,
    strict: bool = False,
    check_path: str | None = None,
) -> CheckResult:
    """Check configuration file for correctness.

    Performs the following checks:
    1. YAML syntax validation
    2. Reference resolution (checks all @references can be resolved)
    3. Circular dependency detection
    4. Expression validation (checks all $expressions can be evaluated)
    5. Component instantiation checks (validates _target_ references)

    Args:
        path: Path to config file or config dict
        strict: If True, treat warnings as errors
        check_path: Optional specific path within config to check (e.g., "model")

    Returns:
        CheckResult object with validation results

    Examples:
        >>> result = check_config("config.yaml")
        >>> if result.is_valid:
        ...     print("Config is valid!")
        >>> else:
        ...     for error in result.errors:
        ...         print(f"Error: {error}")
    """
    from .config_parser import ConfigParser
    from .exceptions import CircularReferenceError, ConfigKeyError, EvaluationError, InstantiationError

    errors = []
    warnings = []
    num_references = 0
    num_expressions = 0
    num_components = 0
    config_ids = []

    # Step 1: Load config (YAML syntax check)
    try:
        if isinstance(path, dict):
            parser = ConfigParser.load(path)
        else:
            parser = ConfigParser.load(path)
    except Exception as e:
        errors.append(f"YAML syntax error: {e}")
        return CheckResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
        )

    # Step 2: Count references, expressions, and components
    try:
        # Get all config items
        parser._parse()
        # Filter out metadata and empty IDs
        config_ids = [
            id_str
            for id_str in parser.ref_resolver.items.keys()
            if not id_str.startswith("_meta_") and id_str != ""
        ]

        # Count different types
        for item_id, item in parser.ref_resolver.items.items():
            config = item.get_config() if hasattr(item, "get_config") else item

            # Check if it's a reference
            if isinstance(config, str) and config.startswith("@"):
                num_references += 1

            # Check if it's an expression
            if isinstance(config, str) and config.startswith("$"):
                num_expressions += 1

            # Check if it's a component
            if isinstance(config, dict) and "_target_" in config:
                num_components += 1

    except Exception as e:
        errors.append(f"Error parsing config: {e}")

    # Step 3: Check each item individually to catch all errors
    # This allows us to report multiple errors instead of stopping at the first one
    if check_path:
        # Check specific path only
        try:
            parser.resolve(check_path)
        except CircularReferenceError as e:
            if strict:
                errors.append(f"Circular reference detected: {e}")
            else:
                warnings.append(f"Circular reference detected: {e}")
        except ConfigKeyError as e:
            errors.append(f"Reference resolution failed: {e}")
        except EvaluationError as e:
            errors.append(f"Expression evaluation failed: {e}")
        except InstantiationError as e:
            errors.append(f"Component instantiation failed: {e}")
        except Exception as e:
            errors.append(f"Unexpected error during resolution: {e}")
    else:
        # Check each item individually to collect all errors
        for item_id in config_ids:
            # Skip metadata
            if item_id.startswith("_meta_") or item_id == "":
                continue

            try:
                parser.resolve(item_id)
            except CircularReferenceError as e:
                if strict:
                    errors.append(f"Circular reference detected: {e}")
                else:
                    warnings.append(f"Circular reference detected: {e}")
            except ConfigKeyError as e:
                errors.append(f"Reference resolution failed: {e}")
            except EvaluationError as e:
                errors.append(f"Expression evaluation failed: {e}")
            except InstantiationError as e:
                errors.append(f"Component instantiation failed: {e}")
            except Exception:
                # Skip other errors silently to continue checking
                pass

    # Determine validity
    is_valid = len(errors) == 0
    if strict and warnings:
        is_valid = False

    return CheckResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        num_references=num_references,
        num_expressions=num_expressions,
        num_components=num_components,
        config_ids=config_ids,
    )


def list_config_ids(path: PathLike | dict, group_by_section: bool = True) -> dict[str, list[str]] | list[str]:
    """List all configuration IDs in a config file.

    Args:
        path: Path to config file or config dict
        group_by_section: If True, group IDs by top-level section (default: True)

    Returns:
        Dictionary mapping section names to lists of IDs if group_by_section=True,
        otherwise a flat list of all IDs

    Examples:
        >>> ids = list_config_ids("config.yaml")
        >>> print(ids)
        {'model': ['model::hidden_size', 'model::lr'], 'training': ['training::epochs']}

        >>> ids = list_config_ids("config.yaml", group_by_section=False)
        >>> print(ids)
        ['model', 'model::hidden_size', 'model::lr', 'training', 'training::epochs']
    """
    from .config_parser import ConfigParser

    # Load config
    if isinstance(path, dict):
        parser = ConfigParser.load(path)
    else:
        parser = ConfigParser.load(path)

    # Parse to get all IDs
    parser._parse()
    all_ids = sorted(parser.ref_resolver.items.keys())

    if not group_by_section:
        return all_ids

    # Group by section
    sections: dict[str, list[str]] = {}
    for id_str in all_ids:
        if "::" in id_str:
            section = id_str.split("::")[0]
        else:
            section = id_str

        if section not in sections:
            sections[section] = []

        sections[section].append(id_str)

    return sections


def format_check_result(result: CheckResult, filepath: str = "config", verbose: bool = False) -> str:
    """Format check result as human-readable text.

    Args:
        result: CheckResult object to format
        filepath: Name of config file being checked
        verbose: If True, show detailed statistics

    Returns:
        Formatted check result string

    Example output:
        ✓ Checking config.yaml

          ✓ YAML syntax valid
          ✓ All references resolved (12 references)
          ✓ No circular dependencies
          ✓ All expressions valid (5 expressions)

        Check passed!
    """
    from .errors.formatters import format_error, format_success, _get_colors_enabled

    lines = []

    # Header
    if result.is_valid:
        if _get_colors_enabled():
            lines.append(f"{format_success('✓')} Checking {filepath}")
        else:
            lines.append(f"✓ Checking {filepath}")
    else:
        if _get_colors_enabled():
            lines.append(f"{format_error('✗')} Checking {filepath}")
        else:
            lines.append(f"✗ Checking {filepath}")

    lines.append("")

    # Always show YAML syntax check (if we got this far, it passed)
    if _get_colors_enabled():
        lines.append(f"  {format_success('✓')} YAML syntax valid")
    else:
        lines.append(f"  ✓ YAML syntax valid")

    # Show reference resolution status
    if result.errors or result.warnings:
        # Check if there are reference errors
        ref_errors = [e for e in result.errors if "Reference" in e or "reference" in e]
        if ref_errors:
            if _get_colors_enabled():
                lines.append(f"  {format_error('✗')} Reference resolution failed ({len(ref_errors)} error{'s' if len(ref_errors) > 1 else ''})")
            else:
                lines.append(f"  ✗ Reference resolution failed ({len(ref_errors)} error{'s' if len(ref_errors) > 1 else ''})")
            for error in ref_errors:
                lines.append(f"      {error}")
        else:
            ref_count = f" ({result.num_references} references)" if verbose else ""
            if _get_colors_enabled():
                lines.append(f"  {format_success('✓')} All references resolved{ref_count}")
            else:
                lines.append(f"  ✓ All references resolved{ref_count}")

        # Check for circular dependency warnings
        circular_warnings = [w for w in result.warnings if "Circular" in w or "circular" in w]
        if circular_warnings:
            if _get_colors_enabled():
                lines.append(f"  {format_error('⚠')} Circular dependency detected ({len(circular_warnings)} warning{'s' if len(circular_warnings) > 1 else ''})")
            else:
                lines.append(f"  ⚠ Circular dependency detected ({len(circular_warnings)} warning{'s' if len(circular_warnings) > 1 else ''})")
            for warning in circular_warnings:
                lines.append(f"      {warning}")
        else:
            if _get_colors_enabled():
                lines.append(f"  {format_success('✓')} No circular dependencies")
            else:
                lines.append(f"  ✓ No circular dependencies")

        # Check for expression errors
        expr_errors = [e for e in result.errors if "Expression" in e or "expression" in e or "evaluation" in e]
        if expr_errors:
            if _get_colors_enabled():
                lines.append(f"  {format_error('✗')} Expression evaluation failed ({len(expr_errors)} error{'s' if len(expr_errors) > 1 else ''})")
            else:
                lines.append(f"  ✗ Expression evaluation failed ({len(expr_errors)} error{'s' if len(expr_errors) > 1 else ''})")
            for error in expr_errors:
                lines.append(f"      {error}")
        else:
            expr_count = f" ({result.num_expressions} expressions)" if verbose else ""
            if _get_colors_enabled():
                lines.append(f"  {format_success('✓')} All expressions valid{expr_count}")
            else:
                lines.append(f"  ✓ All expressions valid{expr_count}")

        # Check for component errors
        comp_errors = [e for e in result.errors if "Component" in e or "component" in e or "instantiation" in e]
        if comp_errors:
            if _get_colors_enabled():
                lines.append(f"  {format_error('✗')} Component instantiation failed ({len(comp_errors)} error{'s' if len(comp_errors) > 1 else ''})")
            else:
                lines.append(f"  ✗ Component instantiation failed ({len(comp_errors)} error{'s' if len(comp_errors) > 1 else ''})")
            for error in comp_errors:
                lines.append(f"      {error}")
        elif result.num_components > 0:
            comp_count = f" ({result.num_components} components)" if verbose else ""
            if _get_colors_enabled():
                lines.append(f"  {format_success('✓')} No instantiation errors{comp_count}")
            else:
                lines.append(f"  ✓ No instantiation errors{comp_count}")
    else:
        # All checks passed
        ref_count = f" ({result.num_references} references)" if verbose else ""
        expr_count = f" ({result.num_expressions} expressions)" if verbose else ""
        comp_count = f" ({result.num_components} components)" if verbose and result.num_components > 0 else ""

        if _get_colors_enabled():
            lines.append(f"  {format_success('✓')} All references resolved{ref_count}")
            lines.append(f"  {format_success('✓')} No circular dependencies")
            lines.append(f"  {format_success('✓')} All expressions valid{expr_count}")
            if result.num_components > 0:
                lines.append(f"  {format_success('✓')} No instantiation errors{comp_count}")
        else:
            lines.append(f"  ✓ All references resolved{ref_count}")
            lines.append(f"  ✓ No circular dependencies")
            lines.append(f"  ✓ All expressions valid{expr_count}")
            if result.num_components > 0:
                lines.append(f"  ✓ No instantiation errors{comp_count}")

    lines.append("")
    lines.append(result.summary())

    return "\n".join(lines)


def format_config_ids(ids: dict[str, list[str]] | list[str], filepath: str = "config") -> str:
    """Format config IDs list as human-readable text.

    Args:
        ids: Dictionary of section -> IDs or flat list of IDs
        filepath: Name of config file

    Returns:
        Formatted ID list string

    Example output:
        Configuration IDs in config.yaml:

        model
          model::hidden_size
          model::num_layers

        training
          training::epochs

        Total: 4 configuration items
    """
    lines = [f"Configuration IDs in {filepath}:", ""]

    if isinstance(ids, dict):
        for section in sorted(ids.keys()):
            lines.append(section)
            for id_str in sorted(ids[section]):
                if id_str != section:  # Don't repeat the section name
                    lines.append(f"  {id_str}")
            lines.append("")

        total = sum(len(id_list) for id_list in ids.values())
    else:
        for id_str in ids:
            lines.append(f"  {id_str}")
        total = len(ids)

    lines.append(f"Total: {total} configuration item{'s' if total != 1 else ''}")

    return "\n".join(lines)
