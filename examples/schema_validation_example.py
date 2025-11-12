"""
Schema validation example for Sparkwheel.

This example demonstrates how to use dataclass schemas to validate
configurations at runtime.
"""

from dataclasses import dataclass, field
from typing import Optional

from sparkwheel import Config, ValidationError

# =============================================================================
# Example 1: Basic Schema Validation
# =============================================================================

print("=" * 70)
print("Example 1: Basic Schema Validation")
print("=" * 70)


@dataclass
class BasicConfig:
    """Simple configuration schema."""

    name: str
    value: int
    enabled: bool = True


# Valid configuration
valid_config = {"name": "test", "value": 42, "enabled": False}

config = Config.load(valid_config, schema=BasicConfig)
print(f"Valid config loaded: {config.get()}")

# Invalid configuration (wrong type)
invalid_config = {"name": "test", "value": "not a number", "enabled": True}

try:
    Config.load(invalid_config, schema=BasicConfig)
except ValidationError as e:
    print(f"\nValidation error caught: {e}")


# =============================================================================
# Example 2: Nested Schemas
# =============================================================================

print("\n" + "=" * 70)
print("Example 2: Nested Schemas")
print("=" * 70)


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str
    port: int
    username: str
    password: str
    pool_size: int = 10


@dataclass
class AppConfig:
    """Application configuration with nested database config."""

    app_name: str
    debug: bool
    database: DatabaseConfig


app_config_dict = {
    "app_name": "MyApp",
    "debug": True,
    "database": {
        "host": "localhost",
        "port": 5432,
        "username": "admin",
        "password": "secret",
        "pool_size": 20,
    },
}

config = Config.load(app_config_dict, schema=AppConfig)
print(f"App name: {config['app_name']}")
print(f"Database host: {config['database::host']}")
print(f"Pool size: {config['database::pool_size']}")


# =============================================================================
# Example 3: Lists and Optional Fields
# =============================================================================

print("\n" + "=" * 70)
print("Example 3: Lists and Optional Fields")
print("=" * 70)


@dataclass
class PluginConfig:
    """Configuration for a plugin."""

    name: str
    version: str
    enabled: bool = True
    config_file: Optional[str] = None


@dataclass
class SystemConfig:
    """System configuration with plugins."""

    system_name: str
    plugins: list[PluginConfig]
    tags: list[str] = field(default_factory=list)


system_config_dict = {
    "system_name": "PluginSystem",
    "plugins": [
        {"name": "logger", "version": "1.0"},
        {"name": "metrics", "version": "2.1", "enabled": False},
        {"name": "cache", "version": "1.5", "config_file": "/etc/cache.yaml"},
    ],
    "tags": ["production", "critical"],
}

config = Config.load(system_config_dict, schema=SystemConfig)
print(f"System: {config['system_name']}")
print(f"Number of plugins: {len(config['plugins'])}")
print(f"Tags: {config['tags']}")


# =============================================================================
# Example 4: Schema with References and Expressions
# =============================================================================

print("\n" + "=" * 70)
print("Example 4: Schema with References and Expressions")
print("=" * 70)


@dataclass
class TrainingConfig:
    """ML training configuration."""

    batch_size: int
    learning_rate: float
    num_epochs: int
    total_steps: int  # Can be computed via expression


training_config_dict = {
    "batch_size": 32,
    "learning_rate": 0.001,
    "num_epochs": 100,
    "total_steps": "$@batch_size * @num_epochs",  # Expression
}

config = Config.load(training_config_dict, schema=TrainingConfig)
print(f"Batch size: {config['batch_size']}")
print(f"Learning rate: {config['learning_rate']}")
print(f"Epochs: {config['num_epochs']}")

# Resolve to get computed value
resolved = config.resolve()
print(f"Total steps (computed): {resolved['total_steps']}")


# =============================================================================
# Example 5: Validation After Modifications
# =============================================================================

print("\n" + "=" * 70)
print("Example 5: Validation After Modifications")
print("=" * 70)


@dataclass
class ModifiableConfig:
    """Config that can be modified and re-validated."""

    count: int
    threshold: float


# Load without initial validation
config = Config.load({"count": 10, "threshold": 0.5})
print(f"Initial config: count={config['count']}, threshold={config['threshold']}")

# Modify
config["count"] = 20
config["threshold"] = 0.75
print(f"Modified config: count={config['count']}, threshold={config['threshold']}")

# Validate after modification
config.validate(ModifiableConfig)
print("Validation passed after modification")

# Try invalid modification
config["count"] = "not a number"
try:
    config.validate(ModifiableConfig)
except ValidationError as e:
    print(f"\nValidation error after bad modification: {e}")


# =============================================================================
# Example 6: Real-World ML Configuration
# =============================================================================

print("\n" + "=" * 70)
print("Example 6: Real-World ML Configuration")
print("=" * 70)


@dataclass
class OptimizerConfig:
    """Optimizer configuration."""

    lr: float
    momentum: float = 0.9
    weight_decay: float = 0.0


@dataclass
class ModelConfig:
    """Model architecture configuration."""

    hidden_size: int
    num_layers: int
    dropout: float
    activation: str = "relu"


@dataclass
class DataConfig:
    """Data loading configuration."""

    batch_size: int
    num_workers: int = 4
    shuffle: bool = True
    data_path: str = "./data"


@dataclass
class MLConfig:
    """Complete ML training configuration."""

    experiment_name: str
    seed: int
    epochs: int
    model: ModelConfig
    optimizer: OptimizerConfig
    data: DataConfig


ml_config_dict = {
    "experiment_name": "bert_finetuning",
    "seed": 42,
    "epochs": 10,
    "model": {
        "hidden_size": 768,
        "num_layers": 12,
        "dropout": 0.1,
        "activation": "gelu",
    },
    "optimizer": {
        "lr": 0.00005,
        "weight_decay": 0.01,
    },
    "data": {
        "batch_size": 16,
        "num_workers": 8,
        "data_path": "/datasets/squad",
    },
}

config = Config.load(ml_config_dict, schema=MLConfig)
print(f"Experiment: {config['experiment_name']}")
print(f"Model: {config['model::num_layers']} layers, {config['model::hidden_size']} hidden")
print(f"Optimizer LR: {config['optimizer::lr']}")
print(f"Batch size: {config['data::batch_size']}")


# =============================================================================
# Example 7: Component Instantiation with Schema
# =============================================================================

print("\n" + "=" * 70)
print("Example 7: Component Instantiation with Schema")
print("=" * 70)


@dataclass
class OptimizerComponentConfig:
    """Schema for optimizer that will be instantiated."""

    lr: float
    momentum: float = 0.9


optimizer_config_dict = {
    "_target_": "collections.Counter",  # Special key ignored by schema
    "lr": 0.001,
    "momentum": 0.95,
}

# Schema validation ignores _target_, _disabled_, etc.
config = Config.load(optimizer_config_dict, schema=OptimizerComponentConfig)
print(f"Optimizer config validated: lr={config['lr']}, momentum={config['momentum']}")
print("Note: _target_ is automatically ignored by schema validation")


print("\n" + "=" * 70)
print("All examples completed successfully!")
print("=" * 70)
