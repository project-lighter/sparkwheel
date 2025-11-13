"""Tests for @validator decorator."""

from dataclasses import dataclass

import pytest

from sparkwheel import Config, ValidationError, validator


class TestValidator:
    """Test @validator decorator."""

    def test_single_field_validation(self):
        """Test validating a single field."""

        @dataclass
        class TestConfig:
            lr: float

            @validator
            def check_lr(self):
                if not (0 < self.lr < 1):
                    raise ValueError("lr must be between 0 and 1")

        # Valid
        config = Config.load({"lr": 0.5}, schema=TestConfig)
        assert config["lr"] == 0.5

        # Invalid
        with pytest.raises(ValidationError, match="lr must be between 0 and 1"):
            Config.load({"lr": 5.0}, schema=TestConfig)

    def test_multiple_validators(self):
        """Test multiple validator methods."""

        @dataclass
        class TestConfig:
            lr: float
            batch_size: int

            @validator
            def check_lr(self):
                if not (0 < self.lr < 1):
                    raise ValueError("lr must be between 0 and 1")

            @validator
            def check_batch_size(self):
                if self.batch_size <= 0:
                    raise ValueError("batch_size must be positive")

        # Valid
        Config.load({"lr": 0.5, "batch_size": 32}, schema=TestConfig)

        # First validator fails
        with pytest.raises(ValidationError, match="lr must be between 0 and 1"):
            Config.load({"lr": 5.0, "batch_size": 32}, schema=TestConfig)

        # Second validator fails
        with pytest.raises(ValidationError, match="batch_size must be positive"):
            Config.load({"lr": 0.5, "batch_size": -1}, schema=TestConfig)

    def test_multiple_checks_in_one_validator(self):
        """Test multiple checks in a single validator."""

        @dataclass
        class TestConfig:
            port: int

            @validator
            def check_port(self):
                if not (1024 <= self.port <= 65535):
                    raise ValueError("port must be 1024-65535")
                if self.port % 2 != 0:
                    raise ValueError("port must be even")

        Config.load({"port": 8080}, schema=TestConfig)

        with pytest.raises(ValidationError, match="1024-65535"):
            Config.load({"port": 80}, schema=TestConfig)

        with pytest.raises(ValidationError, match="must be even"):
            Config.load({"port": 8081}, schema=TestConfig)

    def test_cross_field_validation(self):
        """Test validation across multiple fields."""

        @dataclass
        class TestConfig:
            start: int
            end: int

            @validator
            def check_range(self):
                if self.end <= self.start:
                    raise ValueError("end must be > start")

        Config.load({"start": 1, "end": 10}, schema=TestConfig)

        with pytest.raises(ValidationError, match="end must be > start"):
            Config.load({"start": 10, "end": 5}, schema=TestConfig)

    def test_validators_run_after_type_checking(self):
        """Test validators only run if types are correct."""
        called = []

        @dataclass
        class TestConfig:
            value: int

            @validator
            def track(self):
                called.append(True)

        # Type error - validator not called
        called.clear()
        with pytest.raises(ValidationError, match="Type mismatch"):
            Config.load({"value": "not int"}, schema=TestConfig)
        assert len(called) == 0

        # Type correct - validator called
        called.clear()
        Config.load({"value": 42}, schema=TestConfig)
        assert len(called) == 1

    def test_validator_with_optional_fields(self):
        """Test validators with optional fields."""

        @dataclass
        class TestConfig:
            value: int
            max_value: int | None = None

            @validator
            def check_max(self):
                if self.max_value is not None and self.value > self.max_value:
                    raise ValueError("value exceeds max_value")

        Config.load({"value": 100}, schema=TestConfig)
        Config.load({"value": 50, "max_value": 100}, schema=TestConfig)

        with pytest.raises(ValidationError, match="value exceeds max_value"):
            Config.load({"value": 150, "max_value": 100}, schema=TestConfig)

    def test_nested_dataclasses(self):
        """Test validators in nested dataclasses."""

        @dataclass
        class Inner:
            x: int

            @validator
            def check_x(self):
                if self.x <= 0:
                    raise ValueError("x must be positive")

        @dataclass
        class Outer:
            inner: Inner

        Config.load({"inner": {"x": 10}}, schema=Outer)

        with pytest.raises(ValidationError, match="x must be positive"):
            Config.load({"inner": {"x": -5}}, schema=Outer)

    def test_validator_error_includes_field_path(self):
        """Test error includes field path for nested configs."""

        @dataclass
        class Inner:
            value: int

            @validator
            def check(self):
                if self.value < 0:
                    raise ValueError("must be positive")

        @dataclass
        class Outer:
            inner: Inner

        with pytest.raises(ValidationError) as exc_info:
            Config.load({"inner": {"value": -5}}, schema=Outer)

        assert "inner" in str(exc_info.value)

    def test_validators_skip_on_references(self):
        """Test that configs with references skip validators."""

        @dataclass
        class TestConfig:
            base: float
            lr: float

            @validator
            def check_lr(self):
                if not (0 < self.lr < 1):
                    raise ValueError("lr must be 0-1")

        # Reference should skip validation
        Config.load({"base": 0.001, "lr": "@base"}, schema=TestConfig)

    def test_validators_skip_on_expressions(self):
        """Test that configs with expressions skip validators."""

        @dataclass
        class TestConfig:
            value: int

            @validator
            def check(self):
                if self.value <= 0:
                    raise ValueError("must be positive")

        Config.load({"value": "$2 + 2"}, schema=TestConfig)

    def test_validator_exception_handling(self):
        """Test unexpected exceptions in validators."""

        @dataclass
        class TestConfig:
            value: int

            @validator
            def bad_validator(self):
                return 1 / 0  # ZeroDivisionError

        with pytest.raises(ValidationError, match="ZeroDivisionError"):
            Config.load({"value": 42}, schema=TestConfig)

    def test_complex_multi_field_validation(self):
        """Test complex validation across multiple fields."""

        @dataclass
        class TestConfig:
            min_lr: float
            max_lr: float
            current_lr: float

            @validator
            def a_check_lr_range(self):
                if self.min_lr >= self.max_lr:
                    raise ValueError("min_lr must be < max_lr")

            @validator
            def b_check_current_lr(self):
                if not (self.min_lr <= self.current_lr <= self.max_lr):
                    raise ValueError("current_lr must be between min_lr and max_lr")

        Config.load({"min_lr": 0.0, "max_lr": 1.0, "current_lr": 0.5}, schema=TestConfig)

        with pytest.raises(ValidationError, match="min_lr must be < max_lr"):
            Config.load({"min_lr": 1.0, "max_lr": 0.0, "current_lr": 0.5}, schema=TestConfig)

        with pytest.raises(ValidationError, match="current_lr must be between"):
            Config.load({"min_lr": 0.0, "max_lr": 1.0, "current_lr": 2.0}, schema=TestConfig)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
