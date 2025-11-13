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

import dataclasses
from typing import Any, Union, get_args, get_origin

from .utils.exceptions import BaseError, SourceLocation

__all__ = ["validate", "validator", "ValidationError"]


def validator(func):
    """Decorator to mark a method as a validator.

    Validators run after type checking and can validate single fields
    or relationships between fields. Raise ValueError on failure.

    Example:
        @dataclass
        class Config:
            lr: float
            start: int
            end: int

            @validator
            def check_lr(self):
                if not (0 < self.lr < 1):
                    raise ValueError("lr must be between 0 and 1")

            @validator
            def check_range(self):
                if self.end <= self.start:
                    raise ValueError("end must be > start")
    """
    func.__is_validator__ = True
    return func


def _get_validators(schema_type: type) -> list:
    """Get all validator methods from a dataclass."""
    validators = []
    for attr_name in dir(schema_type):
        if attr_name.startswith("_"):
            continue
        try:
            attr = getattr(schema_type, attr_name)
            if callable(attr) and getattr(attr, "__is_validator__", False):
                validators.append(attr)
        except AttributeError:
            continue
    return validators


def _run_validators(
    config: dict[str, Any],
    schema: type,
    field_path: str = "",
    metadata: Any = None,
) -> None:
    """Run all @validator methods on a dataclass.

    Args:
        config: Configuration dict
        schema: Dataclass type
        field_path: Path to this config
        metadata: Optional metadata

    Raises:
        ValidationError: If validation fails
    """
    validators = _get_validators(schema)
    if not validators:
        return

    # Skip validation for configs with references/expressions/macros
    # They'll be validated after resolution
    for value in config.values():
        if isinstance(value, str) and value.startswith(("@", "$", "%")):
            # Has unresolved references - skip custom validation
            return

    # Create instance to call validators on
    try:
        instance = schema(**config)
    except Exception:
        # Can't create instance - skip validation
        return

    source_loc = _get_source_location(metadata, field_path) if metadata else None

    for validator_method in validators:
        try:
            validator_method(instance)
        except ValueError as e:
            raise ValidationError(
                str(e),
                field_path=field_path,
                source_location=source_loc,
            ) from e
        except Exception as e:
            raise ValidationError(
                f"Validator '{validator_method.__name__}' raised {type(e).__name__}: {e}",
                field_path=field_path,
                source_location=source_loc,
            ) from e


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
            if field_info.default is not dataclasses.MISSING or field_info.default_factory is not dataclasses.MISSING:  # type: ignore[comparison-overlap]
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

    # Run custom validators
    _run_validators(config, schema, field_path, metadata)


def _find_discriminator(union_types: tuple) -> tuple[bool, str | None]:
    """Find discriminator field in a Union of dataclasses.

    A discriminator is a field that:
    - Exists in all dataclass types in the Union
    - Has Literal type annotation
    - Has unique values per type

    Args:
        union_types: Types in the Union

    Returns:
        (has_discriminator, field_name)
    """
    from typing import Literal

    # Filter to dataclasses only
    dataclass_types = [t for t in union_types if dataclasses.is_dataclass(t)]
    if len(dataclass_types) < 2:
        return False, None

    # Find fields that exist in all types with Literal annotation
    all_fields = {}
    for dc_type in dataclass_types:
        for f in dataclasses.fields(dc_type):
            if get_origin(f.type) is Literal:
                if f.name not in all_fields:
                    all_fields[f.name] = []
                literal_values = get_args(f.type)
                all_fields[f.name].append({"type": dc_type, "values": literal_values})

    # Find a field present in all types with unique values
    for field_name, type_infos in all_fields.items():
        if len(type_infos) != len(dataclass_types):
            continue  # Not in all types

        # Check values are unique across types
        all_values = set()
        is_unique = True
        for info in type_infos:
            for val in info["values"]:
                if val in all_values:
                    is_unique = False
                    break
                all_values.add(val)
            if not is_unique:
                break

        if is_unique:
            return True, field_name

    return False, None


