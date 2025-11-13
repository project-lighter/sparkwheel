"""
Comprehensive tests for schema validation using dataclasses.

This module tests the schema validation feature, including:
- Basic type validation
- Required vs optional fields
- Nested dataclasses
- Lists and dictionaries
- Union types and Optional
- Integration with Config
- Error messages and source locations
"""

from dataclasses import dataclass, field
from typing import Literal

import pytest

from sparkwheel import Config, ValidationError, validate


class TestBasicValidation:
    """Test basic schema validation."""

    def test_simple_schema_valid(self):
        """Test validation passes for valid simple schema."""

        @dataclass
        class SimpleConfig:
            name: str
            value: int

        config = {"name": "test", "value": 42}
        validate(config, SimpleConfig)  # Should not raise

    def test_simple_schema_invalid_type(self):
        """Test validation fails for wrong type."""

        @dataclass
        class SimpleConfig:
            name: str
            value: int

        config = {"name": "test", "value": "not an int"}
        with pytest.raises(ValidationError, match="Type mismatch"):
            validate(config, SimpleConfig)

    def test_missing_required_field(self):
        """Test validation fails for missing required field."""

        @dataclass
        class RequiredConfig:
            required_field: str

        config = {}
        with pytest.raises(ValidationError, match="Missing required field 'required_field'"):
            validate(config, RequiredConfig)

    def test_optional_field_missing(self):
        """Test validation passes when optional field is missing."""

        @dataclass
        class OptionalConfig:
            required: str
            optional: str = "default"

        config = {"required": "value"}
        validate(config, OptionalConfig)  # Should not raise

    def test_unexpected_field(self):
        """Test validation fails for unexpected field."""

        @dataclass
        class StrictConfig:
            name: str

        config = {"name": "test", "unexpected": "value"}
        with pytest.raises(ValidationError, match="Unexpected field 'unexpected'"):
            validate(config, StrictConfig)

    def test_sparkwheel_special_keys_ignored(self):
        """Test that sparkwheel special keys are ignored."""

        @dataclass
        class ComponentConfig:
            lr: float

        config = {
            "_target_": "torch.optim.Adam",
            "lr": 0.001,
            "_disabled_": False,
        }
        validate(config, ComponentConfig)  # Should not raise


class TestTypeValidation:
    """Test validation of different types."""

    def test_int_validation(self):
        """Test int type validation."""

        @dataclass
        class IntConfig:
            count: int

        validate({"count": 42}, IntConfig)
        with pytest.raises(ValidationError):
            validate({"count": "not int"}, IntConfig)

    def test_float_validation(self):
        """Test float type validation."""

        @dataclass
        class FloatConfig:
            value: float

        validate({"value": 3.14}, FloatConfig)
        validate({"value": 42}, FloatConfig)  # int should work for float
        with pytest.raises(ValidationError):
            validate({"value": "not float"}, FloatConfig)

    def test_str_validation(self):
        """Test str type validation."""

        @dataclass
        class StrConfig:
            text: str

        validate({"text": "hello"}, StrConfig)
        with pytest.raises(ValidationError):
            validate({"text": 123}, StrConfig)

    def test_bool_validation(self):
        """Test bool type validation."""

        @dataclass
        class BoolConfig:
            flag: bool

        validate({"flag": True}, BoolConfig)
        validate({"flag": False}, BoolConfig)
        with pytest.raises(ValidationError):
            validate({"flag": "yes"}, BoolConfig)


class TestOptionalTypes:
    """Test Optional type handling."""

    def test_optional_with_value(self):
        """Test Optional field with value."""

        @dataclass
        class OptConfig:
            maybe: int | None

        validate({"maybe": 42}, OptConfig)

    def test_optional_with_none(self):
        """Test Optional field with None."""

        @dataclass
        class OptConfig:
            maybe: int | None

        validate({"maybe": None}, OptConfig)

    def test_optional_missing(self):
        """Test Optional field can be missing if it has default."""

        @dataclass
        class OptConfig:
            maybe: int | None = None

        validate({}, OptConfig)  # Should not raise

    def test_optional_wrong_type(self):
        """Test Optional field with wrong type."""

        @dataclass
        class OptConfig:
            maybe: int | None

        with pytest.raises(ValidationError):
            validate({"maybe": "not int"}, OptConfig)


