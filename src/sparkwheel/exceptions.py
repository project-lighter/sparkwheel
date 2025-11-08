"""Custom exceptions for sparkwheel with source location tracking and helpful error messages."""

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "SourceLocation",
    "SparkwheelError",
    "ModuleNotFoundError",
    "CircularReferenceError",
    "InstantiationError",
    "ConfigKeyError",
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


class SparkwheelError(Exception):
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


class ModuleNotFoundError(SparkwheelError):
    """Raised when a _target_ module/class/function cannot be located."""

    pass


class CircularReferenceError(SparkwheelError):
    """Raised when circular references are detected in config."""

    pass


class InstantiationError(SparkwheelError):
    """Raised when instantiating a component fails."""

    pass


class ConfigKeyError(SparkwheelError):
    """Raised when a config key is not found."""

    pass


class EvaluationError(SparkwheelError):
    """Raised when evaluating an expression fails."""

    pass
