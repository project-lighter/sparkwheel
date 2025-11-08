"""
sparkwheel: A powerful YAML-based configuration system with references, expressions, and dynamic instantiation.

Uses YAML format only.
"""

from .config_item import ConfigComponent, ConfigExpression, ConfigItem, Instantiable
from .config_parser import ConfigParser
from .constants import EXPR_KEY, ID_REF_KEY, ID_SEP_KEY, MACRO_KEY
from .exceptions import (
    CircularReferenceError,
    ConfigKeyError,
    EvaluationError,
    InstantiationError,
    ModuleNotFoundError,
    SourceLocation,
    SparkwheelError,
)
from .reference_resolver import ReferenceResolver

__version__ = "0.0.2"

__all__ = [
    "__version__",
    "ConfigParser",
    "ConfigItem",
    "ConfigComponent",
    "ConfigExpression",
    "Instantiable",
    "ReferenceResolver",
    "ID_REF_KEY",
    "ID_SEP_KEY",
    "EXPR_KEY",
    "MACRO_KEY",
    "SparkwheelError",
    "ModuleNotFoundError",
    "CircularReferenceError",
    "InstantiationError",
    "ConfigKeyError",
    "EvaluationError",
    "SourceLocation",
]