class TestListValidation:
    """Test list type validation."""

    def test_list_of_ints(self):
        """Test list[int] validation."""

        @dataclass
        class ListConfig:
            numbers: list[int]

        validate({"numbers": [1, 2, 3]}, ListConfig)

    def test_list_of_ints_invalid_item(self):
        """Test list[int] fails with non-int item."""

        @dataclass
        class ListConfig:
            numbers: list[int]

        with pytest.raises(ValidationError, match=r"numbers\[1\]"):
            validate({"numbers": [1, "two", 3]}, ListConfig)

    def test_list_of_strings(self):
        """Test list[str] validation."""

        @dataclass
        class ListConfig:
            items: list[str]

        validate({"items": ["a", "b", "c"]}, ListConfig)

    def test_empty_list(self):
        """Test empty list validation."""

        @dataclass
        class ListConfig:
            items: list[int]

        validate({"items": []}, ListConfig)

    def test_not_a_list(self):
        """Test non-list value for list field."""

        @dataclass
        class ListConfig:
            items: list[int]

        with pytest.raises(ValidationError, match="Expected list"):
            validate({"items": "not a list"}, ListConfig)


class TestDictValidation:
    """Test dict type validation."""

    def test_dict_str_int(self):
        """Test dict[str, int] validation."""

        @dataclass
        class DictConfig:
            mapping: dict[str, int]

        validate({"mapping": {"a": 1, "b": 2}}, DictConfig)

    def test_dict_invalid_value_type(self):
        """Test dict with wrong value type."""

        @dataclass
        class DictConfig:
            mapping: dict[str, int]

        with pytest.raises(ValidationError):
            validate({"mapping": {"a": 1, "b": "not int"}}, DictConfig)

    def test_dict_invalid_key_type(self):
        """Test dict with wrong key type."""

        @dataclass
        class DictConfig:
            mapping: dict[str, int]

        # Python dicts must have str keys in YAML
        config = {"mapping": {1: 10}}  # int key
        with pytest.raises(ValidationError, match="Dict key has wrong type"):
            validate(config, DictConfig)

    def test_not_a_dict(self):
        """Test non-dict value for dict field."""

        @dataclass
        class DictConfig:
            mapping: dict[str, int]

        with pytest.raises(ValidationError, match="Expected dict"):
            validate({"mapping": "not a dict"}, DictConfig)


class TestNestedDataclasses:
    """Test nested dataclass validation."""

    def test_nested_dataclass(self):
        """Test validation with nested dataclass."""

        @dataclass
        class InnerConfig:
            value: int

        @dataclass
        class OuterConfig:
            name: str
            inner: InnerConfig

        config = {"name": "test", "inner": {"value": 42}}
        validate(config, OuterConfig)

    def test_nested_dataclass_invalid(self):
        """Test nested dataclass with invalid inner value."""

        @dataclass
        class InnerConfig:
            value: int

        @dataclass
        class OuterConfig:
            name: str
            inner: InnerConfig

        config = {"name": "test", "inner": {"value": "not int"}}
        with pytest.raises(ValidationError, match=r"inner\.value"):
            validate(config, OuterConfig)

    def test_deeply_nested(self):
        """Test deeply nested dataclasses."""

        @dataclass
        class Level3:
            value: int

        @dataclass
        class Level2:
            level3: Level3

        @dataclass
        class Level1:
            level2: Level2

        config = {"level2": {"level3": {"value": 42}}}
        validate(config, Level1)

    def test_nested_missing_field(self):
        """Test nested dataclass with missing required field."""

        @dataclass
        class InnerConfig:
            required: str

        @dataclass
        class OuterConfig:
            inner: InnerConfig

        config = {"inner": {}}
        with pytest.raises(ValidationError, match="Missing required field 'required'"):
            validate(config, OuterConfig)


