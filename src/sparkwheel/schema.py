"""Schema validation using dataclasses.

This module provides structured config validation using Python dataclasses.
Define configuration schemas with type hints, then validate your YAML
configs against them at runtime.

Example:
    ```python
    from dataclasses import dataclass
    from typing import Optional
    from sparkwheel import Config
    from sparkwheel.schema import validate

    @dataclass
    class OptimizerConfig:
        lr: float
        momentum: float = 0.9
        weight_decay: Optional[float] = None

    @dataclass
    class ModelConfig:
        hidden_size: int
        num_layers: int
        dropout: float
        optimizer: OptimizerConfig

    # Load and validate config
    config = Config.load("config.yaml")
    validate(config.get(), ModelConfig)  # Raises error if invalid

    # Or validate during load
    config = Config.load("config.yaml", schema=ModelConfig)
    ```
"""

from __future__ import annotations

import dataclasses
from typing import Any, Union, get_args, get_origin

from .utils.exceptions import BaseError, SourceLocation

__all__ = ["validate", "ValidationError"]


class ValidationError(BaseError):
    """Raised when configuration validation fails.

    Attributes:
        message: Error description
        field_path: Dot-separated path to the invalid field (e.g., "model.optimizer.lr")
        expected_type: The type that was expected
        actual_value: The value that failed validation
        source_location: Optional location in source file where error occurred
    """

    def __init__(
        self,
        message: str,
        field_path: str = "",
        expected_type: type | None = None,
        actual_value: Any = None,
        source_location: SourceLocation | None = None,
    ):
        """Initialize validation error.

        Args:
            message: Human-readable error message
            field_path: Dot-separated path to invalid field
            expected_type: Expected type for the field
            actual_value: The actual value that failed validation
            source_location: Source location where the invalid value was defined
        """
        self.field_path = field_path
        self.expected_type = expected_type
        self.actual_value = actual_value

        # Build detailed message
        full_message = message
        if field_path:
            full_message = f"Validation error at '{field_path}': {message}"
        if expected_type is not None:
            type_name = getattr(expected_type, "__name__", str(expected_type))
            full_message += f"\n  Expected type: {type_name}"
        if actual_value is not None:
            actual_type = type(actual_value).__name__
            full_message += f"\n  Actual type: {actual_type}"
            full_message += f"\n  Actual value: {actual_value!r}"

        super().__init__(full_message, source_location=source_location)


def validate(
    config: dict[str, Any],
    schema: type,
    field_path: str = "",
    metadata: Any = None,
) -> None:
    """Validate configuration against a dataclass schema.

    Performs recursive type checking to ensure the configuration matches
    the structure and types defined in the dataclass schema.

    Args:
        config: Configuration dictionary to validate
        schema: Dataclass type defining the expected structure
        field_path: Internal parameter for tracking nested field paths
        metadata: Optional metadata registry for source locations

    Raises:
        ValidationError: If validation fails
        TypeError: If schema is not a dataclass

    Example:
        ```python
        from dataclasses import dataclass
        from sparkwheel import Config
        from sparkwheel.schema import validate

        @dataclass
        class AppConfig:
            name: str
            port: int
            debug: bool = False

        config = Config.load("app.yaml")
        validate(config.get(), AppConfig)
        ```
    """
    if not dataclasses.is_dataclass(schema):
        raise TypeError(f"Schema must be a dataclass, got {type(schema).__name__}")

    if not isinstance(config, dict):
        source_loc = _get_source_location(metadata, field_path) if metadata else None
        raise ValidationError(
            f"Expected dict for dataclass {schema.__name__}",
            field_path=field_path,
            expected_type=dict,
            actual_value=config,
            source_location=source_loc,
        )

    # Get all fields from the dataclass
    schema_fields = {f.name: f for f in dataclasses.fields(schema)}

    # Check for required fields
    for field_name, field_info in schema_fields.items():
        current_path = f"{field_path}.{field_name}" if field_path else field_name

        # Check if field is missing
        if field_name not in config:
            # Field has default or default_factory -> optional
            if field_info.default is not dataclasses.MISSING or field_info.default_factory is not dataclasses.MISSING:  # type: ignore
                continue
            # No default -> required
            source_loc = _get_source_location(metadata, field_path) if metadata else None
            raise ValidationError(
                f"Missing required field '{field_name}'",
                field_path=current_path,
                expected_type=field_info.type,
                source_location=source_loc,
            )

        # Validate the field value
        _validate_field(
            config[field_name],
            field_info.type,
            current_path,
            metadata,
        )

    # Check for unexpected fields
    unexpected_fields = set(config.keys()) - set(schema_fields.keys())
    # Filter out sparkwheel special keys
    special_keys = {"_target_", "_disabled_", "_requires_", "_mode_"}
    unexpected_fields = unexpected_fields - special_keys

    if unexpected_fields:
        first_unexpected = sorted(unexpected_fields)[0]
        current_path = f"{field_path}.{first_unexpected}" if field_path else first_unexpected
        source_loc = _get_source_location(metadata, current_path) if metadata else None
        raise ValidationError(
            f"Unexpected field '{first_unexpected}' not in schema {schema.__name__}",
            field_path=current_path,
            source_location=source_loc,
        )


