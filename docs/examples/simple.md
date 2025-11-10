# Simple Configuration Example

A basic example showing core Sparkwheel features.

## Configuration File

```yaml
# simple_config.yaml
project:
  name: "Image Classifier"
  version: "1.0.0"

dataset:
  path: "/data/images"
  num_classes: 10
  image_size: 224

model:
  _target_: torch.nn.Sequential
  _args_:
    - _target_: torch.nn.Flatten
    - _target_: torch.nn.Linear
      in_features: "$@dataset::image_size ** 2 * 3"  # 224*224*3
      out_features: "@dataset::num_classes"

training:
  batch_size: 32
  epochs: 10
  learning_rate: 0.001
```

## Usage

```python
import torch
from sparkwheel import ConfigParser

# Load configuration
parser = ConfigParser.load("simple_config.yaml")

# Get values
project_name = parser["project"]["name"]
num_classes = parser["dataset"]["num_classes"]

# Instantiate model
model = parser.resolve("model")
print(model)

# Access training parameters
batch_size = parser["training"]["batch_size"]
epochs = parser["training"]["epochs"]
lr = parser["training"]["learning_rate"]

print(f"Training {project_name} for {epochs} epochs with lr={lr}")
```
