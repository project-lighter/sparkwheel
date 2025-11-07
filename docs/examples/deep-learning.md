# Deep Learning Example

Complete deep learning setup with model, optimizer, and data pipeline.

## Configuration

```yaml
# training_config.yaml
dataset:
  root: "/data/cifar10"
  num_classes: 10

transforms:
  train:
    _target_: torchvision.transforms.Compose
    transforms:
      - _target_: torchvision.transforms.RandomHorizontalFlip
      - _target_: torchvision.transforms.ToTensor
      - _target_: torchvision.transforms.Normalize
        mean: [0.485, 0.456, 0.406]
        std: [0.229, 0.224, 0.225]

model:
  _target_: torchvision.models.resnet18
  num_classes: "@dataset::num_classes"

optimizer:
  _target_: torch.optim.Adam
  params: "$@model.parameters()"
  lr: 0.001

scheduler:
  _target_: torch.optim.lr_scheduler.StepLR
  optimizer: "@optimizer"
  step_size: 30
  gamma: 0.1

training:
  epochs: 100
  batch_size: 64
  device: "$'cuda' if torch.cuda.is_available() else 'cpu'"
```

See the [User Guide](../user-guide/basics.md) for more details.