class TestComplexSchemas:
    """Test complex schema combinations."""

    def test_list_of_dataclasses(self):
        """Test list containing dataclasses."""

        @dataclass
        class ItemConfig:
            name: str
            value: int

        @dataclass
        class ListConfig:
            items: list[ItemConfig]

        config = {
            "items": [
                {"name": "first", "value": 1},
                {"name": "second", "value": 2},
            ]
        }
        validate(config, ListConfig)

    def test_dict_of_dataclasses(self):
        """Test dict with dataclass values."""

        @dataclass
        class ModelConfig:
            hidden_size: int

        @dataclass
        class Config:
            models: dict[str, ModelConfig]

        config = {
            "models": {
                "small": {"hidden_size": 128},
                "large": {"hidden_size": 512},
            }
        }
        validate(config, Config)

    def test_optional_nested_dataclass(self):
        """Test optional nested dataclass."""

        @dataclass
        class OptionalInner:
            value: int

        @dataclass
        class OuterConfig:
            maybe_inner: OptionalInner | None = None

        validate({}, OuterConfig)
        validate({"maybe_inner": None}, OuterConfig)
        validate({"maybe_inner": {"value": 42}}, OuterConfig)


class TestReferencesAndExpressions:
    """Test that references and expressions are allowed."""

    def test_reference_allowed(self):
        """Test that @ references pass type validation."""

        @dataclass
        class RefConfig:
            base_value: int
            ref_value: int

        config = {"base_value": 42, "ref_value": "@base_value"}
        validate(config, RefConfig)  # Should not raise

    def test_expression_allowed(self):
        """Test that $ expressions pass type validation."""

        @dataclass
        class ExprConfig:
            computed: int

        config = {"computed": "$2 + 2"}
        validate(config, ExprConfig)  # Should not raise

    def test_macro_allowed(self):
        """Test that % macros pass type validation."""

        @dataclass
        class MacroConfig:
            value: dict

        config = {"value": "%other::config"}
        validate(config, MacroConfig)  # Should not raise


class TestConfigIntegration:
    """Test integration with Config class."""

    def test_config_load_with_schema(self):
        """Test Config.load with schema validation."""

        @dataclass
        class AppConfig:
            name: str
            port: int

        config = Config.load({"name": "myapp", "port": 8080}, schema=AppConfig)
        assert config["name"] == "myapp"
        assert config["port"] == 8080

    def test_config_load_with_schema_invalid(self):
        """Test Config.load fails with invalid schema."""

        @dataclass
        class AppConfig:
            name: str
            port: int

        with pytest.raises(ValidationError):
            Config.load({"name": "myapp", "port": "not int"}, schema=AppConfig)

    def test_config_validate_method(self):
        """Test Config.validate method."""

        @dataclass
        class Schema:
            value: int

        config = Config.load({"value": 42})
        config.validate(Schema)  # Should not raise

    def test_config_validate_method_invalid(self):
        """Test Config.validate method with invalid config."""

        @dataclass
        class Schema:
            value: int

        config = Config.load({"value": "not int"})
        with pytest.raises(ValidationError):
            config.validate(Schema)

    def test_schema_not_dataclass(self):
        """Test error when schema is not a dataclass."""

        class NotADataclass:
            pass

        config = Config.load({"value": 42})
        with pytest.raises(TypeError, match="Schema must be a dataclass"):
            config.validate(NotADataclass)


class TestErrorMessages:
    """Test error message quality."""

    def test_error_message_includes_field_path(self):
        """Test error message includes field path."""

        @dataclass
        class Schema:
            value: int

        try:
            validate({"value": "wrong"}, Schema)
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            assert "value" in str(e)
            assert e.field_path == "value"

    def test_error_message_includes_types(self):
        """Test error message includes type information."""

        @dataclass
        class Schema:
            count: int

        try:
            validate({"count": "string"}, Schema)
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            assert "int" in str(e)
            assert "str" in str(e)

    def test_error_message_nested_path(self):
        """Test error message for nested field."""

        @dataclass
        class Inner:
            value: int

        @dataclass
        class Outer:
            inner: Inner

        try:
            validate({"inner": {"value": "wrong"}}, Outer)
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            assert "inner.value" in str(e)
            assert e.field_path == "inner.value"


