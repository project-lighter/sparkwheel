from collections.abc import Iterable
from typing import Any, TypeVar

__all__ = [
    "first",
    "issequenceiterable",
    "ensure_tuple",
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


def ensure_tuple(vals: Any) -> tuple[Any, ...]:
    """
    Returns a tuple of `vals`.

    Args:
        vals: input data to convert to a tuple.
    """
    return tuple(vals) if issequenceiterable(vals) else (vals,)
