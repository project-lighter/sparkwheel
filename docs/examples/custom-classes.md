# Custom Classes Example

Using Sparkwheel with your own classes.

## Python Code

```python
# myproject/models.py
class CustomModel:
    def __init__(self, input_size: int, hidden_size: int, output_size: int):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size

    def forward(self, x):
        # Your model logic
        pass
```

## Configuration

```yaml
# config.yaml
model:
  _target_: myproject.models.CustomModel
  input_size: 784
  hidden_size: 256
  output_size: 10
```

## Usage

```python
from sparkwheel import ConfigParser

parser = ConfigParser.load("config.yaml")

model = parser.resolve("model")
# model is now an instance of CustomModel!
```
