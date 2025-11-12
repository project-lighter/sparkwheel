"""
sparkwheel: A powerful YAML-based configuration system with references, expressions, and dynamic instantiation.

Uses YAML format only.
"""

from .cli import parse_override, parse_overrides
from .config import Config
from .errors import enable_colors
from .items import Component, Expression, Instantiable, Item
from .operators import apply_operators
from .resolver import Resolver
from .schema import ValidationError, validate
from .utils.constants import DELETE_KEY, EXPR_KEY, ID_REF_KEY, ID_SEP_KEY, MACRO_KEY, MERGE_KEY
from .utils.exceptions import (
    BaseError,
    CircularReferenceError,
    ConfigKeyError,
    ConfigMergeError,
    EvaluationError,
    InstantiationError,
    ModuleNotFoundError,
    SourceLocation,
)

__version__ = "0.0.3"

__all__ = [
    "__version__",
    "Config",
    "Item",
    "Component",
    "Expression",
    "Instantiable",
    "Resolver",
    "apply_operators",
    "validate",
    "parse_override",
    "parse_overrides",
    "enable_colors",
    "ID_REF_KEY",
    "ID_SEP_KEY",
    "EXPR_KEY",
    "MACRO_KEY",
    "DELETE_KEY",
    "MERGE_KEY",
    "BaseError",
    "ModuleNotFoundError",
    "CircularReferenceError",
    "InstantiationError",
    "ConfigKeyError",
    "ConfigMergeError",
    "EvaluationError",
    "ValidationError",
    "SourceLocation",
]
