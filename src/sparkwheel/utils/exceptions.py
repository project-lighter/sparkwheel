"""Custom exceptions for sparkwheel with source location tracking and helpful error messages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "SourceLocation",
    "BaseError",
    "ModuleNotFoundError",
    "CircularReferenceError",
    "InstantiationError",
    "ConfigKeyError",
    "ConfigMergeError",
    "EvaluationError",
]


@dataclass
class SourceLocation:
    """Tracks the source location of a config item."""

    filepath: str
    line: int
    column: int = 0
    id: str = ""

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
        source_location: SourceLocation | None = None,
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
                parts.append(f"[{location} @ {self.source_location.id}] {self._original_message}")
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


class ModuleNotFoundError(BaseError):
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
        source_location: SourceLocation | None = None,
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

    This is typically raised when using merge directives (+ or ~) incorrectly:
    - Using + on a non-existent key
    - Using + with type mismatch (e.g., trying to merge dict into list)
    - Using ~ on a non-existent key
    """

    pass


class EvaluationError(BaseError):
    """Raised when evaluating an expression fails."""

    pass
