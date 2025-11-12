"""Color formatting utilities for terminal output with auto-detection."""

import os
import sys

__all__ = [
    "enable_colors",
    "format_error",
    "format_suggestion",
    "format_code",
    "RED",
    "YELLOW",
    "GREEN",
    "BLUE",
    "GRAY",
    "RESET",
]

# ANSI color codes
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
BLUE = "\033[34m"
GRAY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Global flag for color support
_COLORS_ENABLED: bool | None = None


def _supports_color() -> bool:
    """Auto-detect if the terminal supports colors.

    Checks:
    1. NO_COLOR environment variable (universal standard)
    2. SPARKWHEEL_NO_COLOR environment variable (sparkwheel-specific)
    3. Terminal type and capabilities
    4. CI environment detection

    Returns:
        True if colors should be enabled, False otherwise
    """
    # Check NO_COLOR environment variable (https://no-color.org/)
    if os.environ.get("NO_COLOR"):
        return False

    # Check sparkwheel-specific disable flag
    if os.environ.get("SPARKWHEEL_NO_COLOR"):
        return False

    # Check if stdout is a TTY
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False

    # Check TERM environment variable
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False

    # Common CI environments - disable colors unless explicitly enabled
    ci_vars = ["CI", "CONTINUOUS_INTEGRATION", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI"]
    if any(os.environ.get(var) for var in ci_vars):
        # Unless explicitly requested with FORCE_COLOR
        if not os.environ.get("FORCE_COLOR"):
            return False

    # Default: enable colors
    return True


def enable_colors(enabled: bool | None = None) -> bool:
    """Enable or disable color output.

    Args:
        enabled: True to enable, False to disable, None for auto-detection

    Returns:
        Current color enable status

    Examples:
        >>> enable_colors(False)  # Disable colors
        False
        >>> enable_colors(True)   # Force enable colors
        True
        >>> enable_colors()       # Auto-detect
        True  # (if terminal supports it)
    """
    global _COLORS_ENABLED

    if enabled is None:
        _COLORS_ENABLED = _supports_color()
    else:
        _COLORS_ENABLED = enabled

    return _COLORS_ENABLED


def _get_colors_enabled() -> bool:
    """Get current color enable status, initializing if needed."""
    global _COLORS_ENABLED

    if _COLORS_ENABLED is None:
        enable_colors()  # Auto-detect

    return _COLORS_ENABLED  # type: ignore


def _colorize(text: str, color: str) -> str:
    """Apply color to text if colors are enabled.

    Args:
        text: Text to colorize
        color: ANSI color code

    Returns:
        Colorized text if colors enabled, otherwise plain text
    """
    if _get_colors_enabled():
        return f"{color}{text}{RESET}"
    return text


def format_error(text: str) -> str:
    """Format text as an error (red).

    Args:
        text: Text to format

    Returns:
        Formatted text

    Examples:
        >>> format_error("Error message")
        '\x1b[31mError message\x1b[0m'  # With colors enabled
        >>> format_error("Error message")
        'Error message'  # With colors disabled
    """
    return _colorize(text, RED)


def format_suggestion(text: str) -> str:
    """Format text as a suggestion (yellow).

    Args:
        text: Text to format

    Returns:
        Formatted text
    """
    return _colorize(text, YELLOW)


def format_success(text: str) -> str:
    """Format text as success/correct (green).

    Args:
        text: Text to format

    Returns:
        Formatted text
    """
    return _colorize(text, GREEN)


def format_code(text: str) -> str:
    """Format text as code/metadata (blue).

    Args:
        text: Text to format

    Returns:
        Formatted text
    """
    return _colorize(text, BLUE)


def format_context(text: str) -> str:
    """Format text as context (gray).

    Args:
        text: Text to format

    Returns:
        Formatted text
    """
    return _colorize(text, GRAY)


def format_bold(text: str) -> str:
    """Format text as bold.

    Args:
        text: Text to format

    Returns:
        Formatted text
    """
    if _get_colors_enabled():
        return f"{BOLD}{text}{RESET}"
    return text