def _validate_field(
    value: Any,
    expected_type: type,
    field_path: str,
    metadata: Any = None,
) -> None:
    """Validate a single field value against its expected type.

    Args:
        value: The value to validate
        expected_type: The expected type (may be generic like list[int])
        field_path: Dot-separated path to this field
        metadata: Optional metadata registry for source locations

    Raises:
        ValidationError: If validation fails
    """
    source_loc = _get_source_location(metadata, field_path) if metadata else None

    # Handle None values
    origin = get_origin(expected_type)
    args = get_args(expected_type)

    # Handle Optional[T] (which is Union[T, None])
    if origin is Union:
        # Check if None is allowed
        if type(None) in args:
            if value is None:
                return  # None is valid
            # Remove None from the union and validate against remaining types
            non_none_types = [t for t in args if t is not type(None)]
            if len(non_none_types) == 1:
                # Simple Optional[T] case
                expected_type = non_none_types[0]
                origin = get_origin(expected_type)
                args = get_args(expected_type)
            else:
                # Union with multiple non-None types - try each
                for union_type in non_none_types:
                    try:
                        _validate_field(value, union_type, field_path, metadata)
                        return  # Validation succeeded
                    except ValidationError:
                        continue  # Try next type
                # None worked
                raise ValidationError(
                    "Value doesn't match any type in Union",
                    field_path=field_path,
                    expected_type=expected_type,
                    actual_value=value,
                    source_location=source_loc,
                )
        else:
            # Non-Optional Union - try each type
            for union_type in args:
                try:
                    _validate_field(value, union_type, field_path, metadata)
                    return
                except ValidationError:
                    continue
            raise ValidationError(
                "Value doesn't match any type in Union",
                field_path=field_path,
                expected_type=expected_type,
                actual_value=value,
                source_location=source_loc,
            )

    # Handle list[T]
    if origin is list:
        if not isinstance(value, list):
            raise ValidationError(
                "Expected list",
                field_path=field_path,
                expected_type=list,
                actual_value=value,
                source_location=source_loc,
            )
        if args:
            item_type = args[0]
            for i, item in enumerate(value):
                _validate_field(
                    item,
                    item_type,
                    f"{field_path}[{i}]",
                    metadata,
                )
        return

    # Handle dict[K, V]
    if origin is dict:
        if not isinstance(value, dict):
            raise ValidationError(
                "Expected dict",
                field_path=field_path,
                expected_type=dict,
                actual_value=value,
                source_location=source_loc,
            )
        if args and len(args) == 2:
            key_type, value_type = args
            for k, v in value.items():
                # Validate key type
                if not isinstance(k, key_type):
                    raise ValidationError(
                        "Dict key has wrong type",
                        field_path=f"{field_path}[{k!r}]",
                        expected_type=key_type,
                        actual_value=k,
                        source_location=source_loc,
                    )
                # Validate value type
                _validate_field(
                    v,
                    value_type,
                    f"{field_path}[{k!r}]",
                    metadata,
                )
        return

    # Handle nested dataclasses
    if dataclasses.is_dataclass(expected_type):
        validate(value, expected_type, field_path, metadata)
        return

    # Handle basic types (int, str, float, bool, etc.)
    if not isinstance(value, expected_type):
        # Special case: accept references (@) and expressions ($) as strings
        # since they'll be resolved later
        if isinstance(value, str) and (value.startswith("@") or value.startswith("$") or value.startswith("%")):
            # This is a reference/expression/macro that will be resolved later
            # We can't validate its type until resolution
            return

        # Special case: allow int for float
        if expected_type is float and isinstance(value, int):
            return

        raise ValidationError(
            "Type mismatch",
            field_path=field_path,
            expected_type=expected_type,
            actual_value=value,
            source_location=source_loc,
        )


def _get_source_location(metadata: Any, field_path: str) -> SourceLocation | None:
    """Get source location from metadata registry.

    Args:
        metadata: MetadataRegistry instance
        field_path: Dot-separated field path to look up

    Returns:
        SourceLocation if found, None otherwise
    """
    if metadata is None:
        return None

    try:
        # Convert dot notation to :: notation used by sparkwheel
        id_path = field_path.replace(".", "::")
        return metadata.get(id_path)
    except Exception:
        return None
