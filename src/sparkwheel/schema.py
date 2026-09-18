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
    config = Config()
    config.update("config.yaml")
    validate(config.get(), ModelConfig)  # Raises error if invalid

    # Or validate during load
    config = Config(schema=ModelConfig)
    config.update("config.yaml")
    ```
"""

import dataclasses
import types
from typing import Any, Union, get_args, get_origin, get_type_hints

from .utils.exceptions import BaseError, Location

__all__ = ["validate", "validator", "ValidationError", "MISSING"]


class _MissingSentinel:
    """Sentinel for required-but-not-yet-set config values."""

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


# Singleton instance
MISSING = _MissingSentinel()


def _is_union_type(origin: Any) -> bool:
    """Check if origin is a Union type (handles both typing.Union and types.UnionType)."""
    if origin is Union:
        return True
    # Python 3.10+ uses types.UnionType for X | Y syntax
    if hasattr(types, "UnionType") and origin is types.UnionType:
        return True
    return False


def _format_union_type(types_tuple: tuple[Any, ...]) -> str:
    """Format a tuple of types as Union[...] for error messages."""
    type_names = []
    for t in types_tuple:
        if hasattr(t, "__name__"):
            type_names.append(t.__name__)
        else:
            type_names.append(str(t))
    return f"Union[{', '.join(type_names)}]"


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


def _schema_hints(schema: type) -> dict[str, Any]:
    try:
        return get_type_hints(schema)
    except (NameError, TypeError) as error:
        raise TypeError(f"Cannot resolve annotations for schema {schema.__name__}: {error}") from error


def _has_deferred(value: Any) -> bool:
    if isinstance(value, _MissingSentinel):
        return True
    if isinstance(value, str):
        return value.startswith(("@", "$", "%"))
    if isinstance(value, dict):
        return any(_has_deferred(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_deferred(item) for item in value)
    return False


def _get_validators(schema_type: type) -> list[Any]:
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
    allow_unresolved: bool = True,
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

    # Framework metadata and lenient extra fields are not dataclass init args.
    values = {field.name: config[field.name] for field in dataclasses.fields(schema) if field.init and field.name in config}
    if allow_unresolved and _has_deferred(values):
        return
    source_loc = _get_source_location(metadata, field_path) if metadata else None
    try:
        instance = schema(**values)
    except Exception as error:
        raise _ValidatorExecutionError(
            f"Cannot construct validation instance for {schema.__name__}: {type(error).__name__}: {error}",
            field_path=field_path,
            source_location=source_loc,
        ) from error

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
            raise _ValidatorExecutionError(
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
        source_location: Location | None = None,
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


class _ValidatorExecutionError(ValidationError):
    """Unexpected user-code errors must not be treated as a union mismatch."""


def validate(
    config: dict[str, Any],
    schema: type,
    field_path: str = "",
    metadata: Any = None,
    allow_missing: bool = False,
    strict: bool = True,
    allow_unresolved: bool = True,
    _run_custom: bool = True,
) -> None:
    """Validate configuration against a dataclass schema.

    Performs recursive type checking to ensure the configuration matches
    the structure and types defined in the dataclass schema.

    Args:
        config: Configuration dictionary to validate
        schema: Dataclass type defining the expected structure
        field_path: Internal parameter for tracking nested field paths
        metadata: Optional metadata registry for source locations
        allow_missing: If True, allow MISSING sentinel values for partial configs
        strict: If True, reject unexpected fields. If False, ignore them.

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

        config = Config().update("app.yaml")
        validate(config.get(), AppConfig)
        ```
    """
    if not dataclasses.is_dataclass(schema):
        raise TypeError(f"Schema must be a dataclass, got {type(schema).__name__}")

    if not isinstance(config, dict):
        source_loc = _get_source_location(metadata, field_path) if metadata else None  # type: ignore[unreachable]
        raise ValidationError(
            f"Expected dict for dataclass {schema.__name__}",
            field_path=field_path,
            expected_type=dict,
            actual_value=config,
            source_location=source_loc,
        )

    # Get all fields from the dataclass
    schema_fields = {f.name: f for f in dataclasses.fields(schema)}
    hints = _schema_hints(schema)

    # Check for required fields
    for field_name, field_info in schema_fields.items():
        current_path = f"{field_path}.{field_name}" if field_path else field_name

        # Check if field is missing
        if field_name not in config:
            # Field has default or default_factory -> optional
            if field_info.default is not dataclasses.MISSING or field_info.default_factory is not dataclasses.MISSING:
                continue
            # No default -> required
            source_loc = _get_source_location(metadata, field_path) if metadata else None
            raise ValidationError(
                f"Missing required field '{field_name}'",
                field_path=current_path,
                expected_type=hints[field_name],
                source_location=source_loc,
            )

        # Validate the field value
        _validate_field(
            config[field_name],
            hints[field_name],
            current_path,
            metadata,
            allow_missing=allow_missing,
            strict=strict,
            allow_unresolved=allow_unresolved,
            _run_custom=_run_custom,
        )

    # Check for unexpected fields - only if strict mode
    if strict:
        unexpected_fields = set(config.keys()) - set(schema_fields.keys())
        # Filter out sparkwheel special keys
        special_keys = {"_target_", "_disabled_", "_mode_", "_imports_", "_args_"}
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
    if _run_custom:
        _run_validators(config, schema, field_path, metadata, allow_unresolved=allow_unresolved)


def _find_discriminator(union_types: tuple[Any, ...]) -> tuple[bool, str | None]:
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
    dataclass_types = [t for t in union_types if isinstance(t, type) and dataclasses.is_dataclass(t)]
    if len(dataclass_types) < 2:
        return False, None

    # Find fields that exist in all types with Literal annotation
    all_fields: dict[str, list[Any]] = {}
    for dc_type in dataclass_types:
        for f in dataclasses.fields(dc_type):
            if get_origin(_schema_hints(dc_type)[f.name]) is Literal:
                if f.name not in all_fields:
                    all_fields[f.name] = []
                literal_values = get_args(_schema_hints(dc_type)[f.name])
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
    union_types: tuple[Any, ...],
    discriminator_field: str,
    field_path: str,
    metadata: Any = None,
    allow_missing: bool = False,
    strict: bool = True,
    allow_unresolved: bool = True,
    _run_custom: bool = True,
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
        dataclass_types = [t for t in union_types if isinstance(t, type) and dataclasses.is_dataclass(t)]
        type_names = ", ".join(t.__name__ if isinstance(t, type) else type(t).__name__ for t in dataclass_types)
        raise ValidationError(
            f"Missing discriminator field '{discriminator_field}' (required for union of {type_names})",
            field_path=field_path,
            actual_value=value,
            source_location=source_loc,
        )

    discriminator_value = value[discriminator_field]

    if allow_unresolved and isinstance(discriminator_value, str) and discriminator_value.startswith(("@", "$", "%")):
        # The selected branch is not known until resolution.
        return

    # Find matching type
    dataclass_types = [t for t in union_types if isinstance(t, type) and dataclasses.is_dataclass(t)]
    matching_type = None

    for dc_type in dataclass_types:
        for f in dataclasses.fields(dc_type):
            if f.name == discriminator_field:
                literal_values = get_args(_schema_hints(dc_type)[f.name])
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
                    literal_values = get_args(_schema_hints(dc_type)[f.name])
                    for val in literal_values:
                        type_name = dc_type.__name__ if isinstance(dc_type, type) else type(dc_type).__name__
                        valid_values.append(f"'{val}' ({type_name})")

        valid_str = ", ".join(valid_values)
        raise ValidationError(
            f"Invalid discriminator value '{discriminator_value}'. Valid: {valid_str}",
            field_path=field_path,
            actual_value=value,
            source_location=source_loc,
        )

    # Validate against the selected type
    assert isinstance(matching_type, type)
    validate(
        value,
        matching_type,
        field_path,
        metadata,
        allow_missing=allow_missing,
        strict=strict,
        allow_unresolved=allow_unresolved,
        _run_custom=_run_custom,
    )


def _validate_field(
    value: Any,
    expected_type: Any,
    field_path: str,
    metadata: Any = None,
    allow_missing: bool = False,
    strict: bool = True,
    allow_unresolved: bool = True,
    _run_custom: bool = True,
) -> None:
    """Validate a value with the same policy at every nested boundary."""
    source_loc = _get_source_location(metadata, field_path) if metadata else None
    policy = dict(allow_missing=allow_missing, strict=strict, allow_unresolved=allow_unresolved, _run_custom=_run_custom)
    if isinstance(value, _MissingSentinel):
        if allow_missing:
            return
        raise ValidationError(
            "Field has MISSING value but MISSING not allowed",
            field_path=field_path,
            expected_type=expected_type,
            actual_value=value,
            source_location=source_loc,
        )
    if allow_unresolved and isinstance(value, str) and value.startswith(("@", "$", "%")):
        return
    if expected_type is Any:
        return
    origin, args = get_origin(expected_type), get_args(expected_type)
    if _is_union_type(origin):
        if value is None and type(None) in args:
            return
        branches = tuple(branch for branch in args if branch is not type(None)) if type(None) in args else args
        has_discriminator, discriminator = _find_discriminator(branches)
        if (
            has_discriminator
            and discriminator
            and all(isinstance(branch, type) and dataclasses.is_dataclass(branch) for branch in branches)
        ):
            _validate_discriminated_union(value, branches, discriminator, field_path, metadata, **policy)
            return
        errors = []
        for branch in branches:
            try:
                _validate_field(value, branch, field_path, metadata, **policy)
                return
            except _ValidatorExecutionError:
                raise
            except ValidationError as error:
                name = getattr(branch, "__name__", str(branch))
                message = str(error).split("\n")[0].removeprefix(f"Validation error at '{field_path}': ")
                errors.append(f"  Tried {name}: {message}")
        raise ValidationError(
            f"Value doesn't match any type in {_format_union_type(branches)}\n" + "\n".join(errors),
            field_path=field_path,
            expected_type=expected_type,
            actual_value=value,
            source_location=source_loc,
        )
    if origin is list:
        if not isinstance(value, list):
            raise ValidationError(
                "Expected list", field_path=field_path, expected_type=list, actual_value=value, source_location=source_loc
            )
        if args:
            for i, item in enumerate(value):
                _validate_field(item, args[0], f"{field_path}[{i}]", metadata, **policy)
        return
    if origin is dict:
        if not isinstance(value, dict):
            raise ValidationError(
                "Expected dict", field_path=field_path, expected_type=dict, actual_value=value, source_location=source_loc
            )
        if len(args) == 2:
            for key, item in value.items():
                if args[0] is not Any and not isinstance(key, args[0]):
                    raise ValidationError(
                        "Dict key has wrong type",
                        field_path=f"{field_path}[{key!r}]",
                        expected_type=args[0],
                        actual_value=key,
                        source_location=source_loc,
                    )
                _validate_field(item, args[1], f"{field_path}[{key!r}]", metadata, **policy)
        return
    if isinstance(expected_type, type) and dataclasses.is_dataclass(expected_type):
        validate(value, expected_type, field_path, metadata, **policy)
        return
    from typing import Literal

    if origin is Literal:
        if not any(type(value) is type(candidate) and value == candidate for candidate in args):
            valid_values = ", ".join(repr(candidate) for candidate in args)
            raise ValidationError(
                f"Value must be one of {valid_values}, got {value!r}",
                field_path=field_path,
                expected_type=expected_type,
                actual_value=value,
                source_location=source_loc,
            )
        return
    # Preserve integer compatibility for float annotations, without treating bool
    # as a numeric parameter just because bool subclasses int in Python.
    if expected_type is float and type(value) is int:
        return
    numeric_bool = expected_type in (int, float) and type(value) is bool
    if numeric_bool or not isinstance(value, expected_type):
        raise ValidationError(
            "Type mismatch", field_path=field_path, expected_type=expected_type, actual_value=value, source_location=source_loc
        )


def _coerce_field(
    value: Any,
    expected_type: Any,
    field_path: str = "",
    metadata: Any = None,
    *,
    strict: bool = True,
    allow_missing: bool = False,
    allow_unresolved: bool = True,
    _preserve: set[int] | None = None,
) -> Any:
    """Conservative normalization; never execute targets, validators or defaults."""
    if _preserve and id(value) in _preserve:
        return value

    options = dict(strict=strict, allow_missing=allow_missing, allow_unresolved=allow_unresolved)
    if isinstance(value, _MissingSentinel) or expected_type is Any:
        return value
    if allow_unresolved and isinstance(value, str) and value.startswith(("@", "$", "%")):
        return value
    origin, args = get_origin(expected_type), get_args(expected_type)
    if _is_union_type(origin):
        _, discriminator = _find_discriminator(args)
        if allow_unresolved and discriminator and isinstance(value, dict) and _has_deferred(value.get(discriminator)):
            return value
        # Preserve already-valid alternatives, especially a literal string in
        # str|int. Type checks here never run user validators.
        for branch in args:
            try:
                _validate_field(value, branch, field_path, metadata, _run_custom=False, **options)
            except ValidationError:
                continue
            return _coerce_field(value, branch, field_path, metadata, **options, _preserve=_preserve)
        candidates = []
        for branch in args:
            try:
                candidate = _coerce_field(value, branch, field_path, metadata, **options, _preserve=_preserve)
                _validate_field(candidate, branch, field_path, metadata, _run_custom=False, **options)
                candidates.append(candidate)
            except ValidationError:
                continue
        if len(candidates) > 1:
            raise ValidationError(
                f"Ambiguous coercion to {_format_union_type(args)}; supply an explicitly typed value",
                field_path=field_path,
                actual_value=value,
                source_location=_get_source_location(metadata, field_path),
            )
        return candidates[0] if candidates else value
    if isinstance(expected_type, type) and dataclasses.is_dataclass(expected_type) and isinstance(value, dict):
        result = dict(value)
        for name, annotation in _schema_hints(expected_type).items():
            if name in result:
                path = f"{field_path}.{name}" if field_path else name
                result[name] = _coerce_field(result[name], annotation, path, metadata, **options, _preserve=_preserve)
        return result
    if origin is list and isinstance(value, list) and args:
        return [
            _coerce_field(item, args[0], f"{field_path}[{i}]", metadata, **options, _preserve=_preserve)
            for i, item in enumerate(value)
        ]
    if origin is dict and isinstance(value, dict) and len(args) == 2:
        # Keys retain their identity and spelling: coercing keys can collapse two
        # distinct entries. Their declared types are validated normally.
        return {
            key: _coerce_field(item, args[1], f"{field_path}[{key!r}]", metadata, **options, _preserve=_preserve)
            for key, item in value.items()
        }
    try:
        if expected_type is int:
            if type(value) is str:
                return int(value)
            if type(value) is float and value.is_integer():
                return int(value)
        elif expected_type is float:
            if type(value) is str:
                return float(value)
            if type(value) is int:
                try:
                    converted = float(value)
                except OverflowError as error:
                    raise ValidationError(
                        "Integer cannot be represented as float",
                        field_path=field_path,
                        actual_value=value,
                        source_location=_get_source_location(metadata, field_path),
                    ) from error
                if int(converted) != value:
                    raise ValidationError(
                        "Integer cannot be represented exactly as float",
                        field_path=field_path,
                        actual_value=value,
                        source_location=_get_source_location(metadata, field_path),
                    )
                return converted
        elif expected_type is bool:
            if type(value) is str:
                normalized = value.strip().lower()
                if normalized in {"true", "yes", "1"}:
                    return True
                if normalized in {"false", "no", "0"}:
                    return False
            elif type(value) is int and value in (0, 1):
                return bool(value)
        elif expected_type is str and type(value) in (int, float, bool):
            return str(value)
    except (ValueError, OverflowError):
        # Ordinary validation produces the source-aware type error.
        pass
    return value


def _get_source_location(metadata: Any, field_path: str) -> Location | None:
    """Get source location from metadata registry.

    Args:
        metadata: LocationRegistry instance
        field_path: Dot-separated field path to look up

    Returns:
        Location if found, None otherwise
    """
    if metadata is None:
        return None

    try:
        # Convert dot notation to :: notation used by sparkwheel
        id_path = field_path.replace(".", "::")
        result = metadata.get(id_path)
        return result if result is None or isinstance(result, Location) else None
    except Exception:
        return None
