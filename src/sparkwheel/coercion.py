"""Type coercion for schema validation."""

import dataclasses
import types
from typing import Any, Union, get_args, get_origin

__all__ = ["coerce_value", "can_coerce"]


def _is_union_type(origin: Any) -> bool:
    """Check if origin is a Union type."""
    if origin is Union:
        return True
    if hasattr(types, "UnionType") and origin is types.UnionType:
        return True
    return False


def can_coerce(value: Any, target_type: type) -> bool:
    """Check if value can be coerced to target type."""
    if isinstance(value, target_type):
        return True

    # String to numeric
    if target_type in (int, float) and isinstance(value, str):
        try:
            target_type(value)
            return True
        except (ValueError, TypeError):
            return False

    # Int to float
    if target_type is float and isinstance(value, int):
        return True

    # String to bool
    if target_type is bool and isinstance(value, str):
        return value.lower() in ("true", "false", "1", "0", "yes", "no")

    return False


def coerce_value(value: Any, target_type: type, field_path: str = "") -> Any:
    """Coerce value to target type if possible.

    Args:
        value: Value to coerce
        target_type: Target type (may be generic like List[int])
        field_path: Path for error messages

    Returns:
        Coerced value

    Raises:
        ValueError: If coercion not possible
    """
    origin = get_origin(target_type)
    args = get_args(target_type)

    # Handle Union types (including Optional)
    if _is_union_type(origin):
        # Try coercing to each type in order
        for union_type in args:
            if union_type is type(None) and value is None:
                return None
            try:
                return coerce_value(value, union_type, field_path)
            except (ValueError, TypeError):
                continue
        # No coercion worked
        raise ValueError(f"Cannot coerce {type(value).__name__} to any type in union at '{field_path}'")

    # Handle List[T]
    if origin is list:
        if not isinstance(value, list):
            raise ValueError(f"Cannot coerce {type(value).__name__} to list")
        if args:
            item_type = args[0]
            return [coerce_value(item, item_type, f"{field_path}[{i}]") for i, item in enumerate(value)]
        return value

    # Handle Dict[K, V]
    if origin is dict:
        if not isinstance(value, dict):
            raise ValueError(f"Cannot coerce {type(value).__name__} to dict")
        if args and len(args) == 2:
            key_type, val_type = args
            return {
                coerce_value(k, key_type, f"{field_path}.key"): coerce_value(v, val_type, f"{field_path}[{k!r}]")
                for k, v in value.items()
            }
        return value

    # Handle nested dataclasses - recursively coerce fields
    if dataclasses.is_dataclass(target_type):
        if not isinstance(value, dict):
            raise ValueError(f"Cannot coerce {type(value).__name__} to dataclass {target_type.__name__}")

        coerced = {}
        schema_fields = {f.name: f for f in dataclasses.fields(target_type)}

        for field_name, field_value in value.items():
            if field_name in schema_fields:
                field_info = schema_fields[field_name]
                field_path_full = f"{field_path}.{field_name}" if field_path else field_name
                # field_info.type can be str in some edge cases, but for our use it's always type
                assert isinstance(field_info.type, type)
                coerced[field_name] = coerce_value(field_value, field_info.type, field_path_full)
            else:
                # Keep unknown fields as-is (strict mode will catch them)
                coerced[field_name] = field_value

        return coerced

    # Already correct type
    if isinstance(value, target_type):
        return value

    # String to numeric
    if target_type in (int, float):
        if isinstance(value, str):
            try:
                return target_type(value)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Cannot coerce string '{value}' to {target_type.__name__}") from e

    # Int to float
    if target_type is float and isinstance(value, int):
        return float(value)

    # String to bool
    if target_type is bool and isinstance(value, str):
        lower = value.lower()
        if lower in ("true", "1", "yes"):
            return True
        elif lower in ("false", "0", "no"):
            return False
        else:
            raise ValueError(f"Cannot coerce string '{value}' to bool")

    # No coercion available
    raise ValueError(f"Cannot coerce {type(value).__name__} to {target_type.__name__}")