def _validate_discriminated_union(
    value: Any,
    union_types: tuple,
    discriminator_field: str,
    field_path: str,
    metadata: Any = None,
) -> None:
    """Validate a discriminated union by checking the discriminator.

    Args:
        value: Value to validate (must be dict)
        union_types: Types in the Union
        discriminator_field: Name of discriminator field
        field_path: Path to field
        metadata: Optional metadata

    Raises:
        ValidationError: If validation fails
    """
    source_loc = _get_source_location(metadata, field_path) if metadata else None

    if not isinstance(value, dict):
        raise ValidationError(
            f"Discriminated union requires dict, got {type(value).__name__}",
            field_path=field_path,
            actual_value=value,
            source_location=source_loc,
        )

    # Check discriminator field exists
    if discriminator_field not in value:
        dataclass_types = [t for t in union_types if dataclasses.is_dataclass(t)]
        type_names = ", ".join(t.__name__ for t in dataclass_types)
        raise ValidationError(
            f"Missing discriminator field '{discriminator_field}' (required for union of {type_names})",
            field_path=field_path,
            actual_value=value,
            source_location=source_loc,
        )

    discriminator_value = value[discriminator_field]

    # Find matching type
    dataclass_types = [t for t in union_types if dataclasses.is_dataclass(t)]
    matching_type = None

    for dc_type in dataclass_types:
        for f in dataclasses.fields(dc_type):
            if f.name == discriminator_field:
                literal_values = get_args(f.type)
                if discriminator_value in literal_values:
                    matching_type = dc_type
                    break
        if matching_type:
            break

    if matching_type is None:
        # Build helpful error with valid values
        valid_values = []
        for dc_type in dataclass_types:
            for f in dataclasses.fields(dc_type):
                if f.name == discriminator_field:
                    literal_values = get_args(f.type)
                    for val in literal_values:
                        valid_values.append(f"'{val}' ({dc_type.__name__})")

        valid_str = ", ".join(valid_values)
        raise ValidationError(
            f"Invalid discriminator value '{discriminator_value}'. Valid: {valid_str}",
            field_path=field_path,
            actual_value=value,
            source_location=source_loc,
        )

    # Validate against the selected type
    validate(value, matching_type, field_path, metadata)


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
        # Check for discriminated union first
        has_discriminator, discriminator_field = _find_discriminator(args)
        if has_discriminator and discriminator_field:
            _validate_discriminated_union(value, args, discriminator_field, field_path, metadata)
            return

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
                # Union with multiple non-None types - try each and collect errors
                errors = []
                for union_type in non_none_types:
                    try:
                        _validate_field(value, union_type, field_path, metadata)
                        return  # Validation succeeded
                    except ValidationError as e:
                        type_name = getattr(union_type, "__name__", str(union_type))
                        # Extract just the error message without field path prefix
                        error_msg = str(e).split("\n")[0]
                        if f"Validation error at '{field_path}': " in error_msg:
                            error_msg = error_msg.replace(f"Validation error at '{field_path}': ", "")
                        errors.append(f"  Tried {type_name}: {error_msg}")

                # All failed - build comprehensive error message
                union_types = ", ".join(getattr(t, "__name__", str(t)) for t in non_none_types)
                error_details = "\n".join(errors)
                raise ValidationError(
                    f"Value doesn't match any type in Union[{union_types}]\n{error_details}",
                    field_path=field_path,
                    expected_type=expected_type,
                    actual_value=value,
                    source_location=source_loc,
                )
        else:
            # Non-Optional Union - try each type and collect errors
            errors = []
            for union_type in args:
                try:
                    _validate_field(value, union_type, field_path, metadata)
                    return  # Validation succeeded
                except ValidationError as e:
                    type_name = getattr(union_type, "__name__", str(union_type))
                    # Extract just the error message without field path prefix
                    error_msg = str(e).split("\n")[0]
                    if f"Validation error at '{field_path}': " in error_msg:
                        error_msg = error_msg.replace(f"Validation error at '{field_path}': ", "")
                    errors.append(f"  Tried {type_name}: {error_msg}")

            # All failed - build comprehensive error message
            union_types = ", ".join(getattr(t, "__name__", str(t)) for t in args)
            error_details = "\n".join(errors)
            raise ValidationError(
                f"Value doesn't match any type in Union[{union_types}]\n{error_details}",
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

    # Handle Literal types
    from typing import Literal

    if origin is Literal:
        if value not in args:
            valid_values = ", ".join(repr(v) for v in args)
            raise ValidationError(
                f"Value must be one of {valid_values}, got {value!r}",
                field_path=field_path,
                expected_type=expected_type,
                actual_value=value,
                source_location=source_loc,
            )
        return

    # Handle basic types (int, str, float, bool, etc.)
    if not isinstance(value, expected_type):
        # Special case: accept resolved references (@), raw references (%), and expressions ($) as strings
        # since they'll be resolved/expanded later
        if isinstance(value, str) and (value.startswith("@") or value.startswith("$") or value.startswith("%")):
            # This is a resolved reference/raw reference/expression that will be processed later
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