class TestRealWorldSchemas:
    """Test realistic configuration schemas."""

    def test_ml_training_config(self):
        """Test machine learning training configuration schema."""

        @dataclass
        class OptimizerConfig:
            lr: float
            momentum: float = 0.9
            weight_decay: float = 0.0

        @dataclass
        class ModelConfig:
            hidden_size: int
            num_layers: int
            dropout: float

        @dataclass
        class TrainingConfig:
            batch_size: int
            epochs: int
            model: ModelConfig
            optimizer: OptimizerConfig

        config = {
            "batch_size": 32,
            "epochs": 100,
            "model": {
                "hidden_size": 512,
                "num_layers": 6,
                "dropout": 0.1,
            },
            "optimizer": {
                "lr": 0.001,
                "momentum": 0.95,
            },
        }

        validate(config, TrainingConfig)

    def test_web_api_config(self):
        """Test web API configuration schema."""

        @dataclass
        class DatabaseConfig:
            host: str
            port: int
            username: str
            password: str
            pool_size: int = 10

        @dataclass
        class ServerConfig:
            host: str = "0.0.0.0"
            port: int = 8000
            debug: bool = False

        @dataclass
        class APIConfig:
            server: ServerConfig
            database: DatabaseConfig
            secret_key: str

        config = {
            "server": {"port": 3000},
            "database": {
                "host": "localhost",
                "port": 5432,
                "username": "admin",
                "password": "secret",
            },
            "secret_key": "my-secret",
        }

        validate(config, APIConfig)

    def test_config_with_lists_and_defaults(self):
        """Test configuration with lists and default values."""

        @dataclass
        class PluginConfig:
            name: str
            enabled: bool = True

        @dataclass
        class AppConfig:
            name: str
            version: str = "1.0.0"
            plugins: list[PluginConfig] = field(default_factory=list)
            tags: list[str] = field(default_factory=list)

        config = {
            "name": "MyApp",
            "plugins": [
                {"name": "logger"},
                {"name": "cache", "enabled": False},
            ],
        }

        validate(config, AppConfig)


class TestImprovedUnionErrors:
    """Test improved error messages for Union types."""

    def test_union_error_shows_all_attempts(self):
        """Test that Union errors show why each type failed."""

        @dataclass
        class Config:
            value: int | str | float

        with pytest.raises(ValidationError) as exc_info:
            validate({"value": []}, Config)

        error_msg = str(exc_info.value)
        assert "Union[int, str, float]" in error_msg
        assert "Tried int:" in error_msg
        assert "Tried str:" in error_msg
        assert "Tried float:" in error_msg

    def test_union_error_with_dataclass(self):
        """Test Union error messages with dataclass options."""

        @dataclass
        class Inner:
            x: int

        @dataclass
        class Config:
            value: Inner | str

        with pytest.raises(ValidationError) as exc_info:
            validate({"value": {"x": "not int"}}, Config)

        error_msg = str(exc_info.value)
        assert "Tried Inner:" in error_msg
        assert "Tried str:" in error_msg

    def test_optional_union_error_messages(self):
        """Test error messages for Optional with multiple types."""

        @dataclass
        class Config:
            value: int | str | None

        with pytest.raises(ValidationError) as exc_info:
            validate({"value": []}, Config)

        error_msg = str(exc_info.value)
        assert "Tried int:" in error_msg or "Tried str:" in error_msg


