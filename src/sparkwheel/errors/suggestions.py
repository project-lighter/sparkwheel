"""Smart suggestions for typos and common mistakes using Levenshtein distance."""

from typing import Sequence

__all__ = ["get_suggestions", "levenshtein_distance"]


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein distance between two strings.

    The Levenshtein distance is the minimum number of single-character edits
    (insertions, deletions, or substitutions) required to change one word into another.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Integer representing the edit distance between s1 and s2

    Examples:
        >>> levenshtein_distance("kitten", "sitting")
        3
        >>> levenshtein_distance("hello", "hello")
        0
        >>> levenshtein_distance("hello", "helo")
        1
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    # Create distance matrix
    previous_row = range(len(s2) + 1)

    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def get_suggestions(
    key: str,
    available_keys: Sequence[str],
    max_suggestions: int = 3,
    similarity_threshold: float = 0.6,
) -> list[tuple[str, float]]:
    """Get suggestions for a potentially misspelled key.

    Uses Levenshtein distance to find similar keys and ranks them by similarity.

    Args:
        key: The key that wasn't found
        available_keys: List of available keys to compare against
        max_suggestions: Maximum number of suggestions to return (default: 3)
        similarity_threshold: Minimum similarity score (0-1) for suggestions (default: 0.6)
                             Lower values are more lenient, higher values are stricter

    Returns:
        List of (suggestion, similarity_score) tuples, sorted by similarity (best first)

    Examples:
        >>> keys = ["parameters", "param_groups", "learning_rate", "weight_decay"]
        >>> get_suggestions("paramters", keys)
        [('parameters', 0.9), ('param_groups', 0.54)]
        >>> get_suggestions("lr", keys)
        []  # No matches above threshold
    """
    if not key or not available_keys:
        return []

    scored_suggestions = []

    for candidate in available_keys:
        # Calculate similarity score (1.0 = perfect match, 0.0 = completely different)
        max_len = max(len(key), len(candidate))
        if max_len == 0:
            continue

        distance = levenshtein_distance(key.lower(), candidate.lower())
        similarity = 1.0 - (distance / max_len)

        # Only include suggestions above threshold
        if similarity >= similarity_threshold:
            scored_suggestions.append((candidate, similarity))

    # Sort by similarity (best first) and limit to max_suggestions
    scored_suggestions.sort(key=lambda x: x[1], reverse=True)
    return scored_suggestions[:max_suggestions]


def format_suggestions(suggestions: list[tuple[str, float]]) -> str:
    """Format suggestion list for display in error messages.

    Args:
        suggestions: List of (suggestion, similarity_score) tuples

    Returns:
        Formatted string with suggestions, or empty string if no suggestions

    Examples:
        >>> format_suggestions([('parameters', 0.9), ('param_groups', 0.54)])
        '💡 Did you mean one of these?\\n    - parameters ✓ (90% match)\\n    - param_groups (54% match)'
    """
    if not suggestions:
        return ""

    lines = ["💡 Did you mean one of these?"]
    for suggestion, score in suggestions:
        # Add checkmark for very close matches (>80% similarity)
        check = " ✓" if score > 0.8 else ""
        percentage = int(score * 100)
        lines.append(f"    - {suggestion}{check} ({percentage}% match)")

    return "\n".join(lines)
