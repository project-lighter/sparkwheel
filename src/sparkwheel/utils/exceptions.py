"""Custom exceptions for sparkwheel with source location tracking and helpful error messages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "Location",
    "BaseError",
    "TargetNotFoundError",
    "CircularReferenceError",
    "InstantiationError",
    "ConfigKeyError",
    "ConfigMergeError",
    "EvaluationError",
    "FrozenConfigError",
    "build_missing_key_error",
]


@dataclass
class Location:
    """Tracks the location of a config item in source files.

    Attributes:
        filepath: Path to the source file
        line: Line number in the file (must be >= 1)
        column: Column number (0 if not available)
        id: Config path ID (e.g., "model::lr")
    """

    filepath: str
    line: int
    column: int = 0
    id: str = ""

    def __post_init__(self) -> None:
        """Validate line number after initialization."""
        if self.line < 1:
            raise ValueError(f"line must be >= 1, got {self.line}")

    def __str__(self) -> str:
        return f"{self.filepath}:{self.line}"


class BaseError(Exception):
    """Base exception for sparkwheel with rich error context.

    Attributes:
        message: The error message
        source_location: Optional location in config file where error occurred
        suggestion: Optional helpful suggestion for fixing the error
    """

    def __init__(
        self,
        message: str,
        source_location: Location | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.source_location = source_location
        self.suggestion = suggestion
        self._original_message = message
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with source location and suggestions.

        Critical info (file:line) is on the first line for Rich compatibility,
        since Rich's traceback only shows the first line of exception messages.
        """
        parts = []

        # Put file:line on the FIRST line for Rich visibility
        if self.source_location:
            location = f"{self.source_location.filepath}:{self.source_location.line}"
            if self.source_location.id:
                parts.append(f"[{location} → {self.source_location.id}] {self._original_message}")
            else:
                parts.append(f"[{location}] {self._original_message}")
        else:
            parts.append(self._original_message)

        # Add code snippet on subsequent lines (will be visible in full traceback)
        if self.source_location:
            snippet = self._get_config_snippet()
            if snippet:
                parts.append(f"\n\n{snippet}")

        if self.suggestion:
            parts.append(f"\n\n  💡 {self.suggestion}")

        return "".join(parts)

    def _get_config_snippet(self) -> str:
        """Extract and format a code snippet from the config file."""
        if not self.source_location:
            return ""

        try:
            filepath = Path(self.source_location.filepath)
            if not filepath.exists():
                return ""

            with open(filepath) as f:
                lines = f.readlines()

            # Show 2 lines before and 1 line after the error
            line_num = self.source_location.line
            start = max(0, line_num - 3)
            end = min(len(lines), line_num + 2)

            snippet_lines = []
            for i in range(start, end):
                marker = "→" if i == line_num - 1 else " "
                # Use 4-digit line numbers for alignment
                snippet_lines.append(f"  {marker} {i + 1:4d} │ {lines[i].rstrip()}")

            return "\n".join(snippet_lines)
        except Exception:
            # If we can't read the file, just skip the snippet
            return ""


class TargetNotFoundError(BaseError):
    """Raised when a _target_ module/class/function cannot be located."""

    pass


class CircularReferenceError(BaseError):
    """Raised when circular references are detected in config."""

    pass


class InstantiationError(BaseError):
    """Raised when instantiating a component fails."""

    pass


