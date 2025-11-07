"""
Basic usage example for sparkwheel.

This example demonstrates the core features:
- References with @
- Expressions with $
- Macros with %
- Component instantiation with _target_
"""

from sparkwheel import ConfigParser

# Example 1: Basic configuration with references
print("=" * 70)
print("Example 1: Basic references")
print("=" * 70)

config1 = {
    "learning_rate": 0.001,
    "batch_size": 32,
    "total_steps": "$10 * @batch_size",  # Expression referencing batch_size
    "optimizer": {
        "_target_": "torch.optim.Adam",
        "lr": "@learning_rate",  # Reference to learning_rate
    },
}

parser1 = ConfigParser(config1)
parser1.parse()

print(f"Batch size: {parser1['batch_size']}")
print(f"Total steps: {parser1.get_parsed_content('total_steps')}")
print(f"Optimizer config: {parser1['optimizer']}")

# Example 2: Component instantiation
print("\n" + "=" * 70)
print("Example 2: Component instantiation")
print("=" * 70)

config2 = {
    "model": {
        "_target_": "torch.nn.Sequential",
        "_args_": [
            {"_target_": "torch.nn.Linear", "in_features": 10, "out_features": 5},
            {"_target_": "torch.nn.ReLU"},
            {"_target_": "torch.nn.Linear", "in_features": 5, "out_features": 2},
        ],
    }
}

parser2 = ConfigParser(config2)
parser2.parse()

# Get the instantiated model
model = parser2.get_parsed_content("model", instantiate=True)
print(f"Model: {model}")

# Example 3: Macros (copying configuration)
print("\n" + "=" * 70)
print("Example 3: Macros")
print("=" * 70)

config3 = {
    "train_transform": {
        "resize": 256,
        "crop": 224,
        "normalize": True,
    },
    "val_transform": "%train_transform",  # Copy train_transform
    "test_transform": "%train_transform",  # Copy train_transform
}

parser3 = ConfigParser(config3)
parser3.parse()

print(f"Train transform: {parser3['train_transform']}")
print(f"Val transform: {parser3['val_transform']}")
print(f"Test transform: {parser3['test_transform']}")

# Example 4: Nested references
print("\n" + "=" * 70)
print("Example 4: Nested references with ::")
print("=" * 70)

config4 = {
    "network": {
        "hidden_dim": 128,
        "output_dim": 10,
    },
    "classifier": {
        "_target_": "torch.nn.Linear",
        "in_features": "@network::hidden_dim",  # Reference nested value
        "out_features": "@network::output_dim",
    },
}

parser4 = ConfigParser(config4)
parser4.parse()

print(f"Network config: {parser4['network']}")
print(f"Classifier uses hidden_dim: {parser4['network::hidden_dim']}")

# Example 5: Conditional instantiation with _disabled_
print("\n" + "=" * 70)
print("Example 5: Conditional instantiation")
print("=" * 70)

config5 = {
    "use_scheduler": False,
    "scheduler": {
        "_target_": "torch.optim.lr_scheduler.StepLR",
        "_disabled_": "$not @use_scheduler",  # Conditionally disable
        "step_size": 10,
    },
}

parser5 = ConfigParser(config5)
parser5.parse()

scheduler = parser5.get_parsed_content("scheduler", instantiate=True)
print(f"Scheduler (should be None): {scheduler}")

# Example 6: Using _requires_ for dependencies
print("\n" + "=" * 70)
print("Example 6: Dependencies with _requires_")
print("=" * 70)

config6 = {
    "_requires_": ["$import os"],  # Import statements
    "home_dir": "$os.path.expanduser('~')",
    "data_dir": "$@home_dir + '/data'",
}

parser6 = ConfigParser(config6)
parser6.parse()

print(f"Home directory: {parser6.get_parsed_content('home_dir')}")
print(f"Data directory: {parser6.get_parsed_content('data_dir')}")

print("\n" + "=" * 70)
print("All examples completed successfully!")
print("=" * 70)
