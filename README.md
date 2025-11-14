<br/>
<div align="center">
  <img src="assets/images/sparkwheel_banner.png" width="65%"/>
</div>
<br/><br/>
<p align="center">
  <a href="https://github.com/project-lighter/sparkwheel/actions"><img alt="Tests" src="https://github.com/project-lighter/sparkwheel/workflows/Tests/badge.svg"></a>
  <a href="https://codecov.io/gh/project-lighter/sparkwheel"><img alt="Coverage" src="https://codecov.io/gh/project-lighter/sparkwheel/branch/main/graph/badge.svg"></a>
  <a href="https://pypi.org/project/sparkwheel/"><img alt="PyPI" src="https://img.shields.io/pypi/v/sparkwheel"></a>
  <a href="https://github.com/project-lighter/sparkwheel/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Apache%202.0-blue.svg"></a>
  <a href="https://project-lighter.github.io/sparkwheel"><img alt="Documentation" src="https://img.shields.io/badge/docs-latest-olive"></a>
</p>
<br/>

<p align="center">⚙️ YAML configuration meets Python 🐍</p>
<p align="center">Define Python objects in YAML. Reference, compose, and instantiate them effortlessly.</p>
<br/>

## What is Sparkwheel?

Stop hardcoding parameters. Define complex Python objects in clean YAML files, compose them naturally, and instantiate with one line.

```yaml
# config.yaml
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: "%dataset::num_classes"  # Reference other values

dataset:
  num_classes: 10
```

```python
from sparkwheel import Config

config = Config.load("config.yaml")
model = config.resolve("model")  # Actual torch.nn.Linear(784, 10) instance!
```

## Key Features

- **Declarative Object Creation** - Instantiate any Python class from YAML with `_target_`
- **Smart References** - `@` for resolved values, `%` for raw YAML
- **Composition by Default** - Configs merge naturally (dicts merge, lists extend)
- **Explicit Operators** - `=` to replace, `~` to delete when needed
- **Python Expressions** - Compute values dynamically with `$` prefix
- **Schema Validation** - Type-check configs with Python dataclasses
- **CLI Overrides** - Override any value from command line

## Installation

```bash
pip install sparkwheel
```

**[→ Get Started in 5 Minutes](https://project-lighter.github.io/sparkwheel/getting-started/quickstart/)**

## Coming from Hydra/OmegaConf?

Sparkwheel builds on similar ideas but adds powerful features:

| Feature | Hydra/OmegaConf | Sparkwheel |
|---------|-----------------|------------|
| Config composition | Explicit (`+`, `++`) | **By default** (dicts merge, lists extend) |
| Replace semantics | Default | Explicit with `=` operator |
| Delete keys | Not idempotent | Idempotent `~` operator |
| References | OmegaConf interpolation | `@` (resolved) + `%` (raw YAML) |
| Python expressions | Limited | Full Python with `$` |
| Schema validation | Structured Configs | Python dataclasses |
| List extension | Lists replace | **Lists extend by default** |

**Composition by default** means configs merge naturally without operators:
```yaml
# base.yaml
model:
  hidden_size: 256
  dropout: 0.1

# experiment.yaml
model:
  hidden_size: 512  # Override
  # dropout inherited
```

## Documentation

- [Full Documentation](https://project-lighter.github.io/sparkwheel/)
- [Quick Start Guide](https://project-lighter.github.io/sparkwheel/getting-started/quickstart/)
- [Core Concepts](https://project-lighter.github.io/sparkwheel/user-guide/basics/)
- [Examples](https://project-lighter.github.io/sparkwheel/examples/simple/)
- [API Reference](https://project-lighter.github.io/sparkwheel/reference/)

## Community

- [Discord Server](https://discord.gg/zJcnp6KrUp) - Chat with the community
- [YouTube Channel](https://www.youtube.com/channel/UCef1oTpv2QEBrD2pZtrdk1Q) - Tutorials and demos
- [GitHub Issues](https://github.com/project-lighter/sparkwheel/issues) - Bug reports and feature requests

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## About

Sparkwheel is a hard fork of [MONAI Bundle](https://github.com/Project-MONAI/MONAI/tree/dev/monai/bundle)'s configuration system, refined and expanded for general-purpose use. We're deeply grateful to the MONAI team for their excellent foundation.

Sparkwheel powers [Lighter](https://project-lighter.github.io/lighter/), our configuration-driven deep learning framework built on PyTorch Lightning.

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.
