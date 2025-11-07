# Installation

Sparkwheel requires Python 3.10 or higher.

## Install from PyPI

The simplest way to install Sparkwheel:

```bash
pip install sparkwheel
```

## Install from Source

For the latest development version:

```bash
git clone https://github.com/project-lighter/sparkwheel.git
cd sparkwheel
pip install -e .
```

## Development Setup

If you want to contribute to Sparkwheel, we use [uv](https://github.com/astral-sh/uv) and [just](https://github.com/casey/just) for development:

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install just

=== "macOS"
    ```bash
    brew install just
    ```

=== "Linux"
    ```bash
    # Using cargo
    cargo install just

    # Or download binary from GitHub releases
    ```

=== "Windows"
    ```powershell
    # Using cargo
    cargo install just

    # Or use scoop
    scoop install just
    ```

### Setup Development Environment

```bash
git clone https://github.com/project-lighter/sparkwheel.git
cd sparkwheel
just setup
```

This will:

- Install all dependencies (including dev, test, and doc groups)
- Set up pre-commit hooks
- Configure your development environment

## Verify Installation

Test that Sparkwheel is installed correctly:

```python
import sparkwheel
print(sparkwheel.__version__)
```

## Optional Dependencies

Sparkwheel has minimal dependencies (only PyYAML). However, for certain use cases you might want:

### For Deep Learning

```bash
pip install torch torchvision  # PyTorch
# or
pip install tensorflow  # TensorFlow
```

### For Development

All development dependencies are included in the `dev` dependency group:

```bash
uv sync --all-groups
```

This includes:

- Testing: pytest, pytest-cov, coverage
- Code quality: ruff, mypy
- Documentation: mkdocs and plugins
- Tools: pre-commit, bump-my-version

## Next Steps

- [Quick Start](quickstart.md) - Learn the basics
- [User Guide](../user-guide/basics.md) - Deep dive into features
