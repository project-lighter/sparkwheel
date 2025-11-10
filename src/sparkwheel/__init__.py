"""
sparkwheel: A powerful YAML-based configuration system with references, expressions, and dynamic instantiation.

Uses YAML format only.
"""

from .check import CheckResult, check_config, format_check_result, format_config_ids, list_config_ids
from .cli import parse_args
from .config_item import ConfigComponent, ConfigExpression, ConfigItem, Instantiable
from .config_parser import ConfigParser
from .constants import EXPR_KEY, ID_REF_KEY, ID_SEP_KEY, MACRO_KEY
from .diff import ConfigDiff, diff_configs, format_diff_json, format_diff_tree, format_diff_unified
from .errors import enable_colors
from .exceptions import (
    BaseError,
    CircularReferenceError,
    ConfigKeyError,
    ConfigMergeError,
    EvaluationError,
    InstantiationError,
    ModuleNotFoundError,
    SourceLocation,
)
from .merge import merge_configs
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
    "merge_configs",
    "parse_args",
    "enable_colors",
    "ConfigDiff",
    "diff_configs",
    "format_diff_tree",
    "format_diff_unified",
    "format_diff_json",
    "CheckResult",
    "check_config",
    "list_config_ids",
    "format_check_result",
    "format_config_ids",
    "ID_REF_KEY",
    "ID_SEP_KEY",
    "EXPR_KEY",
    "MACRO_KEY",
    "BaseError",
    "ModuleNotFoundError",
    "CircularReferenceError",
    "InstantiationError",
    "ConfigKeyError",
    "ConfigMergeError",
    "EvaluationError",
    "SourceLocation",
]
