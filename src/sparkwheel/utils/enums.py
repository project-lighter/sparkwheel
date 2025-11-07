from enum import Enum

__all__ = ["CompInitMode"]


class StrEnum(str, Enum):
    """String enumeration base class."""

    pass


class CompInitMode(StrEnum):
    """
    Component initialization mode for ConfigComponent.

    - DEFAULT: Instantiate by calling the component
    - CALLABLE: Return the callable (or partial with kwargs)
    - DEBUG: Use pdb.runcall for debugging
    """

    DEFAULT = "default"
    CALLABLE = "callable"
    DEBUG = "debug"
