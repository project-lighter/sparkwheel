<br/>
<div align="center">
  <img src="assets/images/sparkwheel_banner.png" width="65%"/>
</div>
<br/><br/>
<p align="center">
  <a href="https://github.com/project-lighter/sparkwheel/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/project-lighter/sparkwheel/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://codecov.io/gh/project-lighter/sparkwheel"><img alt="Coverage" src="https://codecov.io/gh/project-lighter/sparkwheel/branch/main/graph/badge.svg"></a>
  <a href="https://pypi.org/project/sparkwheel/"><img alt="PyPI" src="https://img.shields.io/pypi/v/sparkwheel"></a>
  <a href="https://github.com/project-lighter/sparkwheel/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Apache%202.0-blue.svg"></a>
  <a href="https://project-lighter.github.io/sparkwheel"><img alt="Documentation" src="https://img.shields.io/badge/docs-latest-olive"></a>
</p>

<h3 align="center">YAML configuration meets Python</h3>
<p align="center">Define Python objects in YAML. Reference, compose, and instantiate them effortlessly.</p>
<br/>

## Quick Start

```bash
pip install sparkwheel
```

```yaml
# config.yaml
dataset:
  num_classes: 10
  batch_size: 32

model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: "%dataset::num_classes"  # Reference

training:
  steps_per_epoch: "$10000 // @dataset::batch_size"  # Expression
```

```python
from sparkwheel import Config

config = Config()
config.update("config.yaml")

model = config.resolve("model")  # Actual torch.nn.Linear(784, 10)
```

## Features

- **Declarative Objects** - Instantiate any Python class with `_target_`
- **Smart References** - `@` for resolved values, `%` for raw YAML
- **Composition by Default** - Dicts merge, lists extend automatically
- **Explicit Control** - `=` to replace, `~` to delete
- **Python Expressions** - Dynamic values with `$`
- **Schema Validation** - Type-check with dataclasses

**[Get Started](https://project-lighter.github.io/sparkwheel/getting-started/quickstart/)** · **[Documentation](https://project-lighter.github.io/sparkwheel/)** · **[Quick Reference](https://project-lighter.github.io/sparkwheel/user-guide/quick-reference/)**

## Community

- [Discord](https://discord.gg/zJcnp6KrUp) · [YouTube](https://www.youtube.com/channel/UCef1oTpv2QEBrD2pZtrdk1Q) · [Issues](https://github.com/project-lighter/sparkwheel/issues)

## About

Sparkwheel is a hard fork of [MONAI Bundle](https://github.com/Project-MONAI/MONAI/tree/dev/monai/bundle)'s config system, with the goal of making a more general-purpose configuration library for Python projects. It combines the best of MONAI Bundle and [Hydra](http://hydra.cc/)/[OmegaComf](https://omegaconf.readthedocs.io/), while introducing new features and improvements not found in either.