class TestDiscriminatedUnions:
    """Test discriminated union validation."""

    def test_simple_discriminated_union(self):
        """Test basic discriminated union."""

        @dataclass
        class SGD:
            type: Literal["sgd"]
            lr: float
            momentum: float

        @dataclass
        class Adam:
            type: Literal["adam"]
            lr: float
            beta1: float

        @dataclass
        class TestSchema:
            optimizer: SGD | Adam

        # SGD
        config = Config.load({"optimizer": {"type": "sgd", "lr": 0.01, "momentum": 0.9}}, schema=TestSchema)
        assert config["optimizer::type"] == "sgd"

        # Adam
        config = Config.load({"optimizer": {"type": "adam", "lr": 0.001, "beta1": 0.9}}, schema=TestSchema)
        assert config["optimizer::type"] == "adam"

    def test_missing_discriminator(self):
        """Test error when discriminator is missing."""

        @dataclass
        class TypeA:
            type: Literal["a"]
            value: int

        @dataclass
        class TypeB:
            type: Literal["b"]
            value: str

        @dataclass
        class TestSchema:
            item: TypeA | TypeB

        with pytest.raises(ValidationError, match="Missing discriminator field 'type'"):
            Config.load({"item": {"value": 42}}, schema=TestSchema)

    def test_invalid_discriminator_value(self):
        """Test error on invalid discriminator value."""

        @dataclass
        class TypeA:
            type: Literal["a"]
            value: int

        @dataclass
        class TypeB:
            type: Literal["b"]
            value: str

        @dataclass
        class TestSchema:
            item: TypeA | TypeB

        with pytest.raises(ValidationError, match="Invalid discriminator value 'c'"):
            Config.load({"item": {"type": "c", "value": 42}}, schema=TestSchema)

    def test_validates_selected_type(self):
        """Test that the selected type is validated."""

        @dataclass
        class TypeA:
            type: Literal["a"]
            value: int

        @dataclass
        class TypeB:
            type: Literal["b"]
            value: str

        @dataclass
        class TestSchema:
            item: TypeA | TypeB

        # TypeA with wrong value type
        with pytest.raises(ValidationError, match="item.value"):
            Config.load({"item": {"type": "a", "value": "not int"}}, schema=TestSchema)

    def test_multiple_literal_values(self):
        """Test discriminator with multiple literal values per type."""

        @dataclass
        class Primary:
            type: Literal["primary", "main"]
            value: int

        @dataclass
        class Secondary:
            type: Literal["secondary", "backup"]
            value: int

        @dataclass
        class TestSchema:
            item: Primary | Secondary

        Config.load({"item": {"type": "primary", "value": 1}}, schema=TestSchema)
        Config.load({"item": {"type": "main", "value": 1}}, schema=TestSchema)
        Config.load({"item": {"type": "backup", "value": 2}}, schema=TestSchema)

    def test_non_discriminated_fallback(self):
        """Test non-discriminated unions still work."""

        @dataclass
        class TypeA:
            x: int

        @dataclass
        class TypeB:
            y: str

        @dataclass
        class TestSchema:
            item: TypeA | TypeB

        # No discriminator - tries both
        Config.load({"item": {"x": 42}}, schema=TestSchema)
        Config.load({"item": {"y": "hello"}}, schema=TestSchema)

    def test_discriminated_union_with_validators(self):
        """Test discriminated unions work with @validator."""
        from sparkwheel import validator

        @dataclass
        class SGD:
            type: Literal["sgd"]
            lr: float

            @validator
            def check_lr(self):
                if not (0 < self.lr < 1):
                    raise ValueError("lr must be 0-1")

        @dataclass
        class Adam:
            type: Literal["adam"]
            lr: float

            @validator
            def check_lr(self):
                if not (0 < self.lr < 0.1):
                    raise ValueError("Adam lr must be 0-0.1")

        @dataclass
        class TestSchema:
            optimizer: SGD | Adam

        # SGD with valid lr
        Config.load({"optimizer": {"type": "sgd", "lr": 0.5}}, schema=TestSchema)

        # Adam with lr too high for Adam but valid for SGD
        with pytest.raises(ValidationError, match="Adam lr must be 0-0.1"):
            Config.load({"optimizer": {"type": "adam", "lr": 0.5}}, schema=TestSchema)


class TestValidatorEdgeCases:
    """Test edge cases in validator functionality."""

    def test_validator_with_unresolved_references(self):
        """Test validators are skipped when config has unresolved references."""
        from sparkwheel import validator

        @dataclass
        class Config:
            start: int
            end: int

            @validator
            def check_range(self):
                if self.end <= self.start:
                    raise ValueError("end must be > start")

        # With reference - validator should be skipped, no error
        config = {"start": 10, "end": "@start"}
        validate(config, Config)  # Should not raise

        # With expression - validator should be skipped
        config = {"start": 10, "end": "$5 + 5"}
        validate(config, Config)  # Should not raise

        # With macro - validator should be skipped
        config = {"start": 10, "end": "%other::value"}
        validate(config, Config)  # Should not raise

    def test_validator_non_value_error(self):
        """Test validators that raise non-ValueError exceptions."""
        from sparkwheel import validator

        @dataclass
        class Config:
            value: int

            @validator
            def bad_validator(self):
                raise RuntimeError("Unexpected error in validator")

        with pytest.raises(ValidationError, match="Validator 'bad_validator' raised RuntimeError"):
            validate({"value": 42}, Config)

    def test_validator_instance_creation_fails(self):
        """Test validators are skipped when instance can't be created."""
        from sparkwheel import validator

        @dataclass
        class Config:
            required: int
            optional: str = "default"

            @validator
            def check_value(self):
                if self.required < 0:
                    raise ValueError("required must be >= 0")

        # Missing required field - can't create instance, validator skipped
        config = {"optional": "value"}
        # This will fail on missing field validation, not validator
        with pytest.raises(ValidationError, match="Missing required field"):
            validate(config, Config)


