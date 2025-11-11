import os
import warnings
from collections.abc import Iterable
from typing import Any, TypeVar

from yaml import SafeLoader

__all__ = [
    "first",
    "issequenceiterable",
    "ensure_tuple",
    "check_key_duplicates",
    "CheckKeyDuplicatesYamlLoader",
]


T = TypeVar("T")


def first(iterable: Iterable[T], default: T | None = None) -> T | None:
    """
    Returns the first item in the given iterable or `default` if empty.
    """
    for i in iterable:
        return i
    return default


def issequenceiterable(obj: Any) -> bool:
    """
    Determine if the object is an iterable sequence and is not a string.
    """
    try:
        if hasattr(obj, "ndim") and obj.ndim == 0:
            return False  # a 0-d tensor is not iterable
    except Exception:
        return False
    return isinstance(obj, Iterable) and not isinstance(obj, (str, bytes))


def ensure_tuple(vals: Any) -> tuple:
    """
    Returns a tuple of `vals`.

    Args:
        vals: input data to convert to a tuple.
    """
    return tuple(vals) if issequenceiterable(vals) else (vals,)


def check_key_duplicates(ordered_pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
    """
    Checks if there is a duplicated key in the sequence of `ordered_pairs`.
    If there is - it will log a warning or raise ValueError
    (if configured by environmental var `SPARKWHEEL_STRICT_KEYS==1`)

    Otherwise, it returns the dict made from this sequence.

    Note: This function is kept for compatibility but is primarily used by the YAML loader.

    Args:
        ordered_pairs: sequence of (key, value)
    """
    keys = set()
    for k, _ in ordered_pairs:
        if k in keys:
            if os.environ.get("SPARKWHEEL_STRICT_KEYS", "0") == "1":
                raise ValueError(f"Duplicate key: `{k}`")
            else:
                warnings.warn(f"Duplicate key: `{k}`", stacklevel=2)
        else:
            keys.add(k)
    return dict(ordered_pairs)


class CheckKeyDuplicatesYamlLoader(SafeLoader):
    """
    YAML loader that detects duplicate keys and either warns or raises an error.
    Also tracks line numbers for values to enable better error reporting.
    """

    def __init__(self, stream):
        super().__init__(stream)
        # Store filename if available
        self.source_file = getattr(stream, "name", None)

    def construct_mapping(self, node, deep=False):
        mapping = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                if os.environ.get("SPARKWHEEL_STRICT_KEYS", "0") == "1":
                    raise ValueError(f"Duplicate key: `{key}`")
                else:
                    warnings.warn(f"Duplicate key: `{key}`", stacklevel=2)
            mapping.add(key)
        return super().construct_mapping(node, deep)

    def construct_object(self, node, deep=False):
        """Construct object and attach source location metadata."""
        obj = super().construct_object(node, deep)

        # Attach location metadata to the object if it's a dict or scalar
        # This allows us to track where each config value came from
        if hasattr(node, "start_mark") and self.source_file:
            # Store metadata as a special attribute that we can extract later
            # We'll use a tuple: (value, line, column, filepath)
            if isinstance(obj, dict):
                # For dicts, store location info in a special key
                obj["__sparkwheel_metadata__"] = {
                    "line": node.start_mark.line + 1,  # YAML uses 0-indexed lines
                    "column": node.start_mark.column,
                    "file": self.source_file,
                }

        return obj