class ConfigKeyError(BaseError):
    """Raised when a config key is not found.

    Supports smart suggestions and available keys display.
    """

    def __init__(
        self,
        message: str,
        source_location: Location | None = None,
        suggestion: str | None = None,
        missing_key: str | None = None,
        available_keys: list[str] | None = None,
        config_context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ConfigKeyError with enhanced context.

        Args:
            message: Error message
            source_location: Location where error occurred
            suggestion: Manual suggestion (optional)
            missing_key: The key that wasn't found
            available_keys: List of available keys for suggestions
            config_context: The config dict where the key wasn't found (for displaying available keys)
        """
        self.missing_key = missing_key
        self.available_keys = available_keys or []
        self.config_context = config_context

        # Auto-generate suggestion if not provided
        if not suggestion and missing_key and available_keys:
            suggestion = self._generate_suggestion()

        super().__init__(message, source_location, suggestion)

    def _generate_suggestion(self) -> str | None:
        """Generate smart suggestion with typo detection and available keys."""
        from ..errors import format_available_keys, format_suggestions, get_suggestions

        parts = []

        # Try to find similar keys
        if self.missing_key and self.available_keys:
            suggestions = get_suggestions(self.missing_key, self.available_keys)
            if suggestions:
                parts.append(format_suggestions(suggestions))

        # Show available keys if we have config context and not too many keys
        if self.config_context and len(self.config_context) <= 10:
            available = format_available_keys(self.config_context)
            if available:
                if parts:
                    parts.append("")  # Blank line separator
                parts.append(available)

        return "\n".join(parts) if parts else None


class ConfigMergeError(BaseError):
    """Raised when configuration merge operation fails.

    This is typically raised when using operators (= or ~) incorrectly:
    - Using ~ on a non-existent key
    - Using ~ with invalid value (must be null, empty, or list)
    - Type mismatch during merge (e.g., trying to merge dict into list)
    """

    pass


class EvaluationError(BaseError):
    """Raised when evaluating an expression fails."""

    pass


class FrozenConfigError(BaseError):
    """Raised when attempting to modify a frozen config.

    Attributes:
        message: Error description
        field_path: Path that was attempted to modify
    """

    def __init__(self, message: str, field_path: str = ""):
        self.field_path = field_path
        full_message = message
        if field_path:
            full_message = f"Cannot modify frozen config at '{field_path}': {message}"
        super().__init__(full_message)


def build_missing_key_error(
    key: str,
    available_keys: list[str],
    source_location: Location | None = None,
    *,
    max_suggestions: int = 3,
    max_available_keys: int = 10,
    parent_key: str | None = None,
) -> ConfigMergeError:
    """Build a ConfigMergeError for a missing key with helpful suggestions.

    Args:
        key: The key that wasn't found
        available_keys: List of available keys to compare against
        source_location: Optional location where error occurred
        max_suggestions: Maximum number of suggestions to show (default: 3)
        max_available_keys: Maximum number of available keys to show (default: 10)
        parent_key: Optional parent key for nested deletions (e.g., "model" when deleting "model.lr")

    Returns:
        ConfigMergeError with helpful suggestions

    Examples:
        >>> error = build_missing_key_error("paramters", ["parameters", "param_groups"])
        >>> print(error._original_message)
        Cannot delete key 'paramters': key does not exist

        >>> error = build_missing_key_error("lr", ["learning_rate"], parent_key="model")
        >>> print(error._original_message)
        Cannot remove non-existent key 'lr' from 'model'
    """
    from ..errors import get_suggestions
    from .constants import SIMILARITY_THRESHOLD

    # Build appropriate message based on context
    if parent_key:
        message = f"Cannot remove non-existent key '{key}' from '{parent_key}'"
    else:
        message = f"Cannot delete key '{key}': key does not exist"

    suggestion_parts = []
    if available_keys:
        suggestions = get_suggestions(
            key, available_keys, max_suggestions=max_suggestions, similarity_threshold=SIMILARITY_THRESHOLD
        )
        if suggestions:
            suggestion_keys = [s[0] for s in suggestions]
            suggestion_parts.append(f"Did you mean: {', '.join(repr(s) for s in suggestion_keys)}?")

        if len(available_keys) <= max_available_keys:
            suggestion_parts.append(f"Available keys: {', '.join(repr(k) for k in available_keys)}")

    suggestion = "\n".join(suggestion_parts) if suggestion_parts else None
    return ConfigMergeError(message, source_location=source_location, suggestion=suggestion)