class TestLiteralValidation:
    """Test Literal type validation."""

    def test_literal_valid_value(self):
        """Test Literal with valid value."""

        @dataclass
        class Config:
            mode: Literal["train", "test", "eval"]

        validate({"mode": "train"}, Config)
        validate({"mode": "test"}, Config)
        validate({"mode": "eval"}, Config)

    def test_literal_invalid_value(self):
        """Test Literal with invalid value."""

        @dataclass
        class Config:
            mode: Literal["train", "test"]

        with pytest.raises(ValidationError, match="Value must be one of 'train', 'test'"):
            validate({"mode": "invalid"}, Config)


class TestDiscriminatedUnionEdgeCases:
    """Test edge cases in discriminated union validation."""

    def test_discriminated_union_non_dict_value(self):
        """Test discriminated union with non-dict value."""

        @dataclass
        class TypeA:
            type: Literal["a"]
            value: int

        @dataclass
        class TypeB:
            type: Literal["b"]
            value: str

        @dataclass
        class Config:
            item: TypeA | TypeB

        with pytest.raises(ValidationError, match="Discriminated union requires dict"):
            validate({"item": "not a dict"}, Config)

    def test_discriminator_not_in_all_types(self):
        """Test discriminator detection when field not in all types."""

        @dataclass
        class TypeA:
            type: Literal["a"]
            x: int

        @dataclass
        class TypeB:
            kind: Literal["b"]  # Different field name
            y: str

        @dataclass
        class Config:
            item: TypeA | TypeB

        # No common discriminator, falls back to trying each type
        validate({"item": {"type": "a", "x": 42}}, Config)
        validate({"item": {"kind": "b", "y": "hello"}}, Config)

    def test_discriminator_with_duplicate_values(self):
        """Test discriminator detection when values overlap."""

        @dataclass
        class TypeA:
            type: Literal["shared", "a"]  # "shared" appears in both
            x: int

        @dataclass
        class TypeB:
            type: Literal["shared", "b"]  # "shared" appears in both
            y: str

        @dataclass
        class Config:
            item: TypeA | TypeB

        # Overlapping values mean it's not a valid discriminator
        # Falls back to non-discriminated union
        validate({"item": {"type": "shared", "x": 42}}, Config)


class TestNonDictForDataclass:
    """Test validation error when dict expected for dataclass."""

    def test_dataclass_field_non_dict(self):
        """Test error when non-dict provided for nested dataclass field."""

        @dataclass
        class Inner:
            value: int

        @dataclass
        class Outer:
            inner: Inner

        with pytest.raises(ValidationError, match="Expected dict for dataclass Inner"):
            validate({"inner": "not a dict"}, Outer)


class TestPropertyDescriptors:
    """Test handling of property descriptors in validators."""

    def test_property_in_class_with_validators(self):
        """Test that properties don't interfere with validator detection."""
        from sparkwheel import validator

        @dataclass
        class Config:
            value: int

            @property
            def computed(self):
                return self.value * 2

            @validator
            def check_value(self):
                if self.value < 0:
                    raise ValueError("value must be >= 0")

        validate({"value": 42}, Config)
        with pytest.raises(ValidationError, match="value must be >= 0"):
            validate({"value": -1}, Config)


class TestListWithoutTypeArgs:
    """Test list validation without type arguments."""

    def test_list_without_args(self):
        """Test plain list (no type args) validation."""

        @dataclass
        class Config:
            items: list  # No type args

        # Should accept any list
        validate({"items": []}, Config)
        validate({"items": [1, "two", 3.0, None]}, Config)


class TestDictWithoutTypeArgs:
    """Test dict validation without type arguments."""

    def test_dict_without_args(self):
        """Test plain dict (no type args) validation."""

        @dataclass
        class Config:
            mapping: dict  # No type args

        # Should accept any dict
        validate({"mapping": {}}, Config)
        validate({"mapping": {"a": 1, "b": "two"}}, Config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
