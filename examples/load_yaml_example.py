"""
Example of loading and using a YAML configuration file.
"""

from sparkwheel import ConfigParser

# Load configuration from YAML file
parser = ConfigParser("yaml_config_example.yaml")

# Parse the configuration
parser.parse()

# Access raw config values
print("=" * 70)
print("Raw configuration values")
print("=" * 70)
print(f"Learning rate: {parser['learning_rate']}")
print(f"Batch size: {parser['batch_size']}")
print(f"Number of epochs: {parser['num_epochs']}")

# Access computed values (expressions)
print("\n" + "=" * 70)
print("Computed values (expressions)")
print("=" * 70)
total_iterations = parser.get_parsed_content("total_iterations")
print(f"Total iterations: {total_iterations}")

# Access nested values
print("\n" + "=" * 70)
print("Nested configuration access")
print("=" * 70)
print(f"Optimizer learning rate: {parser['optimizer::lr']}")
print(f"Train dataloader batch size: {parser['train_dataloader::batch_size']}")

# Instantiate components
print("\n" + "=" * 70)
print("Instantiate components")
print("=" * 70)

# Get the criterion (loss function)
criterion = parser.get_parsed_content("criterion", instantiate=True)
print(f"Criterion: {criterion}")

# Modify configuration at runtime
print("\n" + "=" * 70)
print("Modify configuration at runtime")
print("=" * 70)
parser["learning_rate"] = 0.01
print(f"Updated learning rate: {parser['learning_rate']}")

# Re-parse to apply changes
parser.parse()
new_lr = parser["optimizer::lr"]
print(f"Optimizer now uses new learning rate: {new_lr}")

# Get all config as dictionary
print("\n" + "=" * 70)
print("Export configuration")
print("=" * 70)
all_config = parser.get()
print(f"Configuration keys: {list(all_config.keys())}")

# Save modified configuration
parser.export_config_file(all_config, "modified_config.yaml")
print("Saved modified configuration to 'modified_config.yaml'")
