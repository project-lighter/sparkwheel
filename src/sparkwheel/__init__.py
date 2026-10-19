"""
sparkwheel: A powerful YAML-based configuration system with references, expressions, and dynamic instantiation.

Uses YAML format only.
"""

from .config import Config
from .items import Component, Expression, Instantiable, Item
from .operators import apply_operators
from .resolver import Resolver
from .schema import MISSING, ValidationError, validate, validator
from .utils.constants import COMBINE_KEY, EXPR_KEY, ID_SEP_KEY, RAW_REF_KEY, REMOVE_KEY, RESOLVED_REF_KEY
from .utils.exceptions import (
    BaseError,
    CircularReferenceError,
    ConfigKeyError,
    ConfigMergeError,
    EvaluationError,
    FrozenConfigError,
    InstantiationError,
    Location,
    TargetNotFoundError,
)

__version__ = "0.0.11"

__all__ = [
    "__version__",
    "Config",
    "MISSING",
    "Item",
    "Component",
    "Expression",
    "Instantiable",
    "Resolver",
    "apply_operators",
    "validate",
    "validator",
    "RESOLVED_REF_KEY",
    "RAW_REF_KEY",
    "ID_SEP_KEY",
    "EXPR_KEY",
    "REMOVE_KEY",
    "COMBINE_KEY",
    "BaseError",
    "TargetNotFoundError",
    "CircularReferenceError",
    "InstantiationError",
    "ConfigKeyError",
    "ConfigMergeError",
    "EvaluationError",
    "FrozenConfigError",
    "ValidationError",
    "Location",
]
